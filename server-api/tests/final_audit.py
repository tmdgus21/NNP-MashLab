"""Exact JSON live audit + latency and Linux Qwen memory measurements.

Run on the server: python3 server-api/tests/final_audit.py /tmp/conditional-ok-audit
No inference is mocked. Expectation objects are defined before making requests.
"""
import json
import pathlib
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

EMPTY = {"availability": [], "role_preferences": [], "role_unavailable": [], "companion_requirement": [], "ambiguities": []}


def interval(start, end, kind="available", strength="required"):
    return {"date": "2026-10-17", "start": start, "end": end, "kind": kind, "strength": strength}


CASES = [
    ("가능시간", "오후 2시부터 오후 4시까지 가능해요.", {"availability": [interval("14:00", "16:00")]}),
    ("불가능시간", "14:00~16:00에는 참여가 불가능해요.", {"availability": [interval("14:00", "16:00", "unavailable")]}),
    ("역할선호·역할불가", "기록 역할을 선호해요. 촬영 역할은 못 해요.", {"role_preferences": [{"role": "기록", "strength": "preferred"}], "role_unavailable": ["촬영"]}),
    ("필수역할", "저는 반드시 진행 역할을 맡아야 해요.", {"role_preferences": [{"role": "진행", "strength": "required"}]}),
    ("필수동행", "민지와 반드시 함께 참여해야 해요.", {"companion_requirement": [{"person": "민지", "relation": "together", "strength": "required"}]}),
    ("선호동행", "민지와 가능하면 함께 참여하고 싶어요.", {"companion_requirement": [{"person": "민지", "relation": "together", "strength": "preferred"}]}),
    ("모호한 시간대", "저녁쯤 가능해요.", {"ambiguities": ["저녁의 정확한 시작과 종료 시간을 알려주세요."]}),
    ("선호시간", "14:00~16:00 시간이 좋아요.", {"availability": [interval("14:00", "16:00", strength="preferred")]}),
    ("모호한 시각", "3시쯤 가능해요.", {"ambiguities": ["3시쯤의 정확한 시작과 종료 시간을 알려주세요."]}),
    ("복수가능시간", "09:00~10:00, 15:00~16:00 두 구간에 참여 가능해요.", {"availability": [interval("09:00", "10:00"), interval("15:00", "16:00")]}),
]


def memory(pid):
    values = {}
    for line in pathlib.Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith(("VmRSS:", "VmHWM:", "VmSwap:")):
            key, value, _ = line.split()
            values[key.rstrip(":") + "_KiB"] = int(value)
    return values


def run():
    prefix = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/conditional-ok-audit")
    pid = int(subprocess.check_output(["systemctl", "show", "conditional-ok-qwen.service", "-p", "MainPID", "--value"]))
    samples = []
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            samples.append(memory(pid)["VmRSS_KiB"])
            stop.wait(0.25)

    before = memory(pid)
    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    results = []
    try:
        for index, (category, text, fields) in enumerate(CASES, 1):
            expected = EMPTY | fields
            request = {"text": text, "meeting_date": "2026-10-17"}
            started = time.perf_counter()
            try:
                req = urllib.request.Request("https://oranganman.site/ai/parse-condition", data=json.dumps(request, ensure_ascii=False).encode(), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=75) as response:
                    status, actual = response.status, json.load(response)
            except urllib.error.HTTPError as error:
                status, actual = error.code, json.load(error)
            except Exception as error:
                status, actual = 0, {"error": str(error)}
            result = {"id": index, "category": category, "request": request, "expected": expected, "actual": actual, "http_status": status, "pass": status == 200 and actual == expected, "seconds": round(time.perf_counter() - started, 3)}
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        stop.set()
        thread.join()
    durations = [r["seconds"] for r in results]
    summary = {"boot_id": pathlib.Path("/proc/sys/kernel/random/boot_id").read_text().strip(), "model_pid": pid, "passed": sum(r["pass"] for r in results), "total": len(results), "mean_seconds": round(statistics.mean(durations), 3), "median_seconds": round(statistics.median(durations), 3), "min_seconds": min(durations), "max_seconds": max(durations), "first_request_seconds": durations[0], "warm_mean_seconds": round(statistics.mean(durations[1:]), 3), "memory_before": before, "memory_after": memory(pid), "sampled_peak_RSS_KiB": max(samples), "sampled_mean_RSS_KiB": round(statistics.mean(samples)), "memory_samples": len(samples)}
    data = {"summary": summary, "results": results}
    prefix.with_suffix(".json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    compact = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("|", "\\|")
    lines = ["# 재부팅 후 실제 Qwen 검증", "", "모든 요청 meeting_date=2026-10-17. 배열 순서와 확인 문구를 포함한 전체 JSON 정확 일치로 판정.", "", "| # | 입력 | 기대 JSON | 실제 JSON | 결과 | 초 |", "|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['id']} | {r['request']['text']} | `{compact(r['expected'])}` | `{compact(r['actual'])}` | {'PASS' if r['pass'] else 'FAIL'} | {r['seconds']} |")
    lines.extend(["", "측정 요약:", "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "", "RAM: /proc/<pid>/status의 VmRSS(실제 상주 메모리)를 250ms 간격으로 측정. VmHWM은 프로세스 생애 최대 RSS. 응답시간은 서버에서 공개 HTTPS API를 순차 호출한 종단 간 시간이며, 동시 부하 측정은 아님."])
    prefix.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["passed"] == len(results) else 1


if __name__ == "__main__":
    sys.exit(run())

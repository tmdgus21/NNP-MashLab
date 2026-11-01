"""Run against a real Qwen-backed FastAPI; no mocked inference. Stdlib only."""
import json
import sys
import time
import urllib.request
import urllib.error

base = sys.argv[1] if len(sys.argv) > 1 else "https://oranganman.site"
cases = [
    ("오후 2시부터 오후 4시까지 가능해요.", lambda r: any(x["start"] == "14:00" and x["end"] == "16:00" and x["kind"] == "available" and x["strength"] == "required" for x in r["availability"])),
    ("14:00~16:00에는 참여가 불가능해요.", lambda r: any(x["kind"] == "unavailable" and x["start"] == "14:00" and x["end"] == "16:00" for x in r["availability"]) and not any(x["kind"] == "available" for x in r["availability"])),
    ("기록 역할을 선호해요. 촬영 역할은 못 해요.", lambda r: {"role": "기록", "strength": "preferred"} in r["role_preferences"] and "촬영" in r["role_unavailable"]),
    ("저는 반드시 진행 역할을 맡아야 해요.", lambda r: {"role": "진행", "strength": "required"} in r["role_preferences"]),
    ("민지와 반드시 함께 참여해야 해요.", lambda r: {"person": "민지", "relation": "together", "strength": "required"} in r["companion_requirement"]),
    ("민지와 가능하면 함께 참여하고 싶어요.", lambda r: {"person": "민지", "relation": "together", "strength": "preferred"} in r["companion_requirement"]),
    ("저녁쯤 가능해요.", lambda r: not r["availability"] and bool(r["ambiguities"])),
    ("14:00~16:00 시간이 좋아요.", lambda r: any(x["kind"] == "available" and x["strength"] == "preferred" for x in r["availability"])),
    ("3시쯤 가능해요.", lambda r: not r["availability"] and bool(r["ambiguities"])),
    ("09:00~10:00, 15:00~16:00 두 구간에 참여 가능해요.", lambda r: {(x["start"], x["end"], x["kind"], x["strength"]) for x in r["availability"]} == {("09:00", "10:00", "available", "required"), ("15:00", "16:00", "available", "required")}),
]
failures = 0
for text, check in cases:
    started = time.monotonic()
    try:
        request = urllib.request.Request(base + "/ai/parse-condition", data=json.dumps({"text": text, "meeting_date": "2026-10-17"}).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=75) as response:
            result = json.load(response)
        passed = check(result)
        if not any(ch.isdigit() for ch in text):
            passed = passed and not result["availability"]
        if "역할" in text:
            passed = passed and not result["companion_requirement"]
        if "민지" in text:
            passed = passed and not result["role_preferences"] and not result["role_unavailable"]
        passed = passed and not (set(result["role_unavailable"]) & {item["role"] for item in result["role_preferences"]})
        failures += not passed
        print(json.dumps({"text": text, "pass": passed, "seconds": round(time.monotonic()-started, 2), "response": result}, ensure_ascii=False), flush=True)
    except Exception as exc:
        failures += 1
        detail = exc.read().decode() if isinstance(exc, urllib.error.HTTPError) else str(exc)
        print(json.dumps({"text": text, "pass": False, "error": detail}, ensure_ascii=False), flush=True)
print(f"LIVE: {len(cases)-failures}/{len(cases)} passed", flush=True)
sys.exit(bool(failures))

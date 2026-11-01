"""Maintenance test: briefly stop Qwen, verify API isolation, then restore it."""
import json
import subprocess
import time
import urllib.error
import urllib.request

UNITS = ["conditional-ok-qwen-proxy.socket", "conditional-ok-qwen-proxy.service", "conditional-ok-qwen.service"]


def fetch(url, payload=None):
    request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=75) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


try:
    subprocess.run(["sudo", "-n", "systemctl", "stop", *UNITS], check=True)
    assert fetch("https://oranganman.site/")[0] == 200
    code, body = fetch("https://oranganman.site/ai/parse-condition", {"text": "기록 역할을 선호해요."})
    assert code == 503 and body["detail"]["code"] == "AI_UNAVAILABLE", (code, body)
    print("MODEL DOWN: AI=503 AI_UNAVAILABLE; existing HTTPS root=200", flush=True)
finally:
    subprocess.run(["sudo", "-n", "systemctl", "start", "conditional-ok-qwen.service", "conditional-ok-qwen-proxy.socket"], check=True)

for attempt in range(60):
    try:
        if fetch("http://127.0.0.1:8080/v1/models")[0] == 200:
            break
    except (OSError, ValueError):
        pass
    time.sleep(0.5)
else:
    raise RuntimeError("Qwen did not recover within 30 seconds")
code, body = fetch("https://oranganman.site/ai/parse-condition", {"text": "기록 역할을 선호해요."})
assert code == 200 and {"role": "기록", "strength": "preferred"} in body["role_preferences"], (code, body)
print("MODEL RECOVERY: model list=200; AI=200; FastAPI/Caddy were not restarted", flush=True)

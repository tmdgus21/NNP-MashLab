"""Explicit live regression: creates one temporary in-memory test room."""
import json
import urllib.request
import urllib.error

BASE = "https://oranganman.site"


def request(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


assert request("/")[0] == 200
payload = {"title": "AI API 회귀 테스트", "date": "2026-10-17", "start_time": "14:00", "end_time": "16:00", "owner_nickname": "검증", "roles": [{"name": "진행", "need_count": 1}]}
status, room = request("/rooms", payload)
assert status == 201, (status, room)
assert len(room["code"]) == 8 and "roomCode" not in room
assert room["roles"] == payload["roles"]
assert room["members"] == [{"nickname": "검증", "is_owner": True}]
assert request("/rooms", {})[0] == 422
assert request("/v1/models")[0] == 404  # Caddy has no public llama.cpp route.
status, api = request("/openapi.json")
assert status == 200 and "/rooms" in api["paths"] and "/ai/parse-condition" in api["paths"]
print("LIVE regression PASS: HTTPS root=200, rooms=201/code, invalid rooms=422, public model route=404, OpenAPI paths present")
print(json.dumps(room, ensure_ascii=False))

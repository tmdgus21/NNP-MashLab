import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

import ai_conditions as ai
os.environ.setdefault("DATABASE_URL", "sqlite://")
from main import app
from database import initialize


EMPTY = dict(availability=[], role_preferences=[], role_unavailable=[], companion_requirement=[], ambiguities=[])


def response_for(result):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result, ensure_ascii=False)}}]}


class ApiTests(unittest.TestCase):
    def setUp(self):
        initialize()
        self.client = TestClient(app)

    def call_model(self, output, text="기록을 선호해요", status=200, meeting_date="2026-10-17"):
        def handler(request):
            self.assertEqual(request.url.path, "/v1/chat/completions")
            body = json.loads(request.content)
            self.assertFalse(body["chat_template_kwargs"]["enable_thinking"])
            self.assertIn("schema", body["response_format"])
            return httpx.Response(status, json=output)
        with patch.object(ai, "model_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:8080")):
            return self.client.post("/ai/parse-condition", json={"text": text, "meeting_date": meeting_date})

    def test_korean_schema_cases(self):
        cases = [
            ("오후 2시부터 4시까지 가능해요", {"availability": [{"date": "2026-10-17", "start": "14:00", "end": "16:00", "kind": "available", "strength": "required"}]}),
            ("14:00~16:00은 불가능해요", {"availability": [{"date": "2026-10-17", "start": "14:00", "end": "16:00", "kind": "unavailable", "strength": "required"}]}),
            ("기록을 선호하지만 촬영은 못해요", {"role_preferences": [{"role": "기록", "strength": "preferred"}], "role_unavailable": ["촬영"]}),
            ("반드시 진행을 맡아야 해요", {"role_preferences": [{"role": "진행", "strength": "required"}]}),
            ("민지와 가능하면 함께 하고 싶어요", {"companion_requirement": [{"person": "민지", "relation": "together", "strength": "preferred"}]}),
            ("저녁쯤 가능해요", {"ambiguities": ["저녁쯤의 정확한 시작과 종료 시간을 알려주세요."]}),
        ]
        for text, fields in cases:
            with self.subTest(text=text):
                expected = EMPTY | fields
                response = self.call_model(response_for(expected), text)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), expected)

    def test_malformed_json(self):
        result = response_for(EMPTY)
        result["choices"][0]["message"]["content"] = "```json\n{}\n```"
        self.assertEqual(self.call_model(result).status_code, 502)

    def test_negated_role_is_never_promoted_to_required(self):
        wrong=EMPTY | {'role_preferences':[{'role':'진행','strength':'required'}]}
        for text in ['진행 역할은 못 해요', '진행은 불가능해요']:
            self.assertEqual(self.call_model(response_for(wrong),text).status_code,502)

    def test_missing_and_extra_fields(self):
        for result in ({}, EMPTY | {"schedule": []}, EMPTY | {"role_unavailable": [123]}):
            self.assertEqual(self.call_model(response_for(result)).status_code, 502)

    def test_invalid_times(self):
        for start, end in [("25:00", "26:00"), ("16:00", "14:00"), ("14:00", "14:00")]:
            result = EMPTY | {"availability": [{"date": None, "start": start, "end": end, "kind": "available", "strength": "required"}]}
            self.assertEqual(self.call_model(response_for(result)).status_code, 502)

    def test_invented_date(self):
        result = EMPTY | {"availability": [{"date": "2027-01-01", "start": "14:00", "end": "16:00", "kind": "available", "strength": "required"}]}
        self.assertEqual(self.call_model(response_for(result)).status_code, 502)

    def test_ungrounded_entities_and_times(self):
        cases = [
            {"role_preferences": [{"role": "요리", "strength": "required"}]},
            {"role_unavailable": ["요리"]},
            {"companion_requirement": [{"person": "수빈", "relation": "together", "strength": "required"}]},
            {"availability": [{"date": "2026-10-17", "start": "09:00", "end": "11:00", "kind": "available", "strength": "required"}]},
            {"role_preferences": [{"role": "기록", "strength": "required"}], "role_unavailable": ["기록"]},
        ]
        for fields in cases:
            self.assertEqual(self.call_model(response_for(EMPTY | fields)).status_code, 502)

    def test_missing_date_is_not_invented(self):
        expected = EMPTY | {"availability": [{"date": None, "start": "14:00", "end": "16:00", "kind": "available", "strength": "required"}], "ambiguities": ["참여 날짜를 알려주세요."]}
        self.assertEqual(self.call_model(response_for(expected), "14:00~16:00 가능", meeting_date=None).status_code, 200)

    def test_truncation_and_missing_content(self):
        result = response_for(EMPTY)
        result["choices"][0]["finish_reason"] = "length"
        for output in (result, {"choices": []}, {"choices": None}, {"choices": [None]}, {"choices": [[]]}):
            self.assertEqual(self.call_model(output).status_code, 502)

    def test_model_http_failure(self):
        self.assertEqual(self.call_model({}, status=500).status_code, 503)

    def test_timeout_and_connection_failure(self):
        for error, expected in [(httpx.ReadTimeout("timeout"), 504), (httpx.ConnectError("offline"), 503)]:
            def handler(request):
                raise error
            with patch.object(ai, "model_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:8080")):
                self.assertEqual(self.client.post("/ai/parse-condition", json={"text": "기록 선호"}).status_code, expected)

    def test_busy(self):
        with patch.object(ai._lock, "locked", return_value=True):
            response = self.client.post("/ai/parse-condition", json={"text": "기록 선호"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers["retry-after"], "3")

    def test_invalid_input(self):
        for payload in ({}, {"text": " "}, {"text": "가" * 1501}, {"text": "안녕", "meeting_date": "bad"}):
            self.assertEqual(self.client.post("/ai/parse-condition", json=payload).status_code, 422)

    def test_rooms_regression(self):
        with self.subTest("persistent legacy contract"):
            request = {"title": "회귀검증", "date": "2026-10-17", "start_time": "14:00", "end_time": "16:00", "owner_nickname": "방장", "roles": [{"name": "진행", "need_count": 1}]}
            response = self.client.post("/rooms", json=request)
            self.assertEqual(response.status_code, 201)
            result = response.json()
            self.assertTrue({"room_id", "code", "title", "date", "start_time", "end_time", "members", "roles"}.issubset(result))
            self.assertEqual(len(result["code"]), 8)
            self.assertEqual(result["members"], [{"nickname": "방장", "is_owner": True}])
            self.assertEqual(result["roles"], request["roles"])
            self.assertEqual(self.client.post("/rooms", json={}).status_code, 422)
            self.assertEqual(self.client.post("/rooms", json=request | {"roles": [{"name": "진행", "need_count": 0}]}).status_code, 422)
            self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()

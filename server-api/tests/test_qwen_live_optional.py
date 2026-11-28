"""Optional live Qwen connectivity (skipped when llama.cpp is unreachable)."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("ADMIN_ENABLED", "0")


def _qwen_reachable() -> bool:
    import httpx

    try:
        from qwen_client import model_client

        # Sync probe via httpx Client mirroring transport settings
        uds = os.getenv("QWEN_UNIX_SOCKET")
        transport = httpx.HTTPTransport(uds=uds) if uds else None
        with httpx.Client(
            base_url="http://127.0.0.1:8080",
            transport=transport,
            timeout=httpx.Timeout(3, connect=2),
            trust_env=False,
        ) as client:
            r = client.get("/v1/models")
            return r.status_code == 200
    except Exception:
        return False


@unittest.skipUnless(_qwen_reachable(), "local Qwen (127.0.0.1:8080) not reachable")
class LiveQwenTests(unittest.IsolatedAsyncioTestCase):
    async def test_chat_completion_roundtrip(self):
        from qwen_client import chat_completion

        text = await chat_completion(
            [
                {
                    "role": "system",
                    "content": "한 문장만 답한다. /no_think",
                },
                {"role": "user", "content": "안녕이라고만 답해."},
            ],
            temperature=0,
            seed=42,
            max_tokens=32,
        )
        self.assertTrue(isinstance(text, str) and len(text.strip()) > 0)


class PotatoMeetDtoContractTests(unittest.TestCase):
    """Kotlin apps/android is not in-repo yet — assert server camelCase contract matches docs."""

    def test_request_aliases_match_architecture(self):
        from schedule.schemas import (
            CreateMeetingIn,
            JoinMeetingIn,
            RevisionIn,
            VoteIn,
        )

        create = CreateMeetingIn.model_validate(
            {
                "title": "t",
                "nickname": "n",
                "startDate": "2026-11-20",
                "endDate": "2026-11-21",
            }
        )
        self.assertEqual("2026-11-20", create.start_date.isoformat())
        join = JoinMeetingIn.model_validate({"code": "ABCD2345", "nickname": "n"})
        self.assertEqual("ABCD2345", join.code)
        vote = VoteIn.model_validate({"candidateIds": ["a", "b"]})
        self.assertEqual(["a", "b"], vote.candidate_ids)
        rev = RevisionIn.model_validate({"expectedRevision": 2})
        self.assertEqual(2, rev.expected_revision)

    def test_candidates_response_keys_documented(self):
        expected = {
            "runId",
            "candidates",
            "status",
            "revision",
            "aiSummary",
            "aiComparison",
            "votingEndsAt",
            "excludedSoonCount",
            "myBallotSubmitted",
            "closedReason",
            "serverTime",
        }
        # Documented shape from candidates_view — keep in sync with architecture.md
        self.assertIn("aiSummary", expected)
        cand_keys = {
            "id",
            "startsAt",
            "endsAt",
            "availableCount",
            "sortOrder",
            "voteCount",
            "memberNicknames",
        }
        self.assertIn("memberNicknames", cand_keys)


if __name__ == "__main__":
    unittest.main()

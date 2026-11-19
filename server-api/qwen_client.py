"""Shared Qwen (llama.cpp) HTTP client for parse-condition and schedule summaries."""
from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

MODEL_NAME = "Qwen3-1.7B-Q8_0"
CHAT_PATH = "/v1/chat/completions"
OVERALL_TIMEOUT_S = 65

# One in-flight inference across the process (parse-condition + schedule summary).
_inference_lock = asyncio.Lock()


class QwenBusy(Exception):
    """Another inference holds the lock."""


class QwenTimeout(Exception):
    """Connect/read or overall timeout."""


class QwenUnavailable(Exception):
    """HTTP / transport failure reaching the model."""


class QwenInvalidResponse(Exception):
    """Missing or malformed chat completion payload."""


def model_client() -> httpx.AsyncClient:
    # Docker loopback is separate; optional Unix socket forwards to host 127.0.0.1:8080.
    uds = os.getenv("QWEN_UNIX_SOCKET")
    transport = httpx.AsyncHTTPTransport(uds=uds) if uds else None
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:8080",
        transport=transport,
        timeout=httpx.Timeout(60, connect=3, pool=3),
        trust_env=False,
    )


def is_busy() -> bool:
    return _inference_lock.locked()


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0,
    seed: int | None = 42,
    max_tokens: int = 1200,
    response_format: dict[str, Any] | None = None,
    skip_if_busy: bool = False,
) -> str:
    """POST /v1/chat/completions and return assistant content.

    If the inference lock is held, raises QwenBusy immediately (no queue).
    Callers that can omit work (schedule summary) pass skip_if_busy=True and
    treat QwenBusy as a soft skip; parse-condition maps it to HTTP 503 AI_BUSY.
    """
    _ = skip_if_busy  # documents caller intent; both paths raise when locked
    if _inference_lock.locked():
        raise QwenBusy()
    async with _inference_lock:
        try:
            async with asyncio.timeout(OVERALL_TIMEOUT_S):
                body: dict[str, Any] = {
                    "model": MODEL_NAME,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": False,
                    "chat_template_kwargs": {"enable_thinking": False},
                }
                if seed is not None:
                    body["seed"] = seed
                if response_format is not None:
                    body["response_format"] = response_format
                async with model_client() as client:
                    response = await client.post(CHAT_PATH, json=body)
                    response.raise_for_status()
                    payload = response.json()
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise QwenTimeout() from exc
        except httpx.HTTPError as exc:
            raise QwenUnavailable() from exc
        except QwenBusy:
            raise
        except Exception as exc:
            raise QwenInvalidResponse() from exc

        try:
            choice = payload["choices"][0]
            if not isinstance(choice, dict):
                raise ValueError("invalid model choice object")
            if choice.get("finish_reason") != "stop":
                raise ValueError("incomplete model response")
            content = choice["message"]["content"]
            if not isinstance(content, str) or len(content) > 24000:
                raise ValueError("invalid content")
            return content
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise QwenInvalidResponse() from exc


# Preserve name used by tests that patch concurrency via ai_conditions._lock
inference_lock = _inference_lock

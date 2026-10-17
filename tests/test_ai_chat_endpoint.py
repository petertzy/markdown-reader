"""Tests for the ``/api/ai/chat`` endpoint's provider-error mapping.

Every other AI endpoint (``/work``, ``/translate``, ``/translate/sentences``)
surfaces upstream failures as a meaningful status code with a descriptive
detail. Chat talks to the provider with a bare ``requests.post`` and let
``raise_for_status()`` errors escape the handler, so a rate limit or an
unreachable provider surfaced as a bare 500 "Internal Server Error" with no
detail for the caller to act on. These tests pin the friendly mapping.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import ai_logic as logic
from backend.routers import ai as ai_router


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class TestAiChatUpstreamErrors(unittest.TestCase):
    def _chat_response(self, logic_stub):
        app = FastAPI()
        app.include_router(ai_router.router)
        patcher = patch.object(ai_router, "_logic", return_value=logic_stub)
        patcher.start()
        self.addCleanup(patcher.stop)
        client = TestClient(app)
        return client.post("/chat", json={"message": "Hello"})

    def test_rate_limit_returns_429_with_detail(self):
        class _LogicStub:
            TranslationConfigError = logic.TranslationConfigError

            def request_ai_agent_response(self, *args, **kwargs):
                raise requests.exceptions.HTTPError(
                    "429 Client Error: Too Many Requests",
                    response=_FakeResponse(429),
                )

        response = self._chat_response(_LogicStub())
        self.assertEqual(response.status_code, 429)
        self.assertIn("AI provider request failed", response.json()["detail"])

    def test_connection_error_returns_502(self):
        class _LogicStub:
            TranslationConfigError = logic.TranslationConfigError

            def request_ai_agent_response(self, *args, **kwargs):
                raise requests.exceptions.ConnectionError(
                    "Connection refused by provider"
                )

        response = self._chat_response(_LogicStub())
        self.assertEqual(response.status_code, 502)
        self.assertIn("AI provider request failed", response.json()["detail"])

    def test_successful_chat_response_is_unchanged(self):
        class _LogicStub:
            TranslationConfigError = logic.TranslationConfigError

            def request_ai_agent_response(self, *args, **kwargs):
                return {
                    "assistant_message": "Hi there!",
                    "proposed_action": {
                        "type": "none",
                        "content": "",
                        "reason": "chat_response",
                    },
                    "used_provider": "openai",
                    "used_sources": [],
                }

        response = self._chat_response(_LogicStub())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["assistant_message"], "Hi there!")

"""Tests for bounded retries of transient AI provider failures.

Covers the behavior described in issue #259: 429/503 and transport errors
are retried for a short time, then surfaced with a friendly message instead
of a raw provider error; quota and auth failures stay immediate.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import ai_logic as logic
from backend.ai_logic import ProviderRequestError, _post_with_retry
from backend.routers import ai as ai_router


class _FakeResponse:
    """A minimal stand-in for requests.Response."""

    def __init__(
        self,
        status_code: int,
        payload=None,
        text: str = "",
        headers=None,
        reason: str = "OK",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.headers = headers or {}
        self.reason = reason

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"{self.status_code} {self.reason}")


def _openai_ok_payload() -> dict:
    return {"choices": [{"message": {"content": "# Titel\n\nHallo **Welt**."}}]}


class TestPostWithRetry(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch.object(logic.time, "sleep")
        self.mock_sleep = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_retries_503_then_succeeds(self) -> None:
        responses = [
            _FakeResponse(503, text="server_error"),
            _FakeResponse(200, _openai_ok_payload()),
        ]
        with patch.object(logic.requests, "post", side_effect=responses) as mock_post:
            response = _post_with_retry(
                "http://provider/v1/chat/completions",
                {"Content-Type": "application/json"},
                {"model": "m"},
                base_delay=0.0,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)

    def test_honors_retry_after_header(self) -> None:
        responses = [
            _FakeResponse(
                429,
                text="rate_limit_exceeded",
                headers={"Retry-After": "7"},
            ),
            _FakeResponse(200, _openai_ok_payload()),
        ]
        with patch.object(logic.requests, "post", side_effect=responses):
            _post_with_retry(
                "http://provider/v1/chat/completions",
                {},
                {"model": "m"},
                base_delay=0.0,
            )
        self.assertEqual(self.mock_sleep.call_args_list[0][0][0], 7)

    def test_retries_connection_error(self) -> None:
        def side_effect(*args, **kwargs):
            if logic.requests.post.call_count <= 1:
                raise logic.requests.ConnectionError("dropped")
            return _FakeResponse(200, _openai_ok_payload())

        with patch.object(logic.requests, "post", side_effect=side_effect) as mock_post:
            response = _post_with_retry(
                "http://provider/v1/chat/completions",
                {},
                {"model": "m"},
                base_delay=0.0,
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_count, 2)

    def test_exhausted_503_surfaces_friendly_error(self) -> None:
        responses = [_FakeResponse(503, text="server_error")] * 3
        with patch.object(logic.requests, "post", side_effect=responses):
            with self.assertRaises(ProviderRequestError) as ctx:
                _post_with_retry(
                    "http://provider/v1/chat/completions",
                    {},
                    {"model": "m"},
                    base_delay=0.0,
                )
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("try again shortly", ctx.exception.detail)

    def test_quota_error_is_immediate(self) -> None:
        responses = [_FakeResponse(429, text="insufficient_quota")] * 3
        with patch.object(logic.requests, "post", side_effect=responses) as mock_post:
            with self.assertRaises(ProviderRequestError) as ctx:
                _post_with_retry(
                    "http://provider/v1/chat/completions",
                    {},
                    {"model": "m"},
                    base_delay=0.0,
                )
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(mock_post.call_count, 1)

    def test_auth_failure_is_immediate(self) -> None:
        with patch.object(
            logic.requests,
            "post",
            return_value=_FakeResponse(401, text="unauthorized"),
        ) as mock_post:
            with self.assertRaises(ProviderRequestError) as ctx:
                _post_with_retry(
                    "http://provider/v1/chat/completions",
                    {},
                    {"model": "m"},
                    base_delay=0.0,
                )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(mock_post.call_count, 1)

    def test_non_retryable_400_is_fatal_with_provider_message(self) -> None:
        with patch.object(
            logic.requests,
            "post",
            return_value=_FakeResponse(400, text="context_length_exceeded"),
        ) as mock_post:
            with self.assertRaises(ProviderRequestError) as ctx:
                _post_with_retry(
                    "http://provider/v1/chat/completions",
                    {},
                    {"model": "m"},
                    base_delay=0.0,
                )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("context_length_exceeded", ctx.exception.detail)
        self.assertEqual(mock_post.call_count, 1)


def _openai_batch_payload(*units: str) -> dict:
    pairs = [{"source": unit, "translated": unit + "!"} for unit in units]
    return {"choices": [{"message": {"content": json.dumps({"pairs": pairs})}}]}


class TestSentenceBatchShrinksOnContextError(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch.object(logic.time, "sleep")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def _run_batch(self, responses, units):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "openai_compatible",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                        "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                        "OPENAI_COMPATIBLE_MODEL": "llama-test",
                    },
                ),
                patch.object(
                    logic.requests, "post", side_effect=responses
                ) as mock_post,
            ):
                pairs = logic.translate_markdown_sentence_batch_with_ai(
                    units, "English", "German"
                )
        return pairs, mock_post

    def test_batch_splits_in_half_on_context_length_error(self) -> None:
        responses = [
            _FakeResponse(400, text="context_length_exceeded"),
            _FakeResponse(200, _openai_batch_payload("A", "B")),
            _FakeResponse(200, _openai_batch_payload("C", "D")),
        ]
        pairs, mock_post = self._run_batch(responses, ["A", "B", "C", "D"])
        self.assertEqual([pair["source"] for pair in pairs], ["A", "B", "C", "D"])
        self.assertEqual(mock_post.call_count, 3)

    def test_matching_provider_text_triggers_shrink(self) -> None:
        responses = [
            _FakeResponse(
                400,
                text="This model's maximum context length is 4096 tokens.",
            ),
            _FakeResponse(200, _openai_batch_payload("A", "B")),
            _FakeResponse(200, _openai_batch_payload("C", "D")),
        ]
        pairs, _ = self._run_batch(responses, ["A", "B", "C", "D"])
        self.assertEqual(len(pairs), 4)

    def test_success_batch_has_no_retries(self) -> None:
        responses = [_FakeResponse(200, _openai_batch_payload("A", "B"))]
        pairs, mock_post = self._run_batch(responses, ["A", "B"])
        self.assertEqual(len(pairs), 2)
        self.assertEqual(mock_post.call_count, 1)

    def test_single_unit_context_error_is_fatal(self) -> None:
        responses = [_FakeResponse(400, text="context_length_exceeded")] * 4
        units = ["A"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "openai_compatible",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                        "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                        "OPENAI_COMPATIBLE_MODEL": "llama-test",
                    },
                ),
                patch.object(
                    logic.requests, "post", side_effect=responses
                ) as mock_post,
            ):
                with self.assertRaises(ProviderRequestError) as ctx:
                    logic.translate_markdown_sentence_batch_with_ai(
                        units, "English", "German"
                    )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(mock_post.call_count, 1)

    def test_non_context_400_is_not_retried(self) -> None:
        responses = [_FakeResponse(400, text="invalid_request_error")] * 4
        units = ["A", "B"]
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "openai_compatible",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                        "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                        "OPENAI_COMPATIBLE_MODEL": "llama-test",
                    },
                ),
                patch.object(
                    logic.requests, "post", side_effect=responses
                ) as mock_post,
            ):
                with self.assertRaises(ProviderRequestError) as ctx:
                    logic.translate_markdown_sentence_batch_with_ai(
                        units, "English", "German"
                    )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(mock_post.call_count, 1)


class TestTranslateWithRetry(unittest.TestCase):
    def setUp(self) -> None:
        self.patcher = patch.object(logic.time, "sleep")
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_translate_retries_transient_failure(self) -> None:
        responses = [
            _FakeResponse(503, text="server_error"),
            _FakeResponse(200, _openai_ok_payload()),
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "openai_compatible",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                        "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                        "OPENAI_COMPATIBLE_MODEL": "llama-test",
                    },
                ),
                patch.object(
                    logic.requests, "post", side_effect=responses
                ) as mock_post,
            ):
                translated = logic.translate_markdown_with_ai(
                    "# Title\n\nHello **world**.", "English", "German"
                )
        self.assertEqual(translated, "# Titel\n\nHallo **Welt**.")
        self.assertEqual(mock_post.call_count, 2)

    def test_translate_reports_503_after_retries(self) -> None:
        responses = [_FakeResponse(503, text="server_error")] * 3
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "openai_compatible",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                        "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                        "OPENAI_COMPATIBLE_MODEL": "llama-test",
                    },
                ),
                patch.object(logic.requests, "post", side_effect=responses),
            ):
                with self.assertRaises(ProviderRequestError) as ctx:
                    logic.translate_markdown_with_ai(
                        "# Title\n\nHello **world**.", "English", "German"
                    )
        self.assertEqual(ctx.exception.status_code, 503)


class TestTranslateRouterStatus(unittest.TestCase):
    def test_transient_failure_returns_503(self) -> None:
        app = FastAPI()
        app.include_router(ai_router.router)

        class _LogicStub:
            TranslationConfigError = logic.TranslationConfigError
            ProviderRequestError = ProviderRequestError

            def translate_markdown_with_ai(self, *args, **kwargs):
                raise ProviderRequestError(
                    503,
                    "The AI provider is temporarily unavailable. "
                    "Please try again shortly.",
                )

        with patch.object(ai_router, "_logic", return_value=_LogicStub()):
            client = TestClient(app)
            response = client.post(
                "/translate",
                json={
                    "content": "Hello",
                    "source_language": "English",
                    "target_language": "German",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertIn("try again shortly", response.json()["detail"])

    def test_quota_failure_returns_429(self) -> None:
        app = FastAPI()
        app.include_router(ai_router.router)

        class _LogicStub:
            TranslationConfigError = logic.TranslationConfigError
            ProviderRequestError = ProviderRequestError

            def translate_markdown_with_ai(self, *args, **kwargs):
                raise ProviderRequestError(
                    429,
                    "The AI provider reported an exceeded quota. "
                    "Please check the account and try again.",
                )

        with patch.object(ai_router, "_logic", return_value=_LogicStub()):
            client = TestClient(app)
            response = client.post(
                "/translate",
                json={
                    "content": "Hello",
                    "source_language": "English",
                    "target_language": "German",
                },
            )
        self.assertEqual(response.status_code, 429)
        self.assertIn("quota", response.json()["detail"])

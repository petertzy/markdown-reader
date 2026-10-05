"""Regression tests for GET /api/ai/models/{provider} credential resolution.

``backend/routers/ai.py`` resolved the API key with
``ai_logic.get_secure_ai_api_key()``, which reads the OS keyring and nothing
else.  Every other AI request goes through
``ai_logic._get_ai_api_key_for_provider()``, which is environment-first::

    api_key = os.getenv(env_var, "").strip() or get_secure_ai_api_key(key_slot).strip()

So with the key supplied through the environment -- loaded by the
``load_dotenv()`` call in ``backend/main.py`` -- and a keyring backend that is
installed but holds no credential, the model dropdown sent no ``Authorization``
header, the provider answered 401, and the bare ``except Exception`` answered
with the hard-coded default model list instead.

These tests drive a real loopback HTTP server so the assertions are about what
the provider actually received, and they cover the keyring-present case that
the existing suite never exercises (it pins ``keyring`` to ``None``, the one
configuration in which the defect cannot show).
"""

import json
import os
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend import ai_logic as logic
from backend.routers import ai as ai_router

# Providers whose key the endpoint is expected to resolve from the environment.
AI_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_NAVIDIA_API_KEY",
    "OPENAI_COMPATIBLE_GROQ_API_KEY",
)


class _RecordingHandler(BaseHTTPRequestHandler):
    """Answers ``/models`` like a real provider: 401 unless authorised."""

    #: ``[(path, authorization_header_or_None), ...]`` for the whole run.
    seen: list[tuple[str, str | None]] = []

    def do_GET(self):  # noqa: N802 - name mandated by BaseHTTPRequestHandler
        authorization = self.headers.get("Authorization")
        type(self).seen.append((self.path, authorization))
        if authorization:
            body = json.dumps({"data": [{"id": "live-model-1"}]}).encode()
            status = 200
        else:
            body = json.dumps({"error": "missing Authorization"}).encode()
            status = 401
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class _EmptyKeyring:
    """A keyring backend that is installed but holds nothing for this service."""

    def get_password(self, service, username):
        return None

    def set_password(self, service, username, password):
        raise AssertionError("the endpoint must not write to the keyring")


class _StubKeyring:
    def __init__(self, password):
        store = {"*": password} if isinstance(password, str) else password
        self._store = store

    def get_password(self, service, username):
        return self._store.get(username, self._store.get("*"))

    def set_password(self, service, username, password):
        raise AssertionError("the endpoint must not write to the keyring")


@contextmanager
def _provider_state(keyring, env=None):
    """Point the AI settings at a throwaway file and a scripted keyring."""
    with TemporaryDirectory() as tmp_dir:
        base_urls = dict(logic.AI_PROVIDER_BASE_URLS)
        base_urls["openai"] = f"http://127.0.0.1:{_server_port}/v1"
        scrubbed = {name: "" for name in AI_KEY_ENV_VARS}
        scrubbed.update(env or {})
        with (
            patch.object(logic, "APP_SETTINGS_FILE_PATH", Path(tmp_dir) / "s.json"),
            patch.object(logic, "keyring", keyring),
            patch.object(logic, "AI_PROVIDER_BASE_URLS", base_urls),
            patch.dict(os.environ, scrubbed),
        ):
            yield


def _setUpServer():
    global _server, _server_port
    _server = HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    _server_port = _server.server_address[1]
    threading.Thread(target=_server.serve_forever, daemon=True).start()


def _tearDownServer():
    _server.shutdown()
    _server.server_close()


class TestAIModelsEndpointCredentialResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _setUpServer()

    @classmethod
    def tearDownClass(cls):
        _tearDownServer()

    def setUp(self):
        _RecordingHandler.seen = []

    @property
    def sent_headers(self):
        return _RecordingHandler.seen

    def test_env_api_key_authorises_the_models_request(self):
        with _provider_state(_EmptyKeyring(), {"OPENAI_API_KEY": "env-key"}):
            result = ai_router.get_models("openai")

        self.assertEqual(
            self.sent_headers,
            [("/v1/models", "Bearer env-key")],
            "the provider must receive the environment-supplied key",
        )
        self.assertEqual(result["models"], ["live-model-1"])
        self.assertNotEqual(
            result["models"],
            logic.get_provider_default_models("openai"),
            "a live answer must not be confused with the hard-coded fallback",
        )

    def test_env_api_key_outranks_the_keyring_copy(self):
        with _provider_state(
            _StubKeyring("keyring-key"), {"OPENAI_API_KEY": "env-key"}
        ):
            ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", "Bearer env-key")])

    def test_keyring_api_key_is_used_when_no_env_var_is_set(self):
        with _provider_state(_StubKeyring("keyring-key")):
            result = ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", "Bearer keyring-key")])
        self.assertEqual(result["models"], ["live-model-1"])

    def test_without_any_credential_the_provider_is_asked_without_a_header(self):
        with _provider_state(_EmptyKeyring()):
            result = ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", None)])
        self.assertEqual(result["models"], logic.get_provider_default_models("openai"))

    def test_base_url_override_selects_that_endpoints_env_var(self):
        groq_url = f"http://127.0.0.1:{_server_port}/groq/v1"
        options = [{"key": "groq", "label": "Groq", "url": groq_url}]
        with (
            _provider_state(
                _EmptyKeyring(), {"OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-env-key"}
            ),
            patch.object(
                logic, "get_openai_compatible_base_url_options", return_value=options
            ),
        ):
            result = ai_router.get_models(
                "openai_compatible", base_url_override=groq_url
            )

        self.assertEqual(
            self.sent_headers,
            [("/groq/v1/models", "Bearer groq-env-key")],
            "the override must select the credential of the endpoint it names",
        )
        self.assertEqual(result["models"], ["live-model-1"])

    def test_env_api_key_is_stripped_before_being_sent(self):
        with _provider_state(_EmptyKeyring(), {"OPENAI_API_KEY": "  env-key \n"}):
            ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", "Bearer env-key")])

    def test_keyring_api_key_is_stripped_before_being_sent(self):
        with _provider_state(_StubKeyring("  keyring-key \n")):
            ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", "Bearer keyring-key")])

    def test_base_url_override_reads_the_keyring_slot_it_selects(self):
        # The settings UI saves an openai_compatible key under the slot name for
        # the chosen base URL, so the keyring lookup must follow key_slot.
        groq_url = f"http://127.0.0.1:{_server_port}/groq/v1"
        options = [{"key": "groq", "label": "Groq", "url": groq_url}]
        keyring = _StubKeyring(
            {
                "openai_compatible": "generic-slot-key",
                "openai_compatible_groq": "groq-slot-key",
            }
        )
        with (
            _provider_state(keyring),
            patch.object(
                logic, "get_openai_compatible_base_url_options", return_value=options
            ),
        ):
            result = ai_router.get_models(
                "openai_compatible", base_url_override=groq_url
            )

        self.assertEqual(
            self.sent_headers, [("/groq/v1/models", "Bearer groq-slot-key")]
        )
        self.assertEqual(result["models"], ["live-model-1"])

    def test_local_provider_is_exempt_from_credentials(self):
        with _provider_state(_EmptyKeyring(), {"LOCAL_AI_API_KEY": "env-key"}):
            result = ai_router.get_models(
                "local", base_url_override=f"http://127.0.0.1:{_server_port}/v1"
            )

        self.assertEqual(self.sent_headers, [("/v1/models", None)])
        self.assertEqual(result["models"], [])
        self.assertIn("not reachable", result["message"])

    def test_generic_openai_compatible_env_var_is_the_fallback(self):
        # `_get_ai_api_key_for_provider` falls back to the provider-wide slot when
        # the slot for the chosen base URL holds nothing. Without the same
        # fallback here, a key in OPENAI_COMPATIBLE_API_KEY authenticated every
        # AI request while this endpoint still reported the fallback model list.
        with (
            _provider_state(
                _EmptyKeyring(), {"OPENAI_COMPATIBLE_API_KEY": "generic-key"}
            ),
            patch.object(
                logic,
                "get_openai_compatible_base_url",
                return_value=f"http://127.0.0.1:{_server_port}/v1",
            ),
        ):
            result = ai_router.get_models("openai_compatible")

        self.assertEqual(self.sent_headers, [("/v1/models", "Bearer generic-key")])
        self.assertEqual(result["models"], ["live-model-1"])

    def test_the_openai_compatible_fallback_does_not_reach_other_providers(self):
        # The fallback is scoped to openai_compatible; an unrelated provider must
        # not pick up a credential meant for it.
        with _provider_state(
            _EmptyKeyring(), {"OPENAI_COMPATIBLE_API_KEY": "generic-key"}
        ):
            result = ai_router.get_models("openai")

        self.assertEqual(self.sent_headers, [("/v1/models", None)])
        self.assertEqual(result["models"], logic.get_provider_default_models("openai"))

    def test_the_key_sent_here_is_the_one_the_ai_requests_would_use(self):
        # The defect was two call sites resolving a key slot differently. Compare
        # the header this endpoint sends with the key the AI request path
        # resolves for the same provider, so the two cannot drift apart again.
        with _provider_state(_EmptyKeyring(), {"OPENAI_API_KEY": "env-key"}):
            ai_router.get_models("openai")
            request_key, key_slot, _ = logic._get_ai_api_key_for_provider("openai")

        self.assertEqual(
            request_key, "env-key", "guard: the comparison must not be vacuous"
        )
        self.assertEqual(key_slot, "openai")
        self.assertEqual(self.sent_headers, [("/v1/models", f"Bearer {request_key}")])

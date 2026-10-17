import os
import tempfile
import threading
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import ai_logic as logic
from backend.routers import ai as ai_router

KEY_SLOTS = (
    "local",
    "openai_compatible_nvidia",
    "openai_compatible_groq",
    "openrouter",
    "openai",
    "anthropic",
)


class _MemoryKeyring:
    def __init__(self):
        self.credentials = {}
        self.reads = []
        self.unavailable = set()

    def get_password(self, service, slot):
        self.reads.append(slot)
        if slot in self.unavailable:
            raise logic.KeyringError("Synthetic credential-store failure")
        return self.credentials.get(slot)

    def set_password(self, service, slot, password):
        self.credentials[slot] = password

    def delete_password(self, service, slot):
        self.credentials.pop(slot, None)


class TestAISettingsAPIKeyStatus(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.enterContext(
            patch.object(
                logic, "APP_SETTINGS_FILE_PATH", Path(temporary.name) / "settings.json"
            )
        )
        environment = {logic._get_key_slot_env_var(slot): "" for slot in KEY_SLOTS}
        environment.update(
            OPENAI_COMPATIBLE_API_KEY="",
            OPENAI_COMPATIBLE_BASE_URL_CHOICE="",
            OPENAI_COMPATIBLE_BASE_URL="",
            AI_PROVIDER="",
        )
        self.enterContext(patch.dict(os.environ, environment))
        self.keyring = _MemoryKeyring()
        self.enterContext(patch.object(logic, "keyring", self.keyring))
        app = FastAPI()
        app.include_router(ai_router.router, prefix="/api/ai")
        self.client = self.enterContext(TestClient(app))

    def settings(self):
        response = self.client.get("/api/ai/settings")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def save_key(self, provider):
        response = self.client.post(
            "/api/ai/settings/apikey",
            json={"provider": provider, "api_key": "synthetic-keyring-value"},
        )
        self.assertEqual(response.status_code, 200)

    def delete_key(self, slot):
        response = self.client.delete(f"/api/ai/settings/apikey/{slot}")
        self.assertEqual(response.status_code, 200)

    def test_empty_store_reports_absence_and_checks_each_action_slot_once(self):
        settings = self.settings()

        self.assertEqual(
            settings.get("api_key_statuses"),
            dict.fromkeys(KEY_SLOTS, "not_saved"),
        )
        self.assertEqual(Counter(self.keyring.reads), Counter(KEY_SLOTS))

    def test_save_and_idempotent_delete_are_reflected_by_settings(self):
        self.save_key("openai")
        settings = self.settings()
        self.assertEqual(settings["api_key_statuses"]["openai"], "saved")
        self.assertTrue(settings["providers"]["openai"]["key_configured"])
        self.assertNotIn("synthetic-keyring-value", str(settings))

        self.delete_key("openai")
        self.delete_key("openai")
        settings = self.settings()
        self.assertEqual(settings["api_key_statuses"]["openai"], "not_saved")
        self.assertFalse(settings["providers"]["openai"]["key_configured"])

    def test_environment_configuration_does_not_claim_a_saved_key(self):
        os.environ["OPENAI_API_KEY"] = "synthetic-environment-value"

        settings = self.settings()

        self.assertEqual(settings["api_key_statuses"]["openai"], "not_saved")
        self.assertTrue(settings["providers"]["openai"]["key_configured"])
        self.assertEqual(self.keyring.reads.count("openai"), 1)

    def test_deleting_saved_key_preserves_environment_authentication(self):
        os.environ["OPENAI_API_KEY"] = "synthetic-environment-value"
        self.save_key("openai")
        self.assertEqual(self.settings()["api_key_statuses"]["openai"], "saved")

        self.delete_key("openai")
        settings = self.settings()

        self.assertEqual(settings["api_key_statuses"]["openai"], "not_saved")
        self.assertTrue(settings["providers"]["openai"]["key_configured"])
        self.assertEqual(
            logic.resolve_ai_api_key_for_slot("openai"), "synthetic-environment-value"
        )

    def test_compatible_endpoints_have_independent_status_and_deletion(self):
        self.save_key("openai_compatible")
        self.client.post(
            "/api/ai/settings/openai-compatible/base-url-choice",
            json={"choice_key": "groq"},
        )
        settings = self.settings()
        self.assertEqual(
            settings["api_key_statuses"]["openai_compatible_nvidia"], "saved"
        )
        self.assertEqual(
            settings["api_key_statuses"]["openai_compatible_groq"], "not_saved"
        )

        self.save_key("openai_compatible")
        self.delete_key("openai_compatible_groq")
        settings = self.settings()

        self.assertEqual(
            settings["api_key_statuses"]["openai_compatible_nvidia"], "saved"
        )
        self.assertEqual(
            settings["api_key_statuses"]["openai_compatible_groq"], "not_saved"
        )

    def test_local_optional_key_remains_saveable_and_deletable(self):
        self.save_key("local")
        self.assertEqual(self.settings()["api_key_statuses"]["local"], "saved")
        self.delete_key("local")
        self.assertEqual(self.settings()["api_key_statuses"]["local"], "not_saved")

    def test_without_keyring_environment_fallback_remains_clearable(self):
        with patch.object(logic, "keyring", None):
            self.save_key("openai")
            self.assertEqual(
                self.settings()["api_key_statuses"]["openai"], "environment"
            )
            self.delete_key("openai")
            self.assertEqual(self.settings()["api_key_statuses"]["openai"], "not_saved")

    def test_readback_reflects_environment_restored_from_existing_settings(self):
        logic._save_app_settings({"OPENAI_API_KEY": "synthetic-existing-setting"})
        with patch.object(logic, "keyring", None):
            self.assertEqual(
                self.settings()["api_key_statuses"]["openai"], "environment"
            )
            self.delete_key("openai")
            self.assertEqual(
                self.settings()["api_key_statuses"]["openai"], "environment"
            )

    def test_a_keyring_error_does_not_report_absence_or_mask_other_slots(self):
        self.keyring.unavailable.add("openai")
        self.keyring.credentials["anthropic"] = "synthetic-keyring-value"

        settings = self.settings()

        self.assertEqual(settings["api_key_statuses"]["openai"], "unavailable")
        self.assertEqual(settings["api_key_statuses"]["anthropic"], "saved")
        self.assertEqual(Counter(self.keyring.reads), Counter(KEY_SLOTS))

    def test_storage_probe_timeout_reports_unknown_with_a_bounded_wait(self):
        release = threading.Event()
        finished = threading.Event()

        class _BlockedKeyring:
            def get_password(self, service, slot):
                try:
                    release.wait(2)
                    return "synthetic-keyring-value"
                finally:
                    finished.set()

        started = time.monotonic()
        try:
            with patch.object(logic, "keyring", _BlockedKeyring()):
                status = logic.get_ai_api_key_storage_status(
                    "openai", timeout_seconds=0.01
                )
            self.assertEqual(status, "unavailable")
            self.assertLess(time.monotonic() - started, 0.5)
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

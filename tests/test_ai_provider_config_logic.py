import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import ai_logic as logic


class TestAIProviderConfigLogic(unittest.TestCase):
    def test_openai_compatible_env_and_display_name(self):
        self.assertEqual(
            logic.get_ai_provider_env_var("openai_compatible"),
            "OPENAI_COMPATIBLE_API_KEY",
        )
        self.assertEqual(
            logic.get_ai_provider_display_name("openai_compatible"),
            "OpenAI Compatible",
        )

    def test_provider_fallback_priority_places_openai_compatible_before_openrouter(
        self,
    ):
        order = logic._build_provider_order("openai")
        self.assertEqual(order[0], "openai")
        self.assertLess(order.index("openai_compatible"), order.index("openrouter"))

    def test_openai_compatible_base_url_choice_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(
                    os.environ,
                    {
                        "OPENAI_COMPATIBLE_BASE_URL": "",
                        "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "",
                    },
                    clear=False,
                ),
            ):
                selected = logic.set_openai_compatible_base_url_choice("groq")
                self.assertEqual(selected, "groq")
                self.assertEqual(
                    os.environ.get("OPENAI_COMPATIBLE_BASE_URL_CHOICE"), "groq"
                )
                self.assertEqual(
                    os.environ.get("OPENAI_COMPATIBLE_BASE_URL"),
                    "https://api.groq.com/openai/v1",
                )

                self.assertEqual(logic.get_openai_compatible_base_url_choice(), "groq")
                self.assertEqual(
                    logic.get_openai_compatible_base_url(),
                    "https://api.groq.com/openai/v1",
                )

    def test_fetch_models_uses_base_url_override(self):
        class _DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "override-model"}]}

        with patch(
            "backend.ai_logic.requests.get", return_value=_DummyResp()
        ) as mock_get:
            models = logic.fetch_available_models(
                "openai_compatible",
                "dummy-key",
                base_url_override="https://api.groq.com/openai/v1",
            )

        called_url = mock_get.call_args[0][0]
        self.assertEqual(called_url, "https://api.groq.com/openai/v1/models")
        self.assertIn("override-model", models)

    def test_openai_compatible_default_models_depend_on_base_url(self):
        navidia_defaults = logic.get_provider_default_models(
            "openai_compatible",
            base_url_override="https://integrate.api.nvidia.com/v1",
        )
        groq_defaults = logic.get_provider_default_models(
            "openai_compatible",
            base_url_override="https://api.groq.com/openai/v1",
        )

        self.assertNotEqual(navidia_defaults, groq_defaults)
        self.assertTrue(len(navidia_defaults) > 0)
        self.assertIn("llama-3.3-70b-versatile", groq_defaults)

    def test_openai_compatible_slot_uses_choice_specific_env_without_keyring(self):
        with (
            patch.object(logic, "keyring", None),
            patch.dict(
                os.environ,
                {
                    "OPENAI_COMPATIBLE_BASE_URL_CHOICE": "groq",
                    "OPENAI_COMPATIBLE_GROQ_API_KEY": "groq-key",
                    "OPENAI_COMPATIBLE_API_KEY": "",
                },
                clear=False,
            ),
        ):
            api_key, key_slot, env_var = logic._get_ai_api_key_for_provider(
                "openai_compatible"
            )

        self.assertEqual(api_key, "groq-key")
        self.assertEqual(key_slot, "openai_compatible_groq")
        self.assertEqual(env_var, "OPENAI_COMPATIBLE_GROQ_API_KEY")

    def test_provider_and_model_are_persisted_to_settings(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(os.environ, {"AI_PROVIDER": "", "OPENAI_MODEL": ""}),
            ):
                logic.set_current_ai_provider("openai")
                logic.set_ai_provider_model("openai", "gpt-test")

                self.assertEqual(logic._get_current_ai_provider(), "openai")
                self.assertEqual(logic.get_ai_provider_model("openai"), "gpt-test")

    def test_persisted_provider_takes_precedence_over_stale_env_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(os.environ, {"AI_PROVIDER": "openrouter"}, clear=False),
            ):
                logic._save_app_settings({"ai_provider": "openai"})

                self.assertEqual(logic._get_current_ai_provider(), "openai")

    def test_translate_uses_configured_openai_compatible_provider(self):
        class _DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [{"message": {"content": "# Titel\n\nHallo **Welt**."}}]
                }

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
                patch(
                    "backend.ai_logic.requests.post", return_value=_DummyResp()
                ) as mock_post,
            ):
                translated = logic.translate_markdown_with_ai(
                    "# Title\n\nHello **world**.", "English", "German"
                )

        called_url = mock_post.call_args[0][0]
        called_json = mock_post.call_args.kwargs["json"]
        called_headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(called_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(called_json["model"], "llama-test")
        self.assertEqual(called_headers["Authorization"], "Bearer groq-key")
        self.assertEqual(translated, "# Titel\n\nHallo **Welt**.")


if __name__ == "__main__":
    unittest.main()

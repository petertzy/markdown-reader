import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import ai_logic as logic
from backend.routers import ai as ai_router


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

    def test_local_provider_defaults_to_lm_studio_base_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(os.environ, {"LOCAL_AI_BASE_URL": ""}, clear=False),
            ):
                self.assertEqual(
                    logic.get_local_ai_base_url(), "http://127.0.0.1:1234/v1"
                )

                saved = logic.set_local_ai_base_url("http://127.0.0.1:1234/v1/")

                self.assertEqual(saved, "http://127.0.0.1:1234/v1")
                self.assertEqual(
                    logic.get_local_ai_base_url(), "http://127.0.0.1:1234/v1"
                )
                self.assertEqual(logic.get_provider_default_models("local"), [])

    def test_local_provider_base_url_choice_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(os.environ, {"LOCAL_AI_BASE_URL": ""}, clear=False),
            ):
                options = logic.get_local_ai_base_url_options()
                option_keys = {item["key"] for item in options}

                self.assertIn("lm_studio", option_keys)
                self.assertIn("ollama", option_keys)
                self.assertIn("custom", option_keys)
                self.assertEqual(logic.get_local_ai_base_url_choice(), "lm_studio")

                choice = logic.set_local_ai_base_url_choice("ollama")

                self.assertEqual(choice, "ollama")
                self.assertEqual(logic.get_local_ai_base_url_choice(), "ollama")
                self.assertEqual(
                    logic.get_local_ai_base_url(), "http://127.0.0.1:11434/v1"
                )

    def test_local_provider_choice_overrides_stale_env_base_url(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(
                    os.environ,
                    {"LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1"},
                    clear=False,
                ),
            ):
                logic._save_app_settings({"local_ai_base_url_choice": "ollama"})

                self.assertEqual(
                    logic.get_local_ai_base_url(), "http://127.0.0.1:11434/v1"
                )

    def test_local_provider_custom_base_url_choice_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(os.environ, {"LOCAL_AI_BASE_URL": ""}, clear=False),
            ):
                choice = logic.set_local_ai_base_url_choice(
                    "custom", custom_base_url="http://localhost:9999/v1/"
                )

                self.assertEqual(choice, "custom")
                self.assertEqual(logic.get_local_ai_base_url_choice(), "custom")
                self.assertEqual(
                    logic.get_local_ai_custom_base_url(), "http://localhost:9999/v1"
                )
                self.assertEqual(
                    logic.get_local_ai_base_url(), "http://localhost:9999/v1"
                )

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

    def test_fetch_models_uses_local_base_url_without_api_key(self):
        class _DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "local-model"}]}

        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.dict(
                    os.environ,
                    {"LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1"},
                    clear=False,
                ),
                patch(
                    "backend.ai_logic.requests.get", return_value=_DummyResp()
                ) as mock_get,
            ):
                models = logic.fetch_available_models("local", "")

        called_url = mock_get.call_args[0][0]
        called_headers = mock_get.call_args.kwargs["headers"]
        self.assertEqual(called_url, "http://127.0.0.1:1234/v1/models")
        self.assertEqual(called_headers, {})
        self.assertIn("local-model", models)

    def test_fetch_models_falls_back_to_ollama_tags_endpoint(self):
        class _OpenAICompatResp:
            def raise_for_status(self):
                raise logic.requests.HTTPError("not found")

            def json(self):
                return {}

        class _OllamaTagsResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"models": [{"name": "llama3.2:latest"}]}

        with patch(
            "backend.ai_logic.requests.get",
            side_effect=[_OpenAICompatResp(), _OllamaTagsResp()],
        ) as mock_get:
            models = logic.fetch_available_models(
                "local", "", base_url_override="http://127.0.0.1:11434/v1"
            )

        called_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertEqual(
            called_urls,
            [
                "http://127.0.0.1:11434/v1/models",
                "http://127.0.0.1:11434/api/tags",
            ],
        )
        self.assertEqual(models, ["llama3.2:latest"])

    def test_local_models_endpoint_returns_empty_list_when_unreachable(self):
        with patch(
            "backend.ai_logic.fetch_available_models",
            side_effect=RuntimeError("connection refused"),
        ):
            result = ai_router.get_models(
                "local", base_url_override="http://127.0.0.1:11434/v1"
            )

        self.assertEqual(result["provider"], "local")
        self.assertEqual(result["models"], [])
        self.assertIn("not reachable", result["message"])

    def test_local_models_endpoint_does_not_read_api_key(self):
        with (
            patch("backend.ai_logic.get_secure_ai_api_key") as mock_get_key,
            patch(
                "backend.ai_logic.fetch_available_models",
                return_value=["llama3.2:latest"],
            ) as mock_fetch_models,
        ):
            result = ai_router.get_models(
                "local", base_url_override="http://127.0.0.1:11434/v1"
            )

        mock_get_key.assert_not_called()
        mock_fetch_models.assert_called_once_with(
            "local", "", base_url_override="http://127.0.0.1:11434/v1"
        )
        self.assertEqual(result["models"], ["llama3.2:latest"])

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

    def test_key_configured_check_times_out_when_keyring_hangs(self):
        class _HangingKeyring:
            def get_password(self, service, provider):
                time.sleep(1)
                return "secret"

        started = time.monotonic()
        with (
            patch.object(logic, "keyring", _HangingKeyring()),
            patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False),
        ):
            configured = logic.is_ai_api_key_configured(
                "openai", "OPENAI_API_KEY", timeout_seconds=0.01
            )

        self.assertFalse(configured)
        self.assertLess(time.monotonic() - started, 0.5)

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

    def test_translate_uses_local_provider_without_api_key(self):
        class _DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Hallo"}}]}

        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "",
                        "LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1",
                        "LOCAL_AI_MODEL": "local-test",
                        "LOCAL_AI_API_KEY": "",
                    },
                ),
                patch(
                    "backend.ai_logic.requests.post", return_value=_DummyResp()
                ) as mock_post,
            ):
                logic._save_app_settings({"ai_provider": "local"})
                translated = logic.translate_markdown_with_ai(
                    "Hello", "English", "German"
                )

        called_url = mock_post.call_args[0][0]
        called_json = mock_post.call_args.kwargs["json"]
        called_headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(called_url, "http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(called_json["model"], "local-test")
        self.assertNotIn("Authorization", called_headers)
        self.assertEqual(translated, "Hallo")

    def test_chat_uses_configured_provider_for_general_messages(self):
        class _DummyResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "choices": [
                        {"message": {"content": "I am Markdown Reader's assistant."}}
                    ]
                }

        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "",
                        "LOCAL_AI_BASE_URL": "http://127.0.0.1:1234/v1",
                        "LOCAL_AI_MODEL": "local-test",
                        "LOCAL_AI_API_KEY": "",
                    },
                ),
                patch(
                    "backend.ai_logic.requests.post", return_value=_DummyResp()
                ) as mock_post,
            ):
                logic._save_app_settings({"ai_provider": "local"})
                result = logic.request_ai_agent_response(
                    "Could you please introduce yourself in detail?"
                )

        called_url = mock_post.call_args[0][0]
        called_json = mock_post.call_args.kwargs["json"]
        called_headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(called_url, "http://127.0.0.1:1234/v1/chat/completions")
        self.assertEqual(called_json["model"], "local-test")
        self.assertNotIn("Authorization", called_headers)
        self.assertEqual(
            result["assistant_message"], "I am Markdown Reader's assistant."
        )
        self.assertEqual(result["proposed_action"]["type"], "none")
        self.assertEqual(result["used_provider"], "local")

    def test_chat_requires_api_key_for_remote_provider(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(os.environ, {"AI_PROVIDER": "", "OPENAI_API_KEY": ""}),
            ):
                logic._save_app_settings({"ai_provider": "openai"})
                with self.assertRaises(logic.TranslationConfigError) as err:
                    logic.request_ai_agent_response("Hello")

        self.assertIn("AI chat requires", str(err.exception))
        self.assertEqual(err.exception.provider_name, "openai")
        self.assertEqual(err.exception.env_var, "OPENAI_API_KEY")

    def test_chat_uses_first_local_model_when_none_is_saved(self):
        class _ModelsResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "local-auto-model"}]}

        class _ChatResp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "Hello from local."}}]}

        with tempfile.TemporaryDirectory() as tmp_dir:
            settings_file = Path(tmp_dir) / "settings.json"
            with (
                patch.object(logic, "APP_SETTINGS_FILE_PATH", settings_file),
                patch.object(logic, "keyring", None),
                patch.dict(
                    os.environ,
                    {
                        "AI_PROVIDER": "",
                        "LOCAL_AI_BASE_URL": "http://127.0.0.1:14567/v1",
                        "LOCAL_AI_MODEL": "",
                        "LOCAL_AI_API_KEY": "",
                    },
                ),
                patch(
                    "backend.ai_logic.requests.get", return_value=_ModelsResp()
                ) as mock_get,
                patch(
                    "backend.ai_logic.requests.post", return_value=_ChatResp()
                ) as mock_post,
            ):
                logic._save_app_settings(
                    {
                        "ai_provider": "local",
                        "local_ai_base_url_choice": "custom",
                        "local_ai_custom_base_url": "http://127.0.0.1:14567/v1",
                    }
                )
                result = logic.request_ai_agent_response("Hello")

        self.assertEqual(mock_get.call_args[0][0], "http://127.0.0.1:14567/v1/models")
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["model"], "local-auto-model"
        )
        self.assertEqual(result["assistant_message"], "Hello from local.")


if __name__ == "__main__":
    unittest.main()

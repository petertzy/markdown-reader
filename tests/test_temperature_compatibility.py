import unittest

from backend import ai_logic as logic


class TestTemperatureCompatibility(unittest.TestCase):
    def test_supported_models_keep_default_temperature(self):
        self.assertEqual(logic._temperature_for_model("gpt-4o", 0.2), 0.2)
        self.assertEqual(logic._temperature_for_model("gpt-4o-mini", 0.4), 0.4)
        self.assertEqual(logic._temperature_for_model("llama-3.3-70b-versatile", 0.1), 0.1)

    def test_reasoning_and_newer_models_omit_temperature(self):
        self.assertIsNone(logic._temperature_for_model("o1-preview", 0.2))
        self.assertIsNone(logic._temperature_for_model("o1-mini", 0.2))
        self.assertIsNone(logic._temperature_for_model("o3-mini", 0.3))
        self.assertIsNone(logic._temperature_for_model("gpt-5.6", 0.2))
        self.assertIsNone(logic._temperature_for_model("openai/gpt-5", 0.2))

    def test_empty_or_invalid_model_falls_back(self):
        self.assertEqual(logic._temperature_for_model("", 0.2), 0.2)
        self.assertEqual(logic._temperature_for_model(None, 0.2), 0.2)


if __name__ == "__main__":
    unittest.main()

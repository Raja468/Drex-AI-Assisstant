import unittest

from brain.ai_router import AIRouter


class TestAIRouterStatus(unittest.TestCase):

    def test_get_status_returns_provider_details(self):
        status = AIRouter().get_status()

        self.assertIsInstance(status, dict)
        self.assertIn("providers", status)
        self.assertIn("default", status)
        self.assertIn("available_count", status)
        self.assertIn("primary", status)

        providers = status["providers"]
        self.assertIsInstance(providers, dict)
        for provider in ("gemini", "groq", "openrouter"):
            self.assertIn(provider, providers)
            self.assertIsInstance(providers[provider], dict)
            self.assertIn("available", providers[provider])
            self.assertIn("configured", providers[provider])
            self.assertIn("model", providers[provider])

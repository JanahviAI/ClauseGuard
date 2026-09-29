import unittest
import os
import json
import tempfile
import sys

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from extraction.prefilter import PrivacyPrefilter
from extraction.llm_extractor import LLMExtractor
from extraction.validator import validate_extraction_output, ValidationError
from extract import extract_pipeline


class TestExtractionPipeline(unittest.TestCase):

    def setUp(self):
        # Save the current provider so tests can safely force mock mode
        # without permanently changing the environment.
        self.original_provider = os.environ.get("CLAUSEGUARD_LLM_PROVIDER")

    def tearDown(self):
        # Restore the provider that existed before the test.
        if self.original_provider is None:
            os.environ.pop("CLAUSEGUARD_LLM_PROVIDER", None)
        else:
            os.environ["CLAUSEGUARD_LLM_PROVIDER"] = self.original_provider

    def test_prefilter(self):
        prefilter = PrivacyPrefilter()
        raw = [
            "We share your location data with marketing partners.",  # Privacy relevant
            "Click here to reset your password."                    # Not privacy relevant
        ]

        filtered = prefilter.filter_candidates(raw)

        self.assertGreaterEqual(len(filtered), 1)
        self.assertTrue(any("location data" in clause for clause in filtered))

        scored = prefilter.score_candidates(raw)
        self.assertEqual(len(scored), 2)
        self.assertIn("privacy_probability", scored[0])
        self.assertIn("is_uncertain", scored[0])

    def test_mock_llm_extractor(self):
        # Explicitly force mock mode.
        # The .env file is configured for Ollama, so removing only
        # OPENAI_API_KEY is not enough to select the mock provider.
        os.environ["CLAUSEGUARD_LLM_PROVIDER"] = "mock"

        extractor = LLMExtractor("TestService", "TestCategory")
        candidates = [
            "We share your location data with marketing partners."
        ]

        result = extractor.extract(candidates)

        self.assertEqual(result["service_name"], "TestService")
        self.assertEqual(result["category"], "TestCategory")
        self.assertEqual(len(result["clauses"]), 1)

        clause = result["clauses"][0]

        self.assertEqual(clause["text"], candidates[0])
        self.assertIn("Location Data", clause["entities"])
        self.assertIsInstance(clause["severity_score"], float)
        self.assertIsInstance(clause["specificity_score"], float)
        self.assertIsInstance(clause["risk_category"], str)
        self.assertIn("recipients", clause)
        self.assertIn("entity_specificity", clause)
        self.assertIn("retention", clause)
        self.assertIn("purposes", clause)
        self.assertIn("confidence", clause)
        self.assertIn("evidence", clause)
        self.assertIn(clause["entity_specificity"], {"specific", "group", "vague"})
        self.assertIn("raw_text", clause["retention"])
        self.assertIn("duration_days", clause["retention"])

    def test_validator_success(self):
        valid_data = {
            "service_name": "Spotify",
            "category": "Streaming",
            "clauses": [
                {
                    "text": "We share your location.",
                    "entities": ["Location"],
                    "severity_score": 4.0,
                    "specificity_score": 2.5,
                    "risk_category": "Data Sharing",
                    "recipients": ["Advertising Partners"],
                    "entity_specificity": "specific",
                    "retention": {"raw_text": "30 days", "duration_days": 30},
                    "purposes": ["Advertising"],
                    "confidence": 0.8,
                    "evidence": "We share your location."
                }
            ]
        }

        self.assertTrue(validate_extraction_output(valid_data))

    def test_validator_failures(self):
        invalid_data = {
            "service_name": "Spotify"
            # missing clauses
        }

        with self.assertRaises(ValidationError):
            validate_extraction_output(invalid_data)

        invalid_data_2 = {
            "service_name": "Spotify",
            "clauses": [
                {
                    "text": "test",
                    "entities": ["test"],
                    "severity_score": "high"  # Invalid type
                }
            ]
        }

        with self.assertRaises(ValidationError):
            validate_extraction_output(invalid_data_2)

    def test_end_to_end_pipeline(self):
        # Explicitly force mock mode.
        os.environ["CLAUSEGUARD_LLM_PROVIDER"] = "mock"

        raw_text = (
            "Welcome to our app. "
            "We share your location data with marketing partners. "
            "Thanks for using our app."
        )

        result = extract_pipeline(
            raw_text,
            "EndToEnd",
            "Test"
        )

        self.assertEqual(result["service_name"], "EndToEnd")
        self.assertGreaterEqual(len(result["clauses"]), 1)
        self.assertTrue(any(
            "location data" in clause["text"]
            for clause in result["clauses"]
        ))


if __name__ == '__main__':
    unittest.main()

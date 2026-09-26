import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from config import get_model, get_provider
from extraction.llm_extractor import LLMExtractor
from extraction.validator import ValidationError, validate_extraction_output
from canonicalize import EntityCanonicalizer


class TestProductionPaths(unittest.TestCase):
    def setUp(self):
        self.old_provider = os.environ.get("CLAUSEGUARD_LLM_PROVIDER")
        self.old_model = os.environ.get("CLAUSEGUARD_LLM_MODEL")
        os.environ["CLAUSEGUARD_LLM_PROVIDER"] = "mock"
        os.environ.pop("CLAUSEGUARD_LLM_MODEL", None)

    def tearDown(self):
        if self.old_provider is None:
            os.environ.pop("CLAUSEGUARD_LLM_PROVIDER", None)
        else:
            os.environ["CLAUSEGUARD_LLM_PROVIDER"] = self.old_provider
        if self.old_model is None:
            os.environ.pop("CLAUSEGUARD_LLM_MODEL", None)
        else:
            os.environ["CLAUSEGUARD_LLM_MODEL"] = self.old_model

    def test_provider_defaults_to_mock_when_explicit(self):
        self.assertEqual(get_provider(), "mock")
        self.assertEqual(get_model(), "mock")

    def test_mock_output_has_provider_metadata(self):
        result = LLMExtractor("Demo", "Streaming").extract(
            ["We collect your location data."]
        )
        self.assertEqual(result["provider"], "mock")
        self.assertEqual(result["model"], "mock")

    def test_model_json_parser_accepts_markdown_fence(self):
        result = LLMExtractor._parse_model_json(
            '```json\n{"clauses": []}\n```'
        )
        self.assertEqual(result, {"clauses": []})

    def test_canonicalization_fuzzy_alias(self):
        c = EntityCanonicalizer()
        self.assertEqual(c.canonicalize("Location informtion"), "Location")
        self.assertEqual(c.canonicalize("email adress"), "Email")
        self.assertEqual(c.canonicalize("Google, LLC"), "Google")

    def test_unknown_entity_is_not_forced_into_known_alias(self):
        c = EntityCanonicalizer()
        self.assertEqual(c.canonicalize("Customer Loyalty Tier"), "Customer Loyalty Tier")

    def test_validation_rejects_out_of_range_scores(self):
        with self.assertRaises(ValidationError):
            validate_extraction_output({
                "service_name": "X",
                "clauses": [{
                    "text": "Collect data.",
                    "entities": ["Email"],
                    "severity_score": 6,
                    "specificity_score": 2,
                }],
            })


if __name__ == "__main__":
    unittest.main()

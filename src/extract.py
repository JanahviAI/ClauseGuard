import argparse
import json
import os
import re

try:
    from .extraction.prefilter import PrivacyPrefilter
    from .extraction.llm_extractor import LLMExtractor
    from .extraction.validator import validate_extraction_output
except ImportError:
    from extraction.prefilter import PrivacyPrefilter
    from extraction.llm_extractor import LLMExtractor
    from extraction.validator import validate_extraction_output


# Common privacy-policy headings that should not be sent to the LLM
HEADING_PATTERNS = [
    r"^your personal data rights and controls$",
    r"^personal data we collect about you$",
    r"^our purpose for using your personal data$",
    r"^sharing your personal data$",
    r"^data retention$",
    r"^keeping your personal data safe$",
    r"^third[- ]party links?$",
    r"^how we use your personal data$",
    r"^how we share your personal data$",
    r"^what personal data we collect$",
    r"^how we protect your personal data$",
    r"^your rights$",
    r"^your choices$",
    r"^contact us$",
    r"^changes to this policy$",
    r"^about this policy$",
]


def is_likely_heading(text):
    """Return True when a text fragment looks like a section heading."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return True

    lower = cleaned.lower().rstrip(":").strip()

    # Known privacy-policy headings.
    for pattern in HEADING_PATTERNS:
        if re.match(pattern, lower, flags=re.I):
            return True

    # Very short fragments without sentence punctuation are often headings.
    words = cleaned.split()

    if len(words) <= 4 and not re.search(r"[.!?;,:]$", cleaned):
        return True

    # Title-style fragments such as:
    # "Data Retention"
    # "Third-Party Links"
    # "Account Privacy"
    if (
        len(words) <= 8
        and not re.search(r"[.!?;]$", cleaned)
        and all(
            word[:1].isupper()
            for word in words
            if word and word[0].isalpha()
        )
    ):
        return True

    return False


def split_policy_into_clauses(raw_text):
    """Split policy prose while filtering obvious section headings."""
    if not raw_text or not raw_text.strip():
        return []

    normalized = re.sub(r"\r\n?", "\n", raw_text)
    normalized = re.sub(r"[ \t]+", " ", normalized)

    # Split on paragraph/newline boundaries and sentence boundaries.
    chunks = re.split(
        r"(?:\n{2,}|(?<=[.!?])\s+|(?<=;)\s+(?=[A-Z]))",
        normalized,
    )

    clauses = []

    for chunk in chunks:
        cleaned = chunk.strip(" \t\n•*-")

        if len(cleaned) <= 10:
            continue

        if is_likely_heading(cleaned):
            continue

        # Avoid fragments that are clearly navigation/UI text.
        if cleaned.lower() in {
            "privacy policy",
            "terms of use",
            "terms and conditions",
            "cookie policy",
            "legal",
            "help",
            "home",
            "menu",
        }:
            continue

        clauses.append(cleaned)

    return clauses


def extract_pipeline(raw_text, service_name, category=None):
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    if not service_name or not service_name.strip():
        raise ValueError("service_name must not be empty")

    raw_clauses = split_policy_into_clauses(raw_text)

    prefilter = PrivacyPrefilter()
    scored_clauses = prefilter.score_candidates(raw_clauses)
    candidate_clauses = [
        item["clause"]
        for item in scored_clauses
        if item["is_privacy"] or item["is_uncertain"]
    ]

    extractor = LLMExtractor(
        service_name=service_name.strip(),
        category=category,
    )

    extracted_json = extractor.extract(candidate_clauses)

    validate_extraction_output(extracted_json)

    return extracted_json


def process_file(input_path, service_name, category=None):
    with open(input_path, "r", encoding="utf-8") as f:
        raw_text = f.read()

    result = extract_pipeline(
        raw_text,
        service_name,
        category,
    )

    base_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    out_dir = os.path.join(
        base_dir,
        "data",
        "extracted",
    )

    os.makedirs(out_dir, exist_ok=True)

    safe_name = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        service_name.lower(),
    ).strip("_") or "service"

    out_path = os.path.join(
        out_dir,
        f"{safe_name}.json",
    )

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Extraction complete. Output written to {out_path}")

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract privacy clauses from raw policy text."
    )

    parser.add_argument("input_file")
    parser.add_argument("service_name")
    parser.add_argument("--category", default=None)

    args = parser.parse_args()

    process_file(
        args.input_file,
        args.service_name,
        args.category,
    )
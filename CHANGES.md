# Changes in this completed package

## Verified baseline fixes

### `src/scoring.py`
The portfolio score now uses the entity-aware composite formula:

`entity exposure = distinct-service concentration × mean(severity × specificity)`

and sums exposure across canonical entities.

### `src/marginal.py`
Marginal risk is computed by direct before/after recomputation:

`ΔR(s|P) = R(P ∪ {s}) − R(P)`

using a temporary copy of the database. The real portfolio DB is not mutated.

The supplied demo verifies the corrected behavior:

- candidate service risk: `14.0`
- marginal risk: `21.0`
- overlapping entity: `Location`

## Completed extraction path

### `src/extraction/llm_extractor.py`
The previous OpenAI implementation was only a partial stub. It is now a provider-neutral implementation supporting:

- `mock`
- `ollama`
- `openai`
- `anthropic`

The provider and model are controlled through environment variables. Responses are parsed and validated instead of being trusted blindly.

Mock mode remains deterministic so the project can run without an API key.

### `src/config.py`
Centralized provider/model configuration was added.

### `.env.example`
Added documented configuration examples for Mock, Ollama, OpenAI, and Anthropic.

### `requirements.txt`
Added `rapidfuzz`, so canonicalization no longer requires a separate manual install.

## Completed canonicalization path

### `src/canonicalize.py`
Canonicalization now combines:

1. normalization,
2. an expanded explicit alias table,
3. conservative fuzzy matching using RapidFuzz,
4. safe preservation of unknown entities.

The fuzzy step only matches against known aliases and uses a high threshold, reducing accidental merges.

The database loader remains idempotent and refreshes clause scoring fields when an existing clause is reprocessed.

## Extraction robustness

### `src/extract.py`
Policy splitting is now less dependent on a literal `". "` pattern and handles common whitespace/newline boundaries.

### `src/extraction/validator.py`
Numeric severity and specificity are now constrained to the documented 1–5 range.

## Developer experience

Added:

- `scripts/setup_windows.ps1`
- `scripts/run_demo_windows.ps1`
- `.env.example`
- regression tests for provider selection, model JSON parsing, fuzzy aliases, unknown-entity preservation, and score validation.

## What still requires human-supplied inputs

The software itself is complete and runnable, but no software package can manufacture a scientifically valid real-world corpus or API credentials.

The included `data/raw/` and `data/extracted/` fixtures are therefore clearly marked as development/demo data. Your team should replace/extend them with its own collected and annotated corpus for final research evaluation.

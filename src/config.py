"""Central configuration for ClauseGuard.

Environment variables:
  CLAUSEGUARD_LLM_PROVIDER=mock|ollama|openai|anthropic|gemini
  CLAUSEGUARD_LLM_MODEL=<provider-specific model>

  OPENAI_API_KEY=...
  ANTHROPIC_API_KEY=...
  GEMINI_API_KEY=...

  OLLAMA_BASE_URL=http://127.0.0.1:11434
  OLLAMA_MODEL=llama3.2:3b
  OPENAI_MODEL=gpt-4o-mini
  ANTHROPIC_MODEL=claude-sonnet-4-6
  GEMINI_MODEL=gemini-3.1-flash-lite

  CLAUSEGUARD_MAX_CLAUSES_PER_REQUEST=25
"""

import os


def _load_dotenv_file():
    """Load simple KEY=VALUE pairs from the project .env without extra dependencies."""
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        os.path.abspath(".env"),
    ]

    for path in candidates:
        if not os.path.isfile(path):
            continue

        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()

                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                if not key or key in os.environ:
                    continue

                if (
                    len(value) >= 2
                    and value[0] == value[-1]
                    and value[0] in {'"', "'"}
                ):
                    value = value[1:-1]

                os.environ[key] = value

        break


_load_dotenv_file()


VALID_PROVIDERS = {
    "mock",
    "ollama",
    "openai",
    "anthropic",
    "gemini",
}


def get_provider():
    explicit = os.getenv("CLAUSEGUARD_LLM_PROVIDER")

    if explicit:
        provider = explicit.strip().lower()

    elif os.getenv("GEMINI_API_KEY"):
        provider = "gemini"

    elif os.getenv("ANTHROPIC_API_KEY"):
        provider = "anthropic"

    elif os.getenv("OPENAI_API_KEY"):
        provider = "openai"

    else:
        provider = "mock"

    if provider not in VALID_PROVIDERS:
        raise ValueError(
            f"Unsupported CLAUSEGUARD_LLM_PROVIDER={provider!r}. "
            f"Choose one of {sorted(VALID_PROVIDERS)}."
        )

    return provider


def get_model(provider=None):
    provider = provider or get_provider()

    defaults = {
        "mock": "mock",

        "ollama": os.getenv(
            "OLLAMA_MODEL",
            "llama3.2:3b",
        ),

        "openai": os.getenv(
            "OPENAI_MODEL",
            "gpt-4o-mini",
        ),

        "anthropic": os.getenv(
            "ANTHROPIC_MODEL",
            "claude-sonnet-4-6",
        ),

        "gemini": os.getenv(
            "GEMINI_MODEL",
            "gemini-3.1-flash-lite",
        ),
    }

    return os.getenv(
        "CLAUSEGUARD_LLM_MODEL",
        defaults[provider],
    )


def get_max_clauses():
    try:
        return max(
            1,
            int(
                os.getenv(
                    "CLAUSEGUARD_MAX_CLAUSES_PER_REQUEST",
                    "25",
                )
            ),
        )
    except ValueError:
        return 25
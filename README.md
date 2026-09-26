# ClauseGuard

ClauseGuard is a local research prototype for analyzing privacy-policy clauses, canonicalizing privacy entities, storing a service portfolio, computing entity-aware exposure, and measuring the marginal risk of adding a candidate service.

## What is included

- C1: TF-IDF/Logistic Regression privacy prefilter.
- C1: Structured LLM extraction with four modes:
  - `mock` — deterministic, offline, no key required.
  - `ollama` — local LLM, no cloud API key required.
  - `openai` — OpenAI API.
  - `anthropic` — Claude Messages API.
- C2: Exact aliases + conservative fuzzy canonicalization.
- C3: SQLite portfolio storage with idempotent loading.
- C4: Entity-aware composite risk:
  `entity exposure = distinct service concentration × mean(severity × specificity)`.
- C5: True marginal risk:
  `R(P ∪ {s}) − R(P)`, computed by direct recomputation on a temporary database copy.
- Flask API and dashboard.
- Chrome extension.
- Evaluation utilities and regression tests.
- End-to-end demo that uses a temporary database and never modifies the real portfolio DB.

## Requirements

- Python 3.9+
- Chrome/Chromium for the extension.
- Optional: Ollama for a local LLM.
- Optional: OpenAI or Anthropic API credentials for cloud extraction.

## Windows setup

From the `clauseguarddemowork` directory:

```powershell
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Or run:

```powershell
.\scripts\setup_windows.ps1
```

The default `.env.example` uses `mock`, so no API key is needed.

## 1. Verify the project

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

A clean installation should report all tests passing.

## 2. Run the end-to-end demo

```powershell
python run_demo.py
```

The demo:

1. Reads the included Spotify fixture.
2. Extracts privacy clauses.
3. Canonicalizes entities.
4. Loads a temporary portfolio.
5. Computes the composite score.
6. Adds the included Google candidate to a temporary DB copy.
7. Computes the true marginal delta.
8. Deletes the temporary database.

It does not modify `data/db/portfolio.db`.

## 3. Use local Ollama

If Ollama is installed and a model is available:

```powershell
ollama list
ollama run llama3.2:3b
```

Set in `.env`:

```text
CLAUSEGUARD_LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Then run the normal extraction or API.

This is the recommended development path when you want real LLM extraction without adding a cloud API key.

## 4. Use OpenAI

Set:

```text
CLAUSEGUARD_LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

The model name is configurable because provider model catalogs change.

## 5. Use Claude

Set:

```text
CLAUSEGUARD_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-sonnet-4-6
```

The model name is configurable so the project can be updated when Anthropic retires or replaces models.

## 6. Analyze a policy text file

Put a policy in:

```text
data/raw/myservice.txt
```

Then:

```powershell
python src/extract.py data/raw/myservice.txt MyService --category Messaging
```

The extracted JSON is written to:

```text
data/extracted/myservice.json
```

To load it into the real portfolio database:

```powershell
python src/canonicalize.py data/extracted/myservice.json
```

The portfolio database is:

```text
data/db/portfolio.db
```

## 7. Start the dashboard/API

```powershell
python src/dashboard.py
```

Open:

```text
http://127.0.0.1:5000
```

Available API routes include:

- `GET /api/portfolio`
- `GET /api/overlap-graph`
- `POST /api/analyze-policy`
- `POST /api/marginal-risk`
- `POST /api/compare-services`

## 8. Load the Chrome extension

1. Start the backend:
   ```powershell
   python src/dashboard.py
   ```
2. Open `chrome://extensions/`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the project's `extension` folder.
6. Open a privacy-policy webpage.
7. Click the ClauseGuard extension.
8. Click **Analyze Policy**.

The extension sends page text to the local Flask backend. The backend performs extraction, canonicalization, and service-level scoring.

## Data and research limitations

The included Spotify/Google fixtures are development/demo data. They are intentionally not presented as a validated real-world benchmark.

For a research evaluation, replace or extend them with your team's collected policy corpus and independently annotated ground truth. Keep held-out examples separate from tuning data.

The numeric scoring weights are deterministic baseline assumptions (`w1=1.0`, `w2=1.0`) and should be treated as experimental parameters, not empirical claims.

## Project structure

```text
clauseguarddemowork/
├── src/
│   ├── extraction/
│   │   ├── prefilter.py
│   │   ├── llm_extractor.py
│   │   └── validator.py
│   ├── canonicalize.py
│   ├── db.py
│   ├── scoring.py
│   ├── marginal.py
│   ├── extract.py
│   ├── dashboard.py
│   └── static/
├── extension/
├── data/
│   ├── raw/
│   ├── extracted/
│   ├── evaluation/
│   └── robustness/
├── tests/
├── scripts/
├── run_demo.py
├── requirements.txt
├── .env.example
├── CHANGES.md
└── README.md
```

## Security notes

- Never commit `.env` or API keys.
- Keep the Flask API bound to `127.0.0.1` for local development.
- The demo uses temporary databases.
- Real policy text should be collected and used according to the applicable website terms, copyright rules, and your institution's research requirements.

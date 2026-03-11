# AGENTS.md

## Cursor Cloud specific instructions

### Overview

GA4 AutoTrack is a pure Python CLI tool — no web server, database, or Docker required. It runs a four-stage pipeline (Crawl → Analyze → SDR → GTM) and can operate in **demo mode** with zero network access.

### Running the application

- Use `python3` (not `python`) — the environment does not alias `python` to `python3`.
- **Demo mode** (offline, no API key): `python3 main.py --demo`
- **Full pipeline** (requires `OPENROUTER_API_KEY`): `python3 main.py --url https://www.oaklandish.com --ga4-id G-XXXXXXX`
- **Crawl only**: `python3 main.py --url https://www.oaklandish.com --crawl-only`
- Output files land in `output/` by default.

### Dependencies

All dependencies are listed in `README.md` under "Dependencies". Install with:
```
pip install requests beautifulsoup4 lxml openpyxl openai python-dotenv
```

### Lint / Test / Build

This project has no linting configuration, automated test suite, or build step. The primary validation is running `python3 main.py --demo` and verifying the two output files are generated (`output/*.xlsx` and `output/*.json`).

### Key caveats

- The `openai` package is used as an OpenRouter API client (not OpenAI directly). The base URL is set to `https://openrouter.ai/api/v1` in `src/analyzer.py`.
- `python-dotenv` is optional — if missing, the app falls back to reading `OPENROUTER_API_KEY` from the environment.
- The AI analyzer calls `anthropic/claude-opus-4.5` via OpenRouter. Without the API key, the full pipeline falls back to demo mode automatically.

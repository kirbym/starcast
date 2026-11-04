# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

StarCast is a Python application: the user supplies a location and date, the app computes which planets and constellations are actually visible that night, and an AI narrator picks 3 highlights and writes a short "cosmic weather report" — grounded in real astronomy but told with a bit of wonder.

## Stack (inferred from .gitignore)

The project uses Python. The .gitignore includes patterns for:
- **Web frameworks**: Flask, Django, Streamlit, or Marimo (UI layer TBD)
- **Task queues**: Celery + Redis or RabbitMQ (async job processing)
- **Packaging**: uv / poetry / pdm (exact tool TBD once pyproject.toml exists)
- **Linting**: Ruff

## Development Commands

Settings for both deployables live in a root `.env` (copy `.env.example`).

### Backend (`backend/`)

```bash
uv sync                                                # install dependencies
uv run --env-file ../.env uvicorn app.main:app --reload   # run the API on port 8000

uv run ruff check .                                    # lint
uv run ruff format .                                   # format

uv run pytest                                          # all tests
uv run pytest tests/test_astronomy.py::test_name       # single test
```

The first astronomy run downloads the DE440s ephemeris (~32 MB) to `backend/.cache/skyfield`, or to `STARCAST_DATA_DIR` if set.

`tests/test_claude_narrator.py` has one opt-in test that calls the real Claude API. It is skipped unless `ANTHROPIC_API_KEY` is set.

### Frontend (`frontend/`)

```bash
npm ci                                  # install dependencies
npm run dev                             # run the app on port 5173

npm run typecheck                       # typecheck
npm run lint                            # lint

npm test                                # all tests
npx vitest run src/App.test.tsx -t "name"   # single test
```

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`kirbym/starcast`). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout: one `CONTEXT.md` at the repo root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.

## Architecture Notes

The core pipeline will likely follow this flow:

1. **Input** — location (lat/lon or place name) + date
2. **Astronomy engine** — compute visible planets, constellations, rise/set times (likely `astropy` or `ephem`)
3. **Filter/rank** — select 3 highlights worth narrating
4. **AI narration** — call Claude API to write the headline and short story
5. **Output** — rendered to UI (Streamlit/Marimo) or CLI

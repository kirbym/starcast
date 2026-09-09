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

> No code exists yet. Update this section once the project is initialized.

Typical commands once set up:

```bash
# Install dependencies
uv sync          # or: pip install -e ".[dev]"

# Run the app
python -m starcast   # or framework-specific command

# Lint
ruff check .
ruff format .

# Tests
pytest
pytest tests/test_specific.py::test_name   # single test
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

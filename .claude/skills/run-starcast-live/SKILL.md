---
name: run-starcast-live
description: Run StarCast live with real Claude narration and open it in the user's own browser for them to try by hand. Use when the user wants to try, view or play with the app themselves, or asks for a live run. For automated checks and screenshots, use run-starcast instead.
---

`.claude/skills/run-starcast-live/serve.mjs` starts the FastAPI backend (port 8000) with the real `.env`, starts the Vite dev server (port 5173), waits for both, and opens http://localhost:5173 in the default browser. It keeps running until it is stopped. It uses only Node built-ins, so it needs no install of its own.

All paths are relative to the repo root.

## Steps

1. **Start it in the background**, so the servers outlive your turn:

   ```powershell
   node .claude/skills/run-starcast-live/serve.mjs
   ```

   Done when its output has a `READY:` line. An exit code of 2 means it refused to start, and its last line says why (see Gotchas).

2. **Hand over.** Tell the user the app is open at http://localhost:5173, that each report costs one real Claude call, and that they have to allow location in the browser or search for a place. Stay available: the `[backend]` and `[frontend]` lines in the task's output are the server logs, so read them when the user reports a problem.

3. **Stop it** when the user is done or asks:

   ```powershell
   node .claude/skills/run-starcast-live/serve.mjs --stop
   ```

   Done when it prints `stopped pid ...` for each port, or `nothing was listening`. Stopping the background task alone can leave the server processes running on Windows, so always run `--stop`. The background task then ends with exit code 1, which is expected.

## Gotchas

- **The `.env` must have `ANTHROPIC_API_KEY`.** The script reads `.env` in this checkout, or in the main checkout when run from a worktree. Without a key it refuses rather than falling back to a stub, because this skill exists to show real narration.
- **Ports already in use**: the script refuses to start. Often StarCast is already running, so just open http://localhost:5173. Otherwise run `--stop` and start again.
- **An activated backend venv hides uv** (`No module named uv`). The script strips the venv from the servers' environment and tries `uv`, `python -m uv`, then `py -m uv`.
- **First report is slow in a fresh checkout**: it downloads the DE440s ephemeris (~32 MB). In a worktree the script points `STARCAST_DATA_DIR` at the main checkout's copy when one exists.
- **Dev mode**: Vite serves with hot reload, so edits to `frontend/` show up without a restart. The backend runs without `--reload`, so restart for backend changes.
- **Reports depend on the place and today's date**, so the sky changes daily. The page computes tonight for the browser's location or the searched place.

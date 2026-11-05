---
name: run-starcast
description: Build, run and drive StarCast (FastAPI backend + Vite/React frontend) in a real browser. Use when asked to start or run the app, try it in a browser, take a screenshot of the UI, smoke test a report end to end, or check a change in the running app.
---

StarCast is a FastAPI backend plus a Vite/React page that shows a narrated Cosmic Report. Drive it with `.claude/skills/run-starcast/driver.mjs`: it starts both servers, opens headless Chrome, checks each scenario, writes screenshots and stops everything.

All paths are relative to the repo root. Verified on Windows 11 with PowerShell. The driver has a POSIX branch that has not been run.

## Prerequisites

Node, Python and Google Chrome installed. The driver uses the installed Chrome, so no browser download is needed.

`uv` may not be on PATH. If it isn't, use `python -m uv` in place of `uv`; the driver does this itself.

## Setup

Run each from the repo root:

```powershell
npm ci --prefix .claude/skills/run-starcast
npm ci --prefix frontend
python -m uv sync --project backend
```

## Run (agent path)

Without a key, and free: Claude is replaced by a local stub at the HTTP boundary.

```powershell
node .claude/skills/run-starcast/driver.mjs --stub
```

With real Claude, one paid call per POST. The driver finds `.env` in this checkout, or in the main checkout when run from a worktree. If there is no `.env`, it falls back to the stub and says so on its first line.

```powershell
node .claude/skills/run-starcast/driver.mjs no-darkness
```

Pass scenario names to run only those. With none, all four run.

| scenario | what it checks |
|---|---|
| `san-francisco` | Location granted: Headline shown, exactly 1 POST, local date |
| `denied` | Location denied: alert shown, no POST, so no Claude cost |
| `phone` | London at 390px wide: Headline shown, no horizontal scroll |
| `no-darkness` | London with the clock at midsummer: zero-length Viewing Window |

Every scenario also fails on a console error or a non-200 report.

Exit code is 0 if all pass, 1 if any fail, 2 if the arguments are bad or a port is taken. Each scenario prints the page text, the request, the Viewing Window and a screenshot path.

Screenshots land in `.cache/run-starcast/<scenario>.png`, which is git-ignored. **Look at them.** The driver can't judge how the page looks.

To cover a new behaviour, add an entry to `SCENARIOS` at the top of `driver.mjs`.

## Run (human path)

Two terminals. From `backend/`, with the `.env` path written with forward slashes:

```powershell
python -m uv run --env-file ../.env uvicorn app.main:app --port 8000
```

From `frontend/`:

```powershell
$env:VITE_API_BASE_URL = 'http://localhost:8000'; npx vite --port 5173 --strictPort
```

Open http://localhost:5173 and allow location. Stop each with Ctrl-C.

## Test

```powershell
python -m uv run --project backend pytest backend
npm test --prefix frontend
```

With `ANTHROPIC_API_KEY` set, the backend suite also makes one real Claude call. Without it, that one test is skipped.

## Gotchas

- **Location is simulated.** The driver grants Chrome a fixed position, so the browser's permission prompt and the machine's real location are never exercised.
- **Astronomy depends on today's date.** Only `no-darkness` fixes the clock, and it does so in the page only, by changing the date the page sends. Other scenarios report tonight, so their output changes daily.
- **Dev server only.** The driver runs Vite in dev mode, not the production build. That helps one check: `StrictMode` runs effects twice in dev, so the "exactly 1 POST" check catches doubled Claude calls.
- **Worktrees have no `.env`.** It is untracked, so `--env-file ../.env` fails in a worktree. Pass the main checkout's path, or use the driver.
- **`VITE_API_BASE_URL` comes from the root `.env`.** Vite reads it through `envDir: '..'`, so in a worktree set it in the environment, or the page POSTs to its own origin.
- **The first astronomy run downloads DE440s** (~32 MB) to `backend/.cache/skyfield`. Each worktree downloads its own copy unless `STARCAST_DATA_DIR` is set.

## Troubleshooting

- **`npm error Unknown cli flags: --port, --strictPort`**: PowerShell's `npm.ps1` swallows the `--` in `npm run dev -- --port 5173`. Call Vite directly with `npx vite`.
- **`error: No environment file found at: D:starcast.env`**: the backslashes were stripped from `D:\starcast\.env`. Use forward slashes.
- **`http://localhost:8000/health is already in use`**: an earlier server is still running. Stop it, then rerun:

  ```powershell
  8000,5173 | ForEach-Object { Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -Confirm:$false } }
  ```

- **`Stop-Process` leaves a server task "failed" with exit code 255**: expected when a server is killed.
- **Refused with "too complex to verify that it stays inside the worktree"**: in a worktree session, run plain single commands, and write files with the Write tool rather than a heredoc.

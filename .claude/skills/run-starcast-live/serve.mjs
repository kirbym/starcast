// Runs StarCast live for a person to try: real Claude narration, both servers, the page open in
// their default browser. Keeps running until stopped.
//
//   node .claude/skills/run-starcast-live/serve.mjs          # start and open the browser
//   node .claude/skills/run-starcast-live/serve.mjs --stop   # stop whatever holds the ports
//
// See SKILL.md. Uses only Node built-ins, so it needs no npm install of its own.
import { execFileSync, spawn, spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { delimiter, dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const API_PORT = 8000
const WEB_PORT = 5173
const API_URL = `http://localhost:${API_PORT}`
const WEB_URL = `http://localhost:${WEB_PORT}/`
const WINDOWS = process.platform === 'win32'

function log(line) {
  console.log(`[starcast-live] ${line}`)
}

function fail(message) {
  console.error(`[starcast-live] ${message}`)
  process.exit(2)
}

function mainCheckout() {
  const commonDir = execFileSync(
    'git',
    ['rev-parse', '--path-format=absolute', '--git-common-dir'],
    { cwd: REPO, encoding: 'utf8' },
  ).trim()
  return dirname(commonDir)
}

// Worktrees don't get the main checkout's untracked .env, so look there too.
function findEnvFile() {
  return [join(REPO, '.env'), join(mainCheckout(), '.env')].find(existsSync)
}

function readEnvFile(path) {
  const values = {}
  for (const line of readFileSync(path, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/)
    if (match) values[match[1]] = match[2].replace(/^(['"])(.*)\1$/, '$2')
  }
  return values
}

// An activated backend venv puts its own python first on PATH, and that python has no uv module.
// So drop the venv from the children's environment, and try each way of reaching uv in turn.
function cleanEnv() {
  const env = { ...process.env }
  const venv = env.VIRTUAL_ENV
  delete env.VIRTUAL_ENV
  if (venv) {
    const pathKey = Object.keys(env).find((key) => key.toUpperCase() === 'PATH')
    const venvDir = resolve(venv).toLowerCase()
    env[pathKey] = env[pathKey]
      .split(delimiter)
      .filter((dir) => !resolve(dir).toLowerCase().startsWith(venvDir))
      .join(delimiter)
  }
  return env
}

function uvCommand(env) {
  const candidates = [['uv'], ['python', '-m', 'uv'], ['python3', '-m', 'uv']]
  if (WINDOWS) candidates.push(['py', '-m', 'uv'])
  const found = candidates.find(
    ([command, ...args]) =>
      spawnSync(command, [...args, '--version'], { env }).status === 0,
  )
  if (!found) fail('uv not found. Install it with: python -m pip install uv')
  return found
}

function listeningPids(port) {
  if (WINDOWS) {
    const out = spawnSync('netstat', ['-ano', '-p', 'tcp'], { encoding: 'utf8' }).stdout
    return [
      ...new Set(
        out
          .split(/\r?\n/)
          .map((line) => line.trim().split(/\s+/))
          .filter((cols) => cols[3] === 'LISTENING' && cols[1]?.endsWith(`:${port}`))
          .map((cols) => cols[4]),
      ),
    ]
  }
  const out = spawnSync('lsof', ['-ti', `tcp:${port}`, '-sTCP:LISTEN'], { encoding: 'utf8' })
  return out.stdout.split(/\s+/).filter(Boolean)
}

function killTree(pid) {
  if (WINDOWS) spawnSync('taskkill', ['/PID', String(pid), '/T', '/F'])
  else {
    try {
      process.kill(-pid, 'SIGTERM')
    } catch {
      try {
        process.kill(pid, 'SIGTERM')
      } catch {}
    }
  }
}

function stopPorts() {
  let stopped = 0
  for (const port of [API_PORT, WEB_PORT]) {
    for (const pid of listeningPids(port)) {
      killTree(pid)
      stopped += 1
      log(`stopped pid ${pid} on port ${port}`)
    }
  }
  if (!stopped) log('nothing was listening on 8000 or 5173')
}

async function isServing(url) {
  try {
    await fetch(url)
    return true
  } catch {
    return false
  }
}

function startProcess(name, command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: !WINDOWS,
  })
  const prefix = (chunk) =>
    chunk
      .toString()
      .split(/\r?\n/)
      .filter(Boolean)
      .forEach((line) => console.log(`[${name}] ${line}`))
  child.stdout.on('data', prefix)
  child.stderr.on('data', prefix)
  return { name, child }
}

async function waitUntilServing(url, started) {
  const deadline = Date.now() + 180_000 // A first run may have to install packages.
  while (Date.now() < deadline) {
    if (await isServing(url)) return
    if (started.child.exitCode !== null) fail(`${started.name} exited before serving ${url}`)
    await new Promise((wait) => setTimeout(wait, 250))
  }
  fail(`${started.name} did not serve ${url} within 3 minutes`)
}

function openBrowser(url) {
  if (WINDOWS) spawn('cmd', ['/c', 'start', '', url], { stdio: 'ignore', detached: true })
  else if (process.platform === 'darwin') spawn('open', [url], { stdio: 'ignore', detached: true })
  else spawn('xdg-open', [url], { stdio: 'ignore', detached: true })
}

if (process.argv.includes('--stop')) {
  stopPorts()
  process.exit(0)
}

for (const url of [`${API_URL}/health`, WEB_URL]) {
  if (await isServing(url)) {
    fail(`${url} is already in use. If it's StarCast, it's already running: open ${WEB_URL}. Otherwise stop it with --stop.`)
  }
}

const envFile = findEnvFile()
if (!envFile) fail('No .env found here or in the main checkout. Copy .env.example to .env and set ANTHROPIC_API_KEY.')
const fileValues = readEnvFile(envFile)
if (!fileValues.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_API_KEY) {
  fail(`ANTHROPIC_API_KEY is empty in ${envFile}. Set it to run with real Claude.`)
}

const env = cleanEnv()
// A worktree would otherwise download its own ~32 MB ephemeris, so share the main checkout's.
const sharedData = join(mainCheckout(), 'backend', '.cache', 'skyfield')
if (!fileValues.STARCAST_DATA_DIR && !env.STARCAST_DATA_DIR && existsSync(sharedData)) {
  env.STARCAST_DATA_DIR = sharedData
}

if (!existsSync(join(REPO, 'frontend', 'node_modules', 'vite'))) {
  log('installing frontend dependencies (npm ci)')
  // npm is a .cmd script on Windows, which only runs through a shell.
  const install = spawnSync('npm ci', { cwd: join(REPO, 'frontend'), stdio: 'inherit', shell: true, env })
  if (install.status !== 0) fail('npm ci failed in frontend/')
}

log(`Claude: real API, each report is a paid call (${envFile})`)
const [uv, ...uvArgs] = uvCommand(env)
const backend = startProcess(
  'backend',
  uv,
  [
    ...uvArgs,
    'run',
    '--env-file',
    envFile.replaceAll('\\', '/'),
    'uvicorn',
    'app.main:app',
    '--port',
    String(API_PORT),
  ],
  { cwd: join(REPO, 'backend'), env: { ...env, CORS_ORIGIN: `http://localhost:${WEB_PORT}` } },
)
const frontend = startProcess(
  'frontend',
  process.execPath,
  ['node_modules/vite/bin/vite.js', '--port', String(WEB_PORT), '--strictPort'],
  { cwd: join(REPO, 'frontend'), env: { ...env, VITE_API_BASE_URL: API_URL } },
)

let stopping = false
function shutdown(code) {
  if (stopping) return
  stopping = true
  log('stopping both servers')
  killTree(backend.child.pid)
  killTree(frontend.child.pid)
  process.exit(code)
}
process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
process.on('SIGHUP', () => shutdown(0))
for (const { name, child } of [backend, frontend]) {
  child.on('exit', (code) => {
    if (stopping) return
    log(`${name} exited (code ${code})`)
    shutdown(1)
  })
}

await waitUntilServing(`${API_URL}/health`, backend)
await waitUntilServing(WEB_URL, frontend)
openBrowser(WEB_URL)
log(`READY: StarCast is running at ${WEB_URL} (API ${API_URL}). Opened it in the default browser.`)
log('Stop with Ctrl-C, or: node .claude/skills/run-starcast-live/serve.mjs --stop')

// Runs StarCast for real: starts the backend and frontend, opens them in headless Chrome,
// checks each scenario, writes screenshots, and stops everything again.
//
//   node .claude/skills/run-starcast/driver.mjs [--stub] [scenario ...]
//
// Exits non-zero if any scenario fails. See SKILL.md.
import { execFileSync, spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync } from 'node:fs'
import { createServer } from 'node:http'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const SHOTS = join(REPO, '.cache', 'run-starcast')
const API_PORT = 8000
const WEB_PORT = 5173
const WEB_URL = `http://localhost:${WEB_PORT}/`

const LONDON = { latitude: 51.5074, longitude: -0.1278 }

const SCENARIOS = {
  'san-francisco': {
    context: {
      geolocation: { latitude: 37.7749, longitude: -122.4194 },
      permissions: ['geolocation'],
      timezoneId: 'America/Los_Angeles',
    },
    expect: { selector: 'h1', posts: 1 },
  },
  denied: {
    context: { timezoneId: 'America/Los_Angeles' },
    expect: { selector: '[role=alert]', posts: 0 },
  },
  phone: {
    context: {
      geolocation: LONDON,
      permissions: ['geolocation'],
      timezoneId: 'Europe/London',
      viewport: { width: 390, height: 780 },
    },
    expect: { selector: 'h1', posts: 1 },
  },
  // London at midsummer has no astronomical darkness, so the Viewing Window has zero length.
  'no-darkness': {
    context: {
      geolocation: LONDON,
      permissions: ['geolocation'],
      timezoneId: 'Europe/London',
    },
    now: '2026-06-21T20:00:00Z',
    expect: { selector: 'h1', posts: 1, zeroLengthWindow: true },
  },
}

function log(line) {
  console.log(`[run-starcast] ${line}`)
}

// Worktrees don't get the main checkout's untracked .env, so look there too.
function findEnvFile() {
  const commonDir = execFileSync(
    'git',
    ['rev-parse', '--path-format=absolute', '--git-common-dir'],
    { cwd: REPO, encoding: 'utf8' },
  ).trim()
  return [join(REPO, '.env'), join(dirname(commonDir), '.env')].find(existsSync)
}

function startStubClaude() {
  const server = createServer((request, response) => {
    request.resume()
    request.on('end', () => {
      const report = { headline: 'A stubbed sky, quiet tonight.', cards: [] }
      response.setHeader('content-type', 'application/json')
      response.end(
        JSON.stringify({
          id: 'msg_stub',
          type: 'message',
          role: 'assistant',
          model: 'claude-sonnet-5-5',
          content: [{ type: 'text', text: JSON.stringify(report) }],
          stop_reason: 'end_turn',
          stop_sequence: null,
          usage: { input_tokens: 1, output_tokens: 1 },
        }),
      )
    })
  })
  return new Promise((ready) =>
    server.listen(0, '127.0.0.1', () => ready(server)),
  )
}

function uvCommand() {
  const onPath = spawnSync('uv', ['--version']).status === 0
  return onPath ? ['uv'] : ['python', '-m', 'uv']
}

function startProcess(name, command, args, options) {
  const child = spawn(command, args, {
    ...options,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: process.platform !== 'win32',
  })
  const output = []
  child.stdout.on('data', (chunk) => output.push(chunk))
  child.stderr.on('data', (chunk) => output.push(chunk))
  return { name, child, output: () => Buffer.concat(output).toString() }
}

function stopProcess({ child }) {
  if (child.exitCode !== null) return
  // Both servers run child processes, so stop the whole tree.
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'])
  } else {
    process.kill(-child.pid, 'SIGTERM')
  }
}

async function isServing(url) {
  try {
    await fetch(url)
    return true
  } catch {
    return false
  }
}

async function waitUntilServing(url, started) {
  const deadline = Date.now() + 120_000 // A first run may have to install packages.
  while (Date.now() < deadline) {
    if (await isServing(url)) return
    if (started.child.exitCode !== null) break
    await new Promise((wait) => setTimeout(wait, 250))
  }
  throw new Error(`${started.name} did not start:\n${started.output()}`)
}

async function runScenario(browser, name, { context, now, expect }) {
  const browserContext = await browser.newContext({
    viewport: { width: 1280, height: 720 },
    ...context,
  })
  const page = await browserContext.newPage()
  if (now) await page.clock.setFixedTime(now)

  const posts = []
  const reports = []
  const consoleErrors = []
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(String(error)))
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/report')) {
      posts.push(request.postDataJSON())
    }
  })
  page.on('response', async (response) => {
    const isPost = response.request().method() === 'POST'
    if (isPost && response.url().endsWith('/api/report')) {
      reports.push({ status: response.status(), body: await response.json() })
    }
  })

  await page.goto(WEB_URL)
  await page.waitForSelector(expect.selector, { timeout: 45_000 })
  await page.waitForTimeout(1500) // Leaves time for a duplicate request to show up.

  const shot = join(SHOTS, `${name}.png`)
  await page.screenshot({ path: shot })
  const text = await page.locator('main').innerText()
  const overflows = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  )
  await browserContext.close()

  const problems = []
  if (posts.length !== expect.posts) {
    problems.push(`expected ${expect.posts} POST, saw ${posts.length}`)
  }
  if (consoleErrors.length) problems.push(`console: ${consoleErrors.join(' | ')}`)
  if (overflows) problems.push('page scrolls horizontally')
  if (reports.some((report) => report.status !== 200)) {
    problems.push(`report failed: ${JSON.stringify(reports)}`)
  }
  if (expect.zeroLengthWindow) {
    const window = reports[0]?.body.viewing_window
    if (window?.starts_at !== window?.ends_at) {
      problems.push(`expected a zero-length window: ${JSON.stringify(window)}`)
    }
  }

  log(`${problems.length ? 'FAIL' : 'ok  '} ${name}: ${text}`)
  if (posts.length) log(`     request: ${JSON.stringify(posts[0])}`)
  if (reports.length) {
    log(`     window: ${JSON.stringify(reports[0].body.viewing_window)}`)
  }
  log(`     screenshot: ${shot}`)
  problems.forEach((problem) => log(`     PROBLEM: ${problem}`))
  return problems.length === 0
}

const args = process.argv.slice(2)
const names = args.filter((arg) => !arg.startsWith('--'))
const selected = names.length ? names : Object.keys(SCENARIOS)
const unknown = selected.filter((name) => !SCENARIOS[name])
if (unknown.length) {
  console.error(
    `Unknown scenario: ${unknown}. Choose from: ${Object.keys(SCENARIOS).join(', ')}`,
  )
  process.exit(2)
}

for (const url of [`http://localhost:${API_PORT}/health`, WEB_URL]) {
  if (await isServing(url)) {
    console.error(`${url} is already in use. Stop that server first.`)
    process.exit(2)
  }
}

mkdirSync(SHOTS, { recursive: true })
const envFile = args.includes('--stub') ? undefined : findEnvFile()
const stub = envFile ? undefined : await startStubClaude()
log(
  envFile
    ? `Claude: real API, each POST is a paid call (${envFile})`
    : 'Claude: local stub, no key used',
)

const [uv, ...uvArgs] = uvCommand()
const backendEnv = { ...process.env, CORS_ORIGIN: `http://localhost:${WEB_PORT}` }
if (stub) {
  backendEnv.ANTHROPIC_API_KEY = 'stub'
  backendEnv.ANTHROPIC_BASE_URL = `http://127.0.0.1:${stub.address().port}`
}
const backend = startProcess(
  'backend',
  uv,
  [
    ...uvArgs,
    'run',
    ...(envFile ? ['--env-file', envFile.replaceAll('\\', '/')] : []),
    'uvicorn',
    'app.main:app',
    '--port',
    String(API_PORT),
  ],
  { cwd: join(REPO, 'backend'), env: backendEnv },
)
const frontend = startProcess(
  'frontend',
  process.execPath,
  ['node_modules/vite/bin/vite.js', '--port', String(WEB_PORT), '--strictPort'],
  {
    cwd: join(REPO, 'frontend'),
    env: {
      ...process.env,
      VITE_API_BASE_URL: `http://localhost:${API_PORT}`,
    },
  },
)

let passed = false
try {
  await waitUntilServing(`http://localhost:${API_PORT}/health`, backend)
  await waitUntilServing(WEB_URL, frontend)
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const results = []
  for (const name of selected) {
    results.push(await runScenario(browser, name, SCENARIOS[name]))
  }
  await browser.close()
  passed = results.every(Boolean)
} finally {
  stopProcess(backend)
  stopProcess(frontend)
  stub?.close()
}
log(passed ? 'All scenarios passed.' : 'Some scenarios FAILED.')
process.exit(passed ? 0 : 1)

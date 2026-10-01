#!/usr/bin/env node

/**
 * Phase 4.6 browser smoke and accessibility gate.
 *
 * The repository deliberately keeps this check dependency-free: the quality
 * gate already installs Vite and axe-core, while Chrome/Chromium is supplied
 * by the build host. The script drives Chrome through its local CDP endpoint,
 * visits every public route in both supported locales, and records axe results.
 */
import { spawn, spawnSync } from 'node:child_process'
import { createServer } from 'node:net'
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'

const root = resolve(process.cwd())
const reportPath = resolve(process.env.PHASE46_BROWSER_REPORT || join(root, '..', 'test-results', 'phase-4-6', 'browser-axe.json'))
const axePath = join(root, 'node_modules', 'axe-core', 'axe.min.js')
const routes = [
  '/', '/login', '/accept-invitation', '/app/dashboard', '/app/usage',
  '/app/prospects', '/app/prospects/new', '/app/prospects/00000000-0000-0000-0000-000000000001',
  '/app/pipeline', '/app/opportunities', '/app/tasks', '/app/search',
  '/app/compliance/sources', '/app/compliance/retention', '/app/imports/history',
  '/app/exports', '/app/account', '/app/admin/organization', '/app/admin/users',
  '/app/platform/organizations', '/app/audit', '/app/platform/audit',
]
const locales = ['fr-CA', 'en-CA']

const wait = (ms) => new Promise((resolvePromise) => setTimeout(resolvePromise, ms))

function freePort() {
  return new Promise((resolvePromise, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port
      server.close(() => resolvePromise(port))
    })
  })
}

function findBrowser() {
  const candidates = [
    process.env.CHROME_PATH,
    process.env.CHROMIUM_PATH,
    process.platform === 'win32' ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : null,
    process.platform === 'win32' ? 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe' : null,
    'google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'msedge',
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (candidate.includes('\\') || candidate.includes('/')) {
      if (existsSync(candidate)) return candidate
    } else {
      const lookup = spawnSync(process.platform === 'win32' ? 'where' : 'which', [candidate], { encoding: 'utf8' })
      if (lookup.status === 0 && lookup.stdout.trim()) return lookup.stdout.trim().split(/\r?\n/)[0]
    }
  }
  throw new Error('Chrome/Chromium introuvable. Définir CHROME_PATH ou installer un navigateur compatible CDP.')
}

async function waitForJson(url, timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return await response.json()
    } catch {
      // The browser or preview is still starting.
    }
    await wait(250)
  }
  throw new Error(`Délai dépassé en attendant ${url}`)
}

async function waitForHttp(url, timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // The preview server is still starting.
    }
    await wait(250)
  }
  throw new Error(`Délai dépassé en attendant ${url}`)
}

class CdpConnection {
  constructor(webSocket) {
    this.webSocket = webSocket
    this.nextId = 1
    this.pending = new Map()
    this.events = []
    webSocket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id && this.pending.has(message.id)) {
        const { resolve: resolvePromise, reject } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) reject(new Error(`${message.error.code}: ${message.error.message}`))
        else resolvePromise(message.result)
      } else if (message.method) {
        this.events.push(message)
      }
    })
  }

  command(method, params = {}, sessionId) {
    const id = this.nextId++
    return new Promise((resolvePromise, reject) => {
      this.pending.set(id, { resolve: resolvePromise, reject })
      this.webSocket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }))
    })
  }

  close() {
    this.webSocket.close()
  }
}

async function connect(url) {
  const webSocket = new WebSocket(url)
  await new Promise((resolvePromise, reject) => {
    webSocket.addEventListener('open', resolvePromise, { once: true })
    webSocket.addEventListener('error', reject, { once: true })
  })
  return new CdpConnection(webSocket)
}

async function main() {
  if (!existsSync(axePath)) throw new Error(`axe-core introuvable: ${axePath}`)
  const browserPath = findBrowser()
  const previewPort = await freePort()
  const debugPort = await freePort()
  const profile = join(process.env.TEMP || process.env.TMPDIR || '/tmp', `marketteo-phase46-${process.pid}`)
  mkdirSync(profile, { recursive: true })
  mkdirSync(resolve(reportPath, '..'), { recursive: true })

  const preview = spawn(process.execPath, [join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'preview', '--host', '127.0.0.1', '--port', String(previewPort)], {
    cwd: root,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  const browser = spawn(browserPath, [
    '--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
    `--remote-debugging-port=${debugPort}`, `--user-data-dir=${profile}`, 'about:blank',
  ], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true })

  const report = { generatedAt: new Date().toISOString(), browser: browserPath, baseUrl: `http://127.0.0.1:${previewPort}`, checks: [], failures: [] }
  let connection
  let stage = 'initialisation'
  try {
    stage = 'démarrage de Vite preview'
    await waitForHttp(`http://127.0.0.1:${previewPort}`)
    stage = 'connexion CDP'
    const version = await waitForJson(`http://127.0.0.1:${debugPort}/json/version`)
    connection = await connect(version.webSocketDebuggerUrl)
    stage = 'création de la cible CDP'
    const target = await connection.command('Target.createTarget', { url: 'about:blank' })
    const attached = await connection.command('Target.attachToTarget', { targetId: target.targetId, flatten: true })
    const sessionId = attached.sessionId
    await connection.command('Page.enable', {}, sessionId)
    await connection.command('Runtime.enable', {}, sessionId)
    await connection.command('Page.addScriptToEvaluateOnNewDocument', { source: `window.__marketteoBrowserErrors=[]; window.addEventListener('error', e => window.__marketteoBrowserErrors.push(String(e.error || e.message))); window.addEventListener('unhandledrejection', e => window.__marketteoBrowserErrors.push(String(e.reason)));` }, sessionId)
    const axeSource = readFileSync(axePath, 'utf8')

    const evaluate = async (expression) => {
      const result = await connection.command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true }, sessionId)
      if (result.exceptionDetails) throw new Error(result.exceptionDetails.text || 'Runtime.evaluate failed')
      return result.result?.value
    }
    for (const locale of locales) {
      stage = `initialisation locale ${locale}`
      await connection.command('Page.navigate', { url: `http://127.0.0.1:${previewPort}/login` }, sessionId)
      await wait(1000)
      await evaluate(`localStorage.setItem('marketteo.public-locale.v1', ${JSON.stringify(locale)})`)
      for (const route of routes) {
        stage = `navigation ${locale} ${route}`
        const url = `http://127.0.0.1:${previewPort}${route}`
        await connection.command('Page.navigate', { url }, sessionId)
        await wait(1000)
        stage = `injection axe ${locale} ${route}`
        await evaluate(axeSource)
        stage = `analyse axe ${locale} ${route}`
        const result = await evaluate(`axe.run(document).then(r => ({ violations: r.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help })) }))`)
        const metadata = await evaluate(`({ path: location.pathname, lang: document.documentElement.lang, title: document.title, documentElement: Boolean(document.documentElement), body: Boolean(document.body), textLength: document.body?.innerText?.trim().length || 0, errors: window.__marketteoBrowserErrors || [] })`)
        const check = { locale, route, ...metadata, violations: result.violations }
        report.checks.push(check)
        for (const violation of result.violations) {
          if (violation.impact === 'critical' || violation.impact === 'serious') report.failures.push({ locale, route, type: 'axe', ...violation })
        }
        for (const error of metadata.errors) report.failures.push({ locale, route, type: 'browser-error', error })
        if (!metadata.documentElement) report.failures.push({ locale, route, type: 'empty-document' })
      }
    }
  } catch (error) {
    report.failures.push({ type: 'runner', stage, error: error?.stack || error?.message || String(error) })
  } finally {
    report.finishedAt = new Date().toISOString()
    if (report.checks.length === 0 && !report.failures.some((failure) => failure.type === 'runner')) {
      report.failures.push({ type: 'runner', error: 'Aucun parcours navigateur n’a été exécuté.' })
    }
    report.verdict = report.failures.length === 0 ? 'PASS' : 'FAIL'
    mkdirSync(resolve(reportPath, '..'), { recursive: true })
    await import('node:fs/promises').then(({ writeFile }) => writeFile(reportPath, JSON.stringify(report, null, 2), 'utf8'))
    connection?.close()
    const terminate = (child, signal = 'SIGKILL') => {
      if (process.platform === 'win32' && child.pid) {
        spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true })
      } else {
        child.kill(signal)
      }
      child.stdout?.destroy()
      child.stderr?.destroy()
      child.unref()
    }
    terminate(browser)
    terminate(preview)
    try {
      rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 250 })
    } catch (cleanupError) {
      console.warn(`[phase4.6-browser] Nettoyage du profil différé: ${cleanupError.message}`)
    }
  }
  if (report.failures.length) {
    throw new Error(`${report.failures.length} échec(s) navigateur/axe. Rapport: ${reportPath}`)
  }
  console.log(`Recette navigateur 4.6: ${report.checks.length} parcours contrôlés, axe PASS. Rapport: ${reportPath}`)
}

main().catch((error) => {
  console.error(`[phase4.6-browser] ${error.message}`)
  process.exitCode = 1
})

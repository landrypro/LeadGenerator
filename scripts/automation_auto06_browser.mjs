// AUT-AUTO-06 browser recipe. Run against `vite preview`:
// node scripts/automation_auto06_browser.mjs <path-to-playwright> [preview-url]
// The API is intercepted so this check validates the UI contract without CRM writes.
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

const require = createRequire(import.meta.url)
const { chromium } = require(process.argv[2] || 'playwright')
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const axePath = require.resolve('axe-core/axe.min.js', { paths: [resolve(root, 'client')] })
const base = process.argv[3] || 'http://127.0.0.1:4178'
const reportPath = resolve(root, process.env.AUT_AUTO06_BROWSER_REPORT || 'test-results/aut-auto-06/browser-report.json')

const organization = { id: 'aut-auto-06-pilot', name: 'Organisation pilote', locale: 'fr-CA' }
const session = {
  user: { id: 'aut-auto-06-user', display_name: 'Recette AUT-AUTO-06', email: 'recette@example.test', platform_role: null },
  active_organization: organization,
  memberships: [{ id: 'aut-auto-06-membership', role: 'admin', organization }],
  capabilities: ['automation:read:self', 'automation:plan:create', 'automation:read:organization'],
  automation_available: true,
  csrf_token: 'aut-auto-06-csrf',
}

const today = {
  counts: { open_prospects: 11, due_tasks: 2, overdue_tasks: 2, open_opportunities: 45 },
  items: [{ id: 'crm-prospect-1', kind: 'prospect', label: 'Prospect Alpha', stage: 'new' }],
}
const suggestions = {
  items: [
    { code: 'scope_open_prospects', label: 'Prospects ouverts', prompt: 'Montre-moi les prospects ouverts' },
    { code: 'rebalance_open_prospects', label: 'Étudier un rééquilibrage', prompt: 'Étudie un rééquilibrage des prospects' },
  ],
}

function planFor(text) {
  const normalized = String(text || '').toLocaleLowerCase()
  if (normalized.includes('aide') || normalized.includes('help')) {
    return { result_code: 'clarification_required', suggestion_codes: ['scope_open_prospects'], plan: null }
  }
  if (normalized.includes('supprime') || normalized.includes('delete')) {
    return { result_code: 'intent_not_supported', suggestion_codes: [], plan: null }
  }
  if (normalized.includes('libre')) {
    return { result_code: 'fallback_guided', suggestion_codes: ['scope_open_prospects'], plan: null }
  }
  if (normalized.includes('aucun') || normalized.includes('none')) {
    return {
      result_code: 'plan_ready', suggestion_codes: [], plan: {
        resolved_count: 0, bounded_count: 0, items: [], control_codes: ['read_only'], not_performed_codes: ['no_crm_write', 'no_job'],
      },
    }
  }
  return {
    result_code: 'plan_ready', suggestion_codes: [], plan: {
      resolved_count: 1, bounded_count: 1,
      items: [{ id: 'crm-prospect-1', kind: 'prospect', label: 'Prospect Alpha', stage: 'new', priority: 2 }],
      control_codes: ['read_only'], not_performed_codes: ['no_crm_write', 'no_job'],
    },
  }
}

const report = { generatedAt: new Date().toISOString(), baseUrl: base, checks: [], failures: [], interceptedWrites: 0 }
const browser = await chromium.launch({ headless: true })

try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  await page.route('**/api/**', async route => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (pathname.endsWith('/auth/me')) return json(session)
    if (pathname === '/api/automation/availability') return json({ global_enabled: true, organization_enabled: true, rollout_enabled: true, effective_enabled: true, assistant_available: true })
    if (pathname === '/api/automation/today') return json(today)
    if (pathname === '/api/automation/suggestions') return json(suggestions)
    if (pathname === '/api/automation/intent-plans') {
      const payload = request.postDataJSON?.() || {}
      return json(planFor(payload.user_text || payload.suggestion_code))
    }
    if (pathname.startsWith('/api/automation/telemetry/')) return json({ accepted: true })
    if (pathname === '/api/health' || pathname === '/api/health/ready') return json({ status: 'ready' })
    if (request.method() !== 'GET') report.interceptedWrites += 1
    return json({ items: [] })
  })

  async function axeAndOverflow(label) {
    await page.addScriptTag({ path: axePath })
    const result = await page.evaluate(async () => ({
      violations: (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } })).violations.map(item => ({ id: item.id, impact: item.impact, nodes: item.nodes.length })),
      overflow: document.documentElement.scrollWidth > innerWidth,
    }))
    report.checks.push({ label, ...result })
    assert.deepEqual(result.violations, [], `${label}: axe violations`)
    assert.equal(result.overflow, false, `${label}: horizontal overflow`)
  }

  await page.goto(`${base}/app/automation/today`)
  await page.getByRole('heading', { name: 'Automatisation — Aujourd’hui' }).waitFor()
  await page.getByRole('heading', { name: 'Données CRM en direct' }).waitFor()
  await page.getByRole('textbox', { name: 'Votre demande' }).fill('Montre-moi les prospects ouverts')
  await page.getByRole('button', { name: 'Préparer un plan' }).click()
  await page.getByRole('heading', { name: 'Plan proposé' }).waitFor()
  await page.getByRole('heading', { name: 'Éléments CRM du plan' }).waitFor()
  await axeAndOverflow('desktop/fr-CA/plan-ready')

  await page.getByRole('textbox', { name: 'Votre demande' }).fill('Aide-moi')
  await page.getByRole('button', { name: 'Préparer un plan' }).click()
  await page.getByRole('heading', { name: 'Précisez votre demande' }).waitFor()
  await axeAndOverflow('desktop/fr-CA/clarification')

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await page.getByRole('heading', { name: 'Automatisation — Aujourd’hui' }).waitFor()
  await page.getByRole('textbox', { name: 'Votre demande' }).fill('prospect')
  await page.getByRole('listbox', { name: 'Suggestions guidées' }).waitFor()
  await page.keyboard.press('Enter')
  assert.equal(await page.getByRole('textbox', { name: 'Votre demande' }).inputValue(), 'Montre-moi les prospects ouverts')
  await axeAndOverflow('mobile/fr-CA/autocomplete')

  await page.getByRole('textbox', { name: 'Votre demande' }).fill('Delete my prospects')
  await page.getByRole('button', { name: 'Préparer un plan' }).click()
  await page.getByRole('heading', { name: 'Cette demande n’est pas prise en charge dans IMP-A5.' }).waitFor()
  await axeAndOverflow('mobile/fr-CA/unsupported')

  organization.locale = 'en-CA'
  await page.reload()
  await page.getByRole('heading', { name: 'Automation — Today' }).waitFor()
  await page.getByRole('textbox', { name: 'Your request' }).fill('Delete my prospects')
  await page.getByRole('button', { name: 'Prepare a plan' }).click()
  await page.getByRole('heading', { name: 'This request is not supported in IMP-A5.' }).waitFor()
  await axeAndOverflow('mobile/en-CA/unsupported')
  assert.deepEqual(errors, [], `Browser errors: ${errors.join('; ')}`)
  assert.equal(report.interceptedWrites, 0, 'The browser recipe must not perform CRM writes')
  report.verdict = 'PASS'
  console.log(`AUT-AUTO-06 browser PASS — ${report.checks.length} desktop/mobile, bilingual and axe checks.`)
} catch (error) {
  report.failures.push({ type: 'browser', error: error?.stack || error?.message || String(error) })
  report.verdict = 'FAIL'
  console.error(`AUT-AUTO-06 browser FAIL — ${error.message}`)
  process.exitCode = 1
} finally {
  report.finishedAt = new Date().toISOString()
  mkdirSync(dirname(reportPath), { recursive: true })
  writeFileSync(reportPath, JSON.stringify(report, null, 2), 'utf8')
  await browser.close()
}

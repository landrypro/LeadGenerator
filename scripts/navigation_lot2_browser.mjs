// Run against `vite preview`; API calls are intercepted with deterministic data.
// node scripts/navigation_lot2_browser.mjs <path-to-playwright> [preview-url]
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require(process.argv[2] || 'playwright')
const axePath = require.resolve('axe-core/axe.min.js', { paths: [fileURLToPath(new URL('../client', import.meta.url))] })
const base = process.argv[3] || 'http://127.0.0.1:4178'
const capabilities = ['dashboard:read:self', 'tasks:read', 'prospects:read', 'pipeline:read', 'opportunities:read', 'google:search', 'providers:read', 'usage:read:self', 'retention:read', 'imports:read', 'exports:create:self', 'audit:read', 'organization:read', 'members:read']
const org = { id: 'nav-org', name: 'Entreprise navigation au nom volontairement très long', locale: 'fr-CA' }
const user = { id: 'nav-user', display_name: 'Camille Navigation Très Longue', email: 'navigation@example.test', platform_role: null }
let session = { user, active_organization: org, memberships: [{ id: 'nav-member', role: 'admin', organization: org }], capabilities, csrf_token: 'synthetic' }
const dashboardSummary = {
  period: { start_on: '2026-09-01', end_on: '2026-09-30', timezone: 'America/Toronto' },
  as_of: '2026-09-23T16:00:00Z', prospects_by_stage: [], tasks: { due_today: 0, overdue: 0 },
  activities_by_type: [], stage_passage: [], stage_losses: [], opportunities: { open: 0, won: 0, lost: 0 },
  pipeline_by_currency: [], owner_breakdown: null, google_usage: { status: 'unavailable', used: null },
}

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text())
  })
  await page.route('**/api/**', route => {
    const pathname = new URL(route.request().url()).pathname
    const body = pathname.endsWith('/auth/me') ? session
      : pathname === '/api/dashboard/summary' ? dashboardSummary
        : { items: [], total: 0 }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })

  await page.goto(`${base}/app/account`)
  await page.getByRole('heading', { name: 'Mon compte', exact: true }).waitFor()
  const mobile = page.getByRole('navigation', { name: 'Navigation mobile' })
  assert.deepEqual(await mobile.locator('a, button').allTextContents(), ['Accueil', 'Tâches', 'Prospects', 'Pipeline', 'Plus'])
  assert.equal(await page.getByRole('button', { name: 'Menu', exact: true }).isVisible(), false)
  assert.equal(await page.locator('.active-organization').isVisible(), true)
  assert.equal(await page.locator('.authenticated-account-menu > summary').isVisible(), true)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'No 390px horizontal overflow')
  assert.equal(await page.locator('#route-content').evaluate(node => parseFloat(getComputedStyle(node).paddingBottom) >= 66), true, 'Content clears bottom bar')

  const more = page.getByRole('button', { name: 'Plus', exact: true })
  await more.click()
  const dialog = page.getByRole('dialog', { name: 'Navigation' })
  assert.equal(await dialog.evaluate(node => node.matches(':modal')), true, 'Navigation uses a native modal dialog')
  assert.equal(await page.getByRole('button', { name: 'Fermer la navigation' }).evaluate(node => node === document.activeElement), true, 'Close receives focus')
  assert.equal(await page.evaluate(() => {
    document.querySelector('#route-content').focus()
    return document.querySelector('#primary-navigation').contains(document.activeElement)
  }), true, 'Background is inert while modal is open')
  await page.addScriptTag({ path: axePath })
  const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } })).violations.map(item => item.id))
  assert.deepEqual(violations, [], `Axe violations: ${violations.join(', ')}`)
  await page.screenshot({ path: 'test-results/navigation-lot2-mobile.png', fullPage: true })

  await page.evaluate(() => history.back())
  await dialog.waitFor({ state: 'hidden' })
  assert.equal(await more.evaluate(node => node === document.activeElement), true, 'Back restores focus to More')
  await more.click()
  await page.keyboard.press('Escape')
  await dialog.waitFor({ state: 'hidden' })
  assert.equal(await more.evaluate(node => node === document.activeElement), true, 'Escape restores focus to More')
  await more.click()
  await dialog.getByRole('link', { name: 'Tableau de bord', exact: true }).click()
  await page.waitForFunction(() => location.pathname === '/app/dashboard')
  await page.goBack()
  await page.waitForFunction(() => location.pathname === '/app/account')
  await page.goto(`${base}/app/account`)
  await page.getByRole('heading', { name: 'Mon compte', exact: true }).waitFor()

  for (const width of [320, 360, 390, 600, 640, 768, 1024, 1280, 1400, 1440]) {
    await page.setViewportSize({ width, height: width === 320 ? 568 : 844 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `No overflow at ${width}px`)
    assert.equal(await page.getByRole('button', { name: 'Menu', exact: true }).isVisible(), width > 600 && width < 1400, `Menu visibility at ${width}px`)
    assert.equal(await mobile.isVisible(), width <= 600, `Bottom navigation visibility at ${width}px`)
  }

  await page.setViewportSize({ width: 844, height: 390 })
  const topMenu = page.getByRole('button', { name: 'Menu', exact: true })
  await topMenu.click()
  assert.equal(await dialog.evaluate(node => node.getBoundingClientRect().height <= innerHeight), true, 'Landscape drawer stays inside dynamic viewport')
  assert.equal(await page.getByRole('button', { name: 'Fermer la navigation' }).isVisible(), true)
  await page.keyboard.press('Escape')

  await page.setViewportSize({ width: 390, height: 500 })
  await page.goto(`${base}/app/search`)
  await page.getByRole('heading', { name: 'Recherche d’établissements', exact: true }).waitFor()
  assert.equal(await page.locator('.authenticated-mobile-navigation').evaluate(node => Number(getComputedStyle(node).zIndex)), 35)
  assert.equal(await page.locator('.sidebar').evaluate(node => Number(getComputedStyle(node).zIndex || 0) >= 50), true, 'Google settings overlay stays above bottom navigation')

  session = { ...session, active_organization: { ...org, locale: 'en-CA' } }
  await page.goto(`${base}/app/account`)
  await page.getByRole('heading', { name: 'My account', exact: true }).waitFor()
  assert.deepEqual(await page.getByRole('navigation', { name: 'Mobile navigation' }).locator('a, button').allTextContents(), ['Home', 'Tasks', 'Prospects', 'Pipeline', 'More'])

  session = { ...session, active_organization: org, capabilities: ['tasks:read', 'prospects:read'] }
  await page.reload()
  assert.deepEqual(await page.getByRole('navigation', { name: 'Navigation mobile' }).locator('a, button').allTextContents(), ['Tâches', 'Prospects', 'Plus'])

  session = { ...session, user: { ...user, platform_role: 'platform_admin' }, active_organization: null, memberships: [], capabilities: ['platform:organizations:read', 'platform:audit:read'] }
  await page.reload()
  const platformMore = page.getByRole('button', { name: 'Plus', exact: true })
  assert.deepEqual(await page.getByRole('navigation', { name: 'Navigation mobile' }).locator('a, button').allTextContents(), ['Plus'])
  await platformMore.click()
  assert.equal(await page.getByRole('link', { name: 'Plateforme', exact: true }).isVisible(), true)
  assert.equal(await page.getByRole('link', { name: 'Audit plateforme', exact: true }).isVisible(), true)
  assert.deepEqual(errors, [])
  console.log('NAV-L2 browser PASS — breakpoints, long labels, FR/EN, rights, modal/inert, Back/Escape, orientation, Google stacking and safe spacing.')
} finally {
  await browser.close()
}

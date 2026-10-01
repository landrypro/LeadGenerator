// Run against `vite preview`; every API call is intercepted with synthetic data.
// node scripts/navigation_lot1_browser.mjs <path-to-playwright> [preview-url]
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { chromium } = require(process.argv[2] || 'playwright')
const base = process.argv[3] || 'http://127.0.0.1:4178'
const capabilities = ['dashboard:read:self', 'tasks:read', 'prospects:read', 'pipeline:read', 'opportunities:read', 'google:search', 'providers:read', 'usage:read:self', 'retention:read', 'imports:read', 'exports:create:self', 'audit:read', 'organization:read', 'members:read']
const org = { id: 'nav-org', name: 'Entreprise navigation', locale: 'fr-CA' }
const user = { id: 'nav-user', display_name: 'Camille', email: 'navigation@example.test', platform_role: null }
let session = { user, active_organization: org, memberships: [{ id: 'nav-member', role: 'admin', organization: org }], capabilities, csrf_token: 'synthetic' }
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/**', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(route.request().url().endsWith('/auth/me') ? session : { items: [] }) }))
  await page.goto(`${base}/app/account`)
  await page.getByRole('heading', { name: 'Mon compte', exact: true }).waitFor()
  assert.deepEqual(await page.locator('.authenticated-navigation > a').allTextContents(), ['Tableau de bord', 'Mes tâches', 'Prospects', 'Pipeline', 'Opportunités'])
  const acquisition = page.locator('.authenticated-navigation summary').filter({ hasText: 'Acquisition' })
  await acquisition.click()
  assert.equal(await page.getByRole('link', { name: 'Recherche d’établissements', exact: true }).isVisible(), true)
  await page.keyboard.press('Escape')
  assert.equal(await acquisition.evaluate(node => node === document.activeElement), true)
  assert.equal(await acquisition.evaluate(node => node.parentElement.open), false)
  await page.locator('.authenticated-account-menu summary').click()
  await page.getByRole('link', { name: 'Compte', exact: true }).click()
  await page.waitForTimeout(80)
  assert.equal(await page.locator('#route-content').evaluate(node => node === document.activeElement), true)
  for (const width of [1440, 1280, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Overflow ${width}`)
    if (width < 1400) {
      const trigger = width <= 600
        ? page.getByRole('button', { name: 'Plus', exact: true })
        : page.getByRole('button', { name: 'Menu', exact: true })
      await trigger.click()
      await page.locator('.authenticated-navigation-dialog summary').filter({ hasText: 'Acquisition' }).click()
      assert.equal(await page.getByRole('link', { name: 'Recherche d’établissements', exact: true }).isVisible(), true)
      await page.getByRole('button', { name: 'Fermer la navigation', exact: true }).click()
    }
  }
  await page.setViewportSize({ width: 1600, height: 1000 })
  session = { ...session, active_organization: { ...org, locale: 'en-CA' } }
  await page.reload()
  await page.getByRole('heading', { name: 'My account', exact: true }).waitFor()
  await page.locator('summary').filter({ hasText: 'Data and audit' }).click()
  assert.equal(await page.getByRole('link', { name: 'CSV exports', exact: true }).isVisible(), true)
  session = { ...session, user: { ...user, platform_role: 'platform_admin' }, active_organization: null, memberships: [], capabilities: ['platform:organizations:read', 'platform:audit:read'] }
  await page.reload()
  await page.locator('.authenticated-navigation a').first().waitFor()
  assert.equal(await page.locator('.authenticated-navigation > a').count(), 2)
  assert.equal(await page.locator('.authenticated-navigation a[href="/app/platform/audit"]').isVisible(), true)
  assert.equal(await page.locator('.organization-switcher').count(), 0)
  session = { ...session, user, capabilities: [] }
  await page.goto(`${base}/`)
  await page.getByRole('link', { name: /^(Compte|Account)$/ }).click()
  await page.locator('.account-page').waitFor()
  assert.equal(await page.locator('.authenticated-navigation a').count(), 0)
  assert.deepEqual(errors, [])
  console.log('NAV-L1 browser PASS — categories, focus, widths, EN, platform audit, account without organization; API mocked.')
} finally {
  await browser.close()
}

// Run against `vite preview`; API calls are intercepted with deterministic data.
// node scripts/navigation_lot3_browser.mjs <path-to-playwright> [preview-url]
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require(process.argv[2] || 'playwright')
const axePath = require.resolve('axe-core/axe.min.js', { paths: [fileURLToPath(new URL('../client', import.meta.url))] })
const base = process.argv[3] || 'http://127.0.0.1:4178'
const organization = { id: 'lot3-org', name: 'Entreprise recette recherche mobile', locale: 'fr-CA' }
const session = {
  user: { id: 'lot3-user', display_name: 'Recette mobile', email: 'recette@example.test', platform_role: null },
  active_organization: organization,
  memberships: [{ id: 'lot3-membership', role: 'admin', organization }],
  capabilities: ['google:search', 'google:map', 'prospects:create', 'organization:read'],
  csrf_token: 'synthetic',
}
const searchResult = {
  places: [
    { place_id: 'lot3-place-1', name: 'Plomberie Boréale', address: 'Québec', primary_type: 'plumber', business_status: 'OPERATIONAL', radius_verified: true, distance_km: 1.2 },
    { place_id: 'lot3-place-2', name: 'Plomberie du Fleuve', address: 'Québec', primary_type: 'plumber', business_status: 'OPERATIONAL', radius_verified: true, distance_km: 2.4 },
  ],
  stats: { api_calls: 1, raw_results: 2, displayed_results: 2 },
  searched_at: '2026-09-25T20:00:00Z', selection_token: 'lot3-selection-token-long-enough',
  search_parameters: { query: 'plombier', center_latitude: 46.8139, center_longitude: -71.208, radius_km: 15, include_service_area_businesses: true, language_code: 'fr', region_code: 'CA' },
}

const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } })
  const errors = []
  let addCalls = 0
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text())
  })
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.endsWith('/auth/me')) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(session) })
    if (pathname === '/api/health') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ google_api_key_configured: true }) })
    if (pathname === '/api/google/places/search') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(searchResult) })
    if (pathname === '/api/prospects/from-google') {
      addCalls += 1
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [{ place_id: 'lot3-place-1', disposition: 'created', prospect: { internal_alias: 'Plomberie Nord' } }] }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ items: [] }) })
  })

  await page.goto(`${base}/app/search`)
  await page.getByRole('heading', { name: 'Recherche d’établissements', exact: true }).waitFor()
  const settingsTrigger = page.getByRole('button', { name: 'Ouvrir les paramètres de recherche' })
  await settingsTrigger.click()
  const dialog = page.getByRole('dialog', { name: 'Paramètres' })
  await dialog.waitFor()
  assert.equal(await page.locator('main.main-content').getAttribute('inert'), '', 'Search content is inert behind its mobile panel')
  assert.equal(await page.locator('.authenticated-header').getAttribute('inert'), '', 'Global header is inert behind its mobile panel')
  await dialog.getByRole('button', { name: /Coordonnées avancées/i }).click()
  await dialog.getByRole('button', { name: 'Rechercher des établissements' }).click()
  await page.getByText('Plomberie Boréale', { exact: true }).waitFor()
  assert.equal(await page.getByText('Recherche appliquée', { exact: true }).isVisible(), true)
  assert.equal(await page.locator('.search-workspace .overview-grid').isVisible(), false, 'Map is secondary after a mobile search')
  await page.getByRole('button', { name: 'Voir la carte' }).click()
  assert.equal(await page.locator('.search-workspace .overview-grid').isVisible(), true, 'Map opens on demand')

  await settingsTrigger.click()
  await dialog.getByRole('textbox', { name: 'Type d’entreprise' }).fill('électricien')
  assert.equal(await dialog.getByText(/Brouillon :/).isVisible(), true)
  await dialog.getByRole('button', { name: 'Fermer les paramètres' }).click()
  await settingsTrigger.click()
  assert.equal(await dialog.getByRole('textbox', { name: 'Type d’entreprise' }).inputValue(), 'électricien', 'Close preserves draft')
  await dialog.getByRole('button', { name: 'Annuler' }).click()
  await settingsTrigger.click()
  assert.equal(await dialog.getByRole('textbox', { name: 'Type d’entreprise' }).inputValue(), 'plombier', 'Cancel restores applied parameters')
  await page.keyboard.press('Escape')
  await page.waitForFunction(() => document.activeElement === document.querySelector('.mobile-controls-button'))
  assert.equal(await settingsTrigger.evaluate(node => node === document.activeElement), true, 'Escape restores focus')

  await page.getByRole('checkbox', { name: 'Sélectionner Plomberie Boréale' }).check()
  const selectAll = page.getByRole('checkbox', { name: 'Sélectionner les résultats affichés' })
  assert.equal(await selectAll.evaluate(node => node.indeterminate), true, 'Partial selection is exposed')
  await page.getByRole('button', { name: 'Ajouter la sélection' }).click()
  assert.equal(await page.getByLabel('Nom interne CRM pour Plomberie Boréale').evaluate(node => node === document.activeElement), true, 'Missing CRM alias receives focus')
  assert.equal(addCalls, 0, 'No CRM write without internal alias')
  await page.getByLabel('Nom interne CRM pour Plomberie Boréale').fill('Plomberie Nord')
  await page.getByRole('button', { name: 'Ajouter la sélection' }).click()
  await page.getByRole('button', { name: 'Ajouté' }).waitFor()
  assert.equal(addCalls, 1, 'Selected business is added after explicit alias entry')

  await page.addScriptTag({ path: axePath })
  const violations = await page.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] } })).violations.map(item => item.id))
  assert.deepEqual(violations, [], `Axe violations: ${violations.join(', ')}`)
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'No mobile horizontal overflow')
  await page.screenshot({ path: 'test-results/navigation-lot3-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log('NAV-L3 browser PASS — applied/draft settings, modal inertness, map on demand, selection, explicit CRM alias and mobile accessibility.')
} finally {
  await browser.close()
}

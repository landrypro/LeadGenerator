import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BillingPage } from './BillingPage'
import { billingApi } from './api/billingApi'

vi.mock('./api/billingApi', () => ({ billingApi: {
  currentCatalog: vi.fn(), subscription: vi.fn(), checkoutOptions: vi.fn(),
  createCheckout: vi.fn(), resumeCheckout: vi.fn(),
} }))

const PLAN = '12345678-1234-4234-8234-123456789abc'
const OFFER = { id: PLAN, code: 'starter', version_number: 1, currency: 'CAD', amount_minor: 2500, billing_cycle: 'monthly' }
const SESSION = { active_organization: { id: 'org-1', locale: 'fr-CA' }, capabilities: ['billing:manage'] }

describe('BillingPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/app/billing')
    window.sessionStorage.clear()
    billingApi.subscription.mockReset().mockResolvedValue({ contract: null, subscription: null, checkout: null, command: null })
    billingApi.checkoutOptions.mockReset().mockResolvedValue({ options: [OFFER] })
    billingApi.createCheckout.mockReset()
    billingApi.resumeCheckout.mockReset()
  })

  it('affiche l’absence de contrat et déclenche le Checkout sandbox après confirmation', async () => {
    billingApi.createCheckout.mockResolvedValue({
      url: 'https://checkout.stripe.com/c/pay/cs_test_example', expires_at: '2026-10-26T12:00:00Z',
    })
    const navigateToCheckout = vi.fn()
    render(<BillingPage session={SESSION} navigateToCheckout={navigateToCheckout} />)
    await screen.findByText('Aucun forfait confirmé.')
    const offer = await screen.findByRole('option', { name: /starter.*25.*CAD.*v1/i })
    fireEvent.change(screen.getByRole('combobox', { name: 'Offre de test' }), { target: { value: offer.value } })
    fireEvent.click(screen.getByRole('button', { name: 'Voir le détail' }))
    expect(screen.getByText(/Aucune conversion de devise/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer et ouvrir Checkout test' }))
    await waitFor(() => expect(navigateToCheckout).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/cs_test_example'))
    expect(billingApi.createCheckout).toHaveBeenCalledWith(PLAN, expect.any(String))
  })

  it('conserve la clé d’idempotence lors d’une reprise après une erreur réseau', async () => {
    billingApi.createCheckout.mockRejectedValueOnce(new Error('Réseau indisponible'))
      .mockResolvedValueOnce({ url: 'https://checkout.stripe.com/c/pay/cs_test_retry' })
    const navigateToCheckout = vi.fn()
    render(<BillingPage session={SESSION} navigateToCheckout={navigateToCheckout} />)
    await screen.findByRole('option', { name: /starter/i })
    fireEvent.change(screen.getByRole('combobox', { name: 'Offre de test' }), { target: { value: PLAN } })
    fireEvent.click(screen.getByRole('button', { name: 'Voir le détail' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer et ouvrir Checkout test' }))
    await screen.findByRole('alert')
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer et ouvrir Checkout test' }))
    await waitFor(() => expect(navigateToCheckout).toHaveBeenCalledTimes(1))
    expect(billingApi.createCheckout.mock.calls[0][1]).toBe(billingApi.createCheckout.mock.calls[1][1])
  })

  it('refuse une destination Checkout étrangère', async () => {
    const navigateToCheckout = vi.fn()
    billingApi.createCheckout.mockResolvedValue({ url: 'https://example.invalid/checkout' })
    render(<BillingPage session={SESSION} navigateToCheckout={navigateToCheckout} />)
    await screen.findByRole('option', { name: /starter/i })
    fireEvent.change(screen.getByRole('combobox', { name: 'Offre de test' }), { target: { value: PLAN } })
    fireEvent.click(screen.getByRole('button', { name: 'Voir le détail' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer et ouvrir Checkout test' }))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('réponse Checkout reçue est invalide'))
    expect(navigateToCheckout).not.toHaveBeenCalled()
  })

  it('explique l’absence d’offres et bloque Checkout', async () => {
    billingApi.checkoutOptions.mockResolvedValue({ options: [] })
    render(<BillingPage session={SESSION} />)
    expect(await screen.findByText(/Aucune offre de test disponible/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Voir le détail' })).toBeDisabled()
    expect(billingApi.createCheckout).not.toHaveBeenCalled()
  })

  it('permet de recharger les offres après une erreur réseau', async () => {
    billingApi.checkoutOptions.mockRejectedValueOnce(new Error('Réseau indisponible'))
      .mockResolvedValueOnce({ options: [OFFER] })
    render(<BillingPage session={SESSION} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Réseau indisponible')
    expect(screen.getByRole('button', { name: 'Voir le détail' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('option', { name: /starter/i })).toBeInTheDocument()
    expect(billingApi.checkoutOptions).toHaveBeenCalledTimes(2)
  })

  it('affiche XAF sans conversion de centimes', async () => {
    billingApi.checkoutOptions.mockResolvedValue({ options: [{ ...OFFER, currency: 'XAF', amount_minor: 1234 }] })
    render(<BillingPage session={SESSION} />)
    const option = await screen.findByRole('option', { name: /starter/i })
    expect(option.textContent).toMatch(/1.?234/)
    expect(option.textContent).not.toContain('12,34')
  })

  it('ne prétend pas que le retour Checkout confirme l’abonnement', () => {
    window.history.replaceState({}, '', '/app/billing?checkout=success')
    render(<BillingPage session={SESSION} />)
    expect(screen.getByText(/Vérification de la confirmation du paiement/)).toBeInTheDocument()
  })

  it('bloque un nouveau paiement quand un abonnement est déjà confirmé', async () => {
    billingApi.subscription.mockResolvedValue({
      contract: { currency: 'CAD', state: 'active', plan_code: 'starter', version_number: 1 }, checkout: null, command: null,
      subscription: { state: 'active', provider: 'stripe', currency: 'CAD', plan_code: 'starter', version_number: 1,
        current_period_end: '2026-12-01T00:00:00Z' },
    })
    render(<BillingPage session={SESSION} />)
    expect(await screen.findByText('Paiement confirmé')).toBeInTheDocument()
    expect(screen.getByText('starter · v1 · CAD')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Voir le détail' })).not.toBeInTheDocument()
    expect(billingApi.createCheckout).not.toHaveBeenCalled()
  })

  it('reprend une session existante sans créer de nouveau Checkout', async () => {
    billingApi.subscription.mockResolvedValue({
      contract: { currency: 'CAD', state: 'pending', plan_code: 'starter', version_number: 1 }, subscription: null, command: null,
      checkout: { state: 'open', currency: 'CAD', expires_at: '2026-12-01T00:00:00Z' },
    })
    billingApi.resumeCheckout.mockResolvedValue({ url: 'https://checkout.stripe.com/c/pay/cs_test_resume' })
    const navigateToCheckout = vi.fn()
    render(<BillingPage session={SESSION} navigateToCheckout={navigateToCheckout} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Reprendre la session Checkout' }))
    await waitFor(() => expect(navigateToCheckout).toHaveBeenCalledTimes(1))
    expect(billingApi.createCheckout).not.toHaveBeenCalled()
  })

  it('bloque Checkout si l’état serveur est indisponible', async () => {
    billingApi.subscription.mockRejectedValue(new Error('État indisponible'))
    render(<BillingPage session={SESSION} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('État indisponible')
    expect(screen.queryByRole('button', { name: 'Voir le détail' })).not.toBeInTheDocument()
  })
})

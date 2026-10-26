import { useEffect, useRef, useState } from 'react'

import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { createRequestId } from '../../shared/ids/requestId'
import { billingApi } from './api/billingApi'
import './billing.css'


const COPY = {
  'fr-CA': {
    title: 'Facturation', intro: 'Créer une session Checkout pour la recette Stripe sandbox.',
    sandbox: 'Environnement de test', sandboxDetail: 'Utilisez uniquement des prix et des moyens de paiement fictifs.',
    plan: 'Offre de test', planHelp: 'Choisissez une offre mensuelle publiée. Le prix Stripe est vérifié lors de la création de la session.',
    current: 'Contrat courant', noContract: 'Aucun contrat courant.',
    choose: 'Choisir une offre', loading: 'Chargement des offres…',
    empty: 'Aucune offre de test disponible. Un administrateur plateforme doit publier un plan et une version mensuelle avec un prix fictif configuré.',
    loadError: 'Impossible de charger les offres de test.', retry: 'Réessayer',
    submit: 'Ouvrir Checkout test', submitting: 'Création de la session…', invalid: 'Choisissez une offre de test.',
    unavailable: 'La réponse Checkout reçue est invalide.',
    success: 'Retour de Checkout reçu. La confirmation de l’abonnement dépend encore du webhook Stripe.',
    cancel: 'Checkout annulé. Aucun paiement n’a été confirmé par ce retour.',
    continue: 'Ouvrir la session Checkout', expires: 'Session valable jusqu’au',
  },
  'en-CA': {
    title: 'Billing', intro: 'Create a Checkout session for Stripe sandbox testing.',
    sandbox: 'Test environment', sandboxDetail: 'Use only fictitious prices and test payment methods.',
    plan: 'Test offer', planHelp: 'Choose a published monthly offer. The Stripe price is checked when the session is created.',
    current: 'Current contract', noContract: 'No current contract.',
    choose: 'Choose an offer', loading: 'Loading offers…',
    empty: 'No test offer is available. A platform administrator must publish a plan and monthly version with a configured test price.',
    loadError: 'Unable to load test offers.', retry: 'Try again',
    submit: 'Open test Checkout', submitting: 'Creating session…', invalid: 'Choose a test offer.',
    unavailable: 'The Checkout response is invalid.',
    success: 'Checkout returned. The subscription still awaits confirmation by a Stripe webhook.',
    cancel: 'Checkout was canceled. This return did not confirm a payment.',
    continue: 'Open Checkout session', expires: 'Session valid until',
  },
}

function stripeCheckoutUrl(value) {
  try {
    const url = new URL(value)
    return url.origin === 'https://checkout.stripe.com' && !url.username && !url.password ? url.href : null
  } catch {
    return null
  }
}

function optionLabel(option, locale) {
  const amount = option.currency === 'XAF' ? option.amount_minor : option.amount_minor / 100
  const price = new Intl.NumberFormat(locale, { style: 'currency', currency: option.currency, currencyDisplay: 'code' }).format(amount)
  return `${option.code} · ${price} / ${locale === 'en-CA' ? 'month' : 'mois'} · v${option.version_number}`
}

export function BillingPage({ session, navigateToCheckout = (url) => window.location.assign(url) }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const [planVersionId, setPlanVersionId] = useState('')
  const [options, setOptions] = useState([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [optionsError, setOptionsError] = useState('')
  const [optionsReload, setOptionsReload] = useState(0)
  const [contract, setContract] = useState(null)
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [checkout, setCheckout] = useState(null)
  const pendingRef = useRef(false)
  const commandRef = useRef(null)
  const returnStatus = new URLSearchParams(window.location.search).get('checkout')

  useEffect(() => {
    const controller = new AbortController()
    billingApi.currentCatalog(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setContract(data.contract)
      })
      .catch(() => {}) // The contract is a convenience; an explicit plan version remains usable.
      .finally(() => { if (!controller.signal.aborted) setLoadingCatalog(false) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    billingApi.checkoutOptions(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setOptions(data.options)
        setOptionsError('')
      })
      .catch(requestError => {
        if (!controller.signal.aborted) setOptionsError(toUserMessage(requestError, copy.loadError))
      })
      .finally(() => { if (!controller.signal.aborted) setLoadingOptions(false) })
    return () => controller.abort()
  }, [optionsReload, copy.loadError])

  function updatePlan(value) {
    setPlanVersionId(value)
    setError('')
    setCheckout(null)
    commandRef.current = null
  }

  async function submit(event) {
    event.preventDefault()
    if (pendingRef.current) return
    const plan = planVersionId
    if (!options.some(option => option.id === plan)) { setError(copy.invalid); return }
    pendingRef.current = true
    setSubmitting(true)
    setError('')
    const key = commandRef.current?.plan === plan ? commandRef.current.key : createRequestId()
    commandRef.current = { plan, key }
    try {
      const response = await billingApi.createCheckout(plan, key)
      const url = stripeCheckoutUrl(response.url)
      if (!url) throw new Error(copy.unavailable)
      setCheckout({ url, expiresAt: response.expires_at })
      navigateToCheckout(url)
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.unavailable))
    } finally {
      pendingRef.current = false
      setSubmitting(false)
    }
  }

  return <main className="administration-page billing-page" aria-labelledby="billing-title">
    <header className="administration-page-heading">
      <p className="eyebrow">Marketteo CRM</p>
      <h1 id="billing-title">{copy.title}</h1>
      <p>{copy.intro}</p>
    </header>

    <div className="billing-sandbox-notice" role="note">
      <strong>{copy.sandbox}</strong><span>{copy.sandboxDetail}</span>
    </div>

    {returnStatus === 'success' && <p className="billing-return-notice" role="status">{copy.success}</p>}
    {returnStatus === 'cancel' && <p className="billing-return-notice" role="status">{copy.cancel}</p>}

    <section className="administration-card billing-card" aria-labelledby="billing-checkout-title">
      <h2 id="billing-checkout-title">Checkout Stripe</h2>
      {contract ? <p className="billing-contract">
        <span>{copy.current} : {contract.currency} · {contract.state}</span>
      </p> : !loadingCatalog && <p className="account-note">{copy.noContract}</p>}
      <form onSubmit={submit} className="billing-form">
        <label htmlFor="billing-plan-version">{copy.plan}</label>
        <select id="billing-plan-version" value={planVersionId} onChange={event => updatePlan(event.target.value)}
          required disabled={loadingOptions || options.length === 0} aria-describedby="billing-plan-help">
          <option value="">{copy.choose}</option>
          {options.map(option => <option key={option.id} value={option.id}>{optionLabel(option, locale)}</option>)}
        </select>
        <p id="billing-plan-help" className="form-help">{copy.planHelp}</p>
        {loadingOptions && <p className="account-note" role="status">{copy.loading}</p>}
        {optionsError && <div className="billing-options-error"><ErrorBanner>{optionsError}</ErrorBanner>
          <button type="button" className="secondary-button" onClick={() => { setLoadingOptions(true); setOptionsError(''); setOptionsReload(value => value + 1) }}>{copy.retry}</button>
        </div>}
        {!loadingOptions && !optionsError && options.length === 0 && <p className="billing-empty" role="status">{copy.empty}</p>}
        {error && <ErrorBanner>{error}</ErrorBanner>}
        <button className="primary-button" type="submit" disabled={submitting || loadingOptions || options.length === 0}>
          {submitting ? copy.submitting : copy.submit}
        </button>
      </form>
      {checkout && <p className="billing-checkout-link">
        <a href={checkout.url} rel="noopener noreferrer">{copy.continue}</a>
        {checkout.expiresAt && <small>{copy.expires} {new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(checkout.expiresAt))}</small>}
      </p>}
    </section>
  </main>
}

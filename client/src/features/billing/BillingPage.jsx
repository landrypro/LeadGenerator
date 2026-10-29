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
    current: 'État du forfait', noContract: 'Aucun forfait confirmé.',
    choose: 'Choisir une offre', loading: 'Chargement des offres…',
    empty: 'Aucune offre de test disponible. Un administrateur plateforme doit publier un plan et une version mensuelle avec un prix fictif configuré.',
    loadError: 'Impossible de charger les offres de test.', retry: 'Réessayer',
    submit: 'Ouvrir Checkout test', submitting: 'Création de la session…', invalid: 'Choisissez une offre de test.',
    unavailable: 'La réponse Checkout reçue est invalide.',
    success: 'Retour de Checkout reçu. Vérification de la confirmation du paiement par le serveur.',
    cancel: 'Retour de Checkout annulé. Vérifiez l’état ci-dessous avant de recommencer.',
    continue: 'Ouvrir la session Checkout', expires: 'Session valable jusqu’au',
    statusError: 'Impossible de vérifier l’état de la facturation.', statusLoading: 'Vérification de la facturation…',
    refresh: 'Actualiser l’état', select: 'Voir le détail', confirm: 'Confirmer et ouvrir Checkout test',
    review: 'Vous allez ouvrir Stripe Checkout pour cette offre fictive.',
    reviewNote: 'Le paiement et les droits ne seront confirmés qu’après vérification par le serveur. Aucune conversion de devise n’est effectuée.',
    resume: 'Reprendre la session Checkout', resumeLoading: 'Vérification de la session…',
    portal: 'Gérer la facturation', portalLoading: 'Ouverture du portail…',
    portalUnavailable: 'La réponse du portail de facturation est invalide.',
    pending: 'Paiement en attente de confirmation', preparing: 'Préparation du paiement à vérifier',
    expired: 'La session a expiré. Son état doit être rapproché avant un nouveau paiement.',
    active: 'Paiement confirmé', grace_period: 'Renouvellement à régulariser', canceling: 'Annulation programmée',
    suspended: 'Forfait suspendu', canceled: 'Abonnement terminé', pending_checkout: 'Paiement en attente',
    past_due: 'Paiement à régulariser', existing: 'Un forfait ou un paiement est déjà en cours. Aucun nouveau Checkout ne sera créé.',
    due: 'Période courante jusqu’au', graceUntil: 'Délai de régularisation jusqu’au',
    manualGrantActive: 'Accès sandbox temporaire accordé', manualGrantPending: 'Attribution sandbox en attente d’approbation',
    manualGrantNote: 'Cet accès ne correspond à aucun paiement ni abonnement Stripe.',
    manualGrantExisting: 'Un accès sandbox temporaire est en cours. Un administrateur plateforme doit le révoquer ou attendre son expiration avant un Checkout.',
  },
  'en-CA': {
    title: 'Billing', intro: 'Create a Checkout session for Stripe sandbox testing.',
    sandbox: 'Test environment', sandboxDetail: 'Use only fictitious prices and test payment methods.',
    plan: 'Test offer', planHelp: 'Choose a published monthly offer. The Stripe price is checked when the session is created.',
    current: 'Plan status', noContract: 'No confirmed plan.',
    choose: 'Choose an offer', loading: 'Loading offers…',
    empty: 'No test offer is available. A platform administrator must publish a plan and monthly version with a configured test price.',
    loadError: 'Unable to load test offers.', retry: 'Try again',
    submit: 'Open test Checkout', submitting: 'Creating session…', invalid: 'Choose a test offer.',
    unavailable: 'The Checkout response is invalid.',
    success: 'Checkout returned. The server is checking payment confirmation.',
    cancel: 'Checkout returned as canceled. Check the status below before trying again.',
    continue: 'Open Checkout session', expires: 'Session valid until',
    statusError: 'Unable to verify billing status.', statusLoading: 'Checking billing status…',
    refresh: 'Refresh status', select: 'Review offer', confirm: 'Confirm and open test Checkout',
    review: 'You are about to open Stripe Checkout for this fictitious offer.',
    reviewNote: 'Payment and access are confirmed only after server verification. No currency conversion is performed.',
    resume: 'Resume Checkout session', resumeLoading: 'Checking session…',
    portal: 'Manage billing', portalLoading: 'Opening billing portal…',
    portalUnavailable: 'The billing portal response is invalid.',
    pending: 'Payment awaiting confirmation', preparing: 'Payment preparation needs verification',
    expired: 'The session expired. Its status must be reconciled before another payment.',
    active: 'Payment confirmed', grace_period: 'Renewal payment needs attention', canceling: 'Cancellation scheduled',
    suspended: 'Plan suspended', canceled: 'Subscription ended', pending_checkout: 'Payment pending',
    past_due: 'Payment needs attention', existing: 'A plan or payment is already in progress. No new Checkout will be created.',
    due: 'Current period ends', graceUntil: 'Grace period ends',
    manualGrantActive: 'Temporary sandbox access granted', manualGrantPending: 'Sandbox grant awaiting approval',
    manualGrantNote: 'This access does not represent a Stripe payment or subscription.',
    manualGrantExisting: 'Temporary sandbox access is in progress. A platform administrator must revoke it or wait for it to expire before Checkout.',
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

function stripePortalUrl(value) {
  try {
    const url = new URL(value)
    return url.origin === 'https://billing.stripe.com' && !url.username && !url.password ? url.href : null
  } catch {
    return null
  }
}

function offerPrice(option, locale) {
  const amount = option.currency === 'XAF' ? option.amount_minor : option.amount_minor / 100
  return new Intl.NumberFormat(locale, { style: 'currency', currency: option.currency, currencyDisplay: 'code' }).format(amount)
}

function optionLabel(option, locale) {
  return `${option.code} · ${offerPrice(option, locale)} / ${locale === 'en-CA' ? 'month' : 'mois'} · v${option.version_number}`
}

function displayDate(value, locale) {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function BillingPage({ session, navigateToCheckout = (url) => window.location.assign(url) }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const organization = session.active_organization?.id || ''
  const copy = COPY[locale]
  const [planVersionId, setPlanVersionId] = useState('')
  const [options, setOptions] = useState([])
  const [loadingOptions, setLoadingOptions] = useState(true)
  const [optionsError, setOptionsError] = useState('')
  const [optionsReload, setOptionsReload] = useState(0)
  const [status, setStatus] = useState(null)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [statusError, setStatusError] = useState('')
  const [statusReload, setStatusReload] = useState(0)
  const [reviewing, setReviewing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [resuming, setResuming] = useState(false)
  const [openingPortal, setOpeningPortal] = useState(false)
  const [error, setError] = useState('')
  const [checkout, setCheckout] = useState(null)
  const pendingRef = useRef(false)
  const commandRef = useRef(null)
  const returnStatus = new URLSearchParams(window.location.search).get('checkout')

  useEffect(() => {
    const controller = new AbortController()
    billingApi.subscription(controller.signal)
      .then(data => {
        if (controller.signal.aborted) return
        setStatus(data)
        setStatusError('')
      })
      .catch(requestError => { if (!controller.signal.aborted) setStatusError(toUserMessage(requestError, copy.statusError)) })
      .finally(() => { if (!controller.signal.aborted) setLoadingStatus(false) })
    return () => controller.abort()
  }, [statusReload, copy.statusError, organization])

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
  }, [optionsReload, copy.loadError, organization])

  const subscription = status?.subscription
  const contract = status?.contract
  const pendingCheckout = status?.checkout
  const pendingCommand = status?.command
  const manualGrant = status?.manual_grant
  const hasCurrentSubscription = subscription && subscription.state !== 'canceled'
  const hasCurrentContract = contract && ['active', 'suspended'].includes(contract.state)
  const hasManualGrant = manualGrant && ['pending_approval', 'active'].includes(manualGrant.state)
  const canStart = Boolean(status && !statusError && !loadingStatus && !hasCurrentSubscription && !hasCurrentContract && !hasManualGrant && !pendingCheckout && !pendingCommand)
  const canResume = Boolean(pendingCheckout?.state === 'open' && !hasCurrentSubscription && !hasCurrentContract && !hasManualGrant)
  const canOpenPortal = Boolean(
    status?.portal_available && subscription && ['active', 'past_due', 'grace_period', 'suspended', 'canceling'].includes(subscription.state)
  )
  const chosen = options.find(option => option.id === planVersionId)
  const waitForConfirmation = Boolean(status && (pendingCheckout || pendingCommand || subscription?.state === 'pending_checkout' ||
    (returnStatus === 'success' && !['active', 'canceling', 'grace_period', 'suspended', 'canceled'].includes(subscription?.state))))

  useEffect(() => {
    if (!waitForConfirmation) return undefined
    const timer = window.setInterval(() => setStatusReload(value => value + 1), 5000)
    return () => window.clearInterval(timer)
  }, [waitForConfirmation])

  function updatePlan(value) {
    setPlanVersionId(value)
    setReviewing(false)
    setError('')
    setCheckout(null)
    commandRef.current = null
  }

  async function submit(event) {
    event.preventDefault()
    if (pendingRef.current || !canStart) return
    const plan = planVersionId
    if (!chosen) { setError(copy.invalid); return }
    if (!reviewing) { setReviewing(true); return }
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
      setStatusReload(value => value + 1)
      navigateToCheckout(url)
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.unavailable))
      setStatusReload(value => value + 1)
    } finally {
      pendingRef.current = false
      setSubmitting(false)
    }
  }

  async function resume() {
    if (pendingRef.current || !canResume) return
    pendingRef.current = true
    setResuming(true)
    setError('')
    try {
      const response = await billingApi.resumeCheckout()
      const url = stripeCheckoutUrl(response.url)
      if (!url) throw new Error(copy.unavailable)
      navigateToCheckout(url)
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.unavailable))
      setStatusReload(value => value + 1)
    } finally {
      pendingRef.current = false
      setResuming(false)
    }
  }

  async function openPortal() {
    if (pendingRef.current || !canOpenPortal) return
    pendingRef.current = true
    setOpeningPortal(true)
    setError('')
    try {
      const response = await billingApi.createPortal(createRequestId())
      const url = stripePortalUrl(response.url)
      if (!url) throw new Error(copy.portalUnavailable)
      navigateToCheckout(url)
    } catch (requestError) {
      setError(toUserMessage(requestError, copy.portalUnavailable))
      setStatusReload(value => value + 1)
    } finally {
      pendingRef.current = false
      setOpeningPortal(false)
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

    <section className="administration-card billing-card" aria-labelledby="billing-status-title">
      <h2 id="billing-status-title">{copy.current}</h2>
      {loadingStatus && <p role="status">{copy.statusLoading}</p>}
      {statusError && <ErrorBanner>{statusError}</ErrorBanner>}
      {status && !statusError && <div className="billing-state" role="status">
        {hasCurrentSubscription ? <>
          <strong>{copy[subscription.state] || copy.preparing}</strong>
          <span>{subscription.plan_code} · v{subscription.version_number} · {subscription.currency}</span>
          {subscription.current_period_end && <span>{copy.due} {displayDate(subscription.current_period_end, locale)}</span>}
          {subscription.grace_ends_at && <span>{copy.graceUntil} {displayDate(subscription.grace_ends_at, locale)}</span>}
        </> : manualGrant ? <>
          <strong>{manualGrant.state === 'active' ? copy.manualGrantActive : copy.manualGrantPending}</strong>
          <span>{manualGrant.plan_code} · v{manualGrant.version_number} · {manualGrant.currency}</span>
          {manualGrant.ends_at && <span>{copy.due} {displayDate(manualGrant.ends_at, locale)}</span>}
          <span>{copy.manualGrantNote}</span>
        </> : pendingCheckout ? <>
          <strong>{pendingCheckout.state === 'expired' ? copy.expired : copy.pending}</strong>
          <span>{pendingCheckout.currency} · {copy.expires} {displayDate(pendingCheckout.expires_at, locale)}</span>
        </> : pendingCommand ? <strong>{copy.preparing}</strong> : contract ? <>
          <strong>{copy[contract.state] || copy.preparing}</strong>
          <span>{contract.plan_code} · v{contract.version_number} · {contract.currency}</span>
        </> : <span>{copy.noContract}</span>}
      </div>}
      <div className="billing-actions">
        <button type="button" className="secondary-button" onClick={() => setStatusReload(value => value + 1)}>{copy.refresh}</button>
        {canResume && <button type="button" className="primary-button" onClick={resume} disabled={resuming}>
          {resuming ? copy.resumeLoading : copy.resume}</button>}
        {canOpenPortal && <button type="button" className="secondary-button" onClick={openPortal} disabled={openingPortal}>
          {openingPortal ? copy.portalLoading : copy.portal}</button>}
      </div>
    </section>

    {canStart ? <section className="administration-card billing-card" aria-labelledby="billing-checkout-title">
      <h2 id="billing-checkout-title">Checkout Stripe</h2>
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
        {reviewing && chosen && <div className="billing-review" role="group" aria-label={copy.review}>
          <strong>{chosen.code} · {offerPrice(chosen, locale)}</strong>
          <span>{locale === 'en-CA' ? 'Monthly billing' : 'Facturation mensuelle'} · v{chosen.version_number}</span>
          <p>{copy.reviewNote}</p>
        </div>}
        {error && <ErrorBanner>{error}</ErrorBanner>}
        <button className="primary-button" type="submit" disabled={submitting || loadingOptions || Boolean(optionsError) || options.length === 0}>
          {submitting ? copy.submitting : reviewing ? copy.confirm : copy.select}
        </button>
      </form>
      {checkout && <p className="billing-checkout-link">
        <a href={checkout.url} rel="noopener noreferrer">{copy.continue}</a>
        {checkout.expiresAt && <small>{copy.expires} {displayDate(checkout.expiresAt, locale)}</small>}
      </p>}
    </section> : status && !statusError && <p className="billing-existing" role="note">{hasManualGrant ? copy.manualGrantExisting : copy.existing}</p>}
    {error && !canStart && <ErrorBanner>{error}</ErrorBanner>}
  </main>
}

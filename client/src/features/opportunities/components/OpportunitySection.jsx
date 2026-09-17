import { useRef, useState } from 'react'

import { formatDate, formatMoney, OPPORTUNITY_STAGES, stageLabel } from '../opportunityPresentation'

function initialForm() {
  return { name: '', amount: '', currency_code: 'CAD', probability: '50', expected_close_on: '' }
}

const CREATE_FIELD_MESSAGES = {
  name: 'Saisissez un nom d’opportunité.',
  amount: 'Saisissez un montant supérieur à zéro, avec au plus quatre décimales.',
  currency_code: 'Saisissez un code de devise ISO à trois lettres, par exemple CAD ou USD.',
  probability: 'Saisissez une probabilité entière entre 0 et 100.',
  expected_close_on: 'Choisissez une échéance égale ou postérieure à aujourd’hui.',
}

const OPEN_STAGES = OPPORTUNITY_STAGES.slice(0, 4).map(([code]) => code)
const LOSS_REASONS = [
  ['no_need', 'Le besoin ne correspond pas à notre offre'], ['no_budget', 'Le budget n’est pas disponible'], ['no_response', 'Aucun retour après les relances'], ['competitor', 'Une offre concurrente a été retenue'], ['timing', 'Le projet est reporté'], ['scope_mismatch', 'Le prospect est hors territoire'], ['invalid_or_duplicate', 'Le prospect est invalide ou en double'], ['other', 'Autre motif'],
]
const REOPEN_REASONS = [['customer_reengaged', 'Le client a repris contact'], ['additional_information', 'De nouvelles informations sont disponibles'], ['entered_in_error', 'La clôture était une erreur'], ['other', 'Autre motif']]
const PIPELINE_BY_OPPORTUNITY_STAGE = { discovery: 'new', qualification: 'qualified', proposal: 'proposal_sent', negotiation: 'negotiation', won: 'won', lost: 'lost' }
const PIPELINE_SEQUENCE = ['new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won']
const PIPELINE_LABELS = { new: 'Nouveau', qualifying: 'Qualification', qualified: 'Qualifié', contacted: 'Contacté', opportunity: 'Opportunité', proposal_sent: 'Soumission envoyée', negotiation: 'Négociation', won: 'Gagné', lost: 'Perdu' }

function nextOpenStages(stage) {
  const index = OPEN_STAGES.indexOf(stage)
  return [OPEN_STAGES[index - 1], OPEN_STAGES[index + 1]].filter(Boolean)
}

function organizationToday(timezone) {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const values = Object.fromEntries(parts.map(({ type, value }) => [type, value]))
    return `${values.year}-${values.month}-${values.day}`
  } catch {
    return new Date().toISOString().slice(0, 10)
  }
}

function validateCreateForm(form, timezone) {
  const errors = {}
  const amount = form.amount.trim()
  const probability = Number(form.probability)
  const today = organizationToday(timezone)
  if (!form.name.trim()) errors.name = CREATE_FIELD_MESSAGES.name
  if (!/^\d+(?:\.\d+)?$/.test(amount) || !/[1-9]/.test(amount) || (amount.split('.')[1]?.length ?? 0) > 4) errors.amount = CREATE_FIELD_MESSAGES.amount
  if (!/^[A-Z]{3}$/.test(form.currency_code)) errors.currency_code = CREATE_FIELD_MESSAGES.currency_code
  if (!/^\d+$/.test(form.probability) || !Number.isInteger(probability) || probability < 0 || probability > 100) errors.probability = CREATE_FIELD_MESSAGES.probability
  if (!form.expected_close_on || form.expected_close_on < today) errors.expected_close_on = CREATE_FIELD_MESSAGES.expected_close_on
  return errors
}

function inlineErrors(fields = {}) {
  return Object.fromEntries(
    Object.keys(fields)
      .filter((field) => Object.hasOwn(CREATE_FIELD_MESSAGES, field))
      .map((field) => [field, CREATE_FIELD_MESSAGES[field]]),
  )
}

function FieldError({ id, message }) {
  return message ? <p id={id} className="field-error" role="alert">{message}</p> : null
}

export function OpportunitySection({ prospect, opportunities = [], aggregates = [], locale = 'fr-CA', timezone, canCreate, canUpdate, canClose, canReopen, canAlign, submitting, onCreate, onTransition, onReopen, onAlign }) {
  const [form, setForm] = useState(initialForm)
  const [formErrors, setFormErrors] = useState({})
  const fieldRefs = useRef({})
  const [lossIntent, setLossIntent] = useState(null)
  const [lossReason, setLossReason] = useState('no_need')
  const [lossNote, setLossNote] = useState('')
  const [reopenIntent, setReopenIntent] = useState(null)
  const [reopenReason, setReopenReason] = useState('customer_reengaged')
  const [reopenNote, setReopenNote] = useState('')
  const [alignIntent, setAlignIntent] = useState(null)

  async function submit(event) {
    event.preventDefault()
    const errors = validateCreateForm(form, timezone)
    if (Object.keys(errors).length) {
      setFormErrors(errors)
      fieldRefs.current[Object.keys(errors)[0]]?.focus()
      return
    }
    setFormErrors({})
    const result = await onCreate({ ...form, probability: Number(form.probability) })
    if (result === true) {
      setForm(initialForm())
    } else if (result?.fieldErrors) {
      const errors = inlineErrors(result.fieldErrors)
      setFormErrors(errors)
      fieldRefs.current[Object.keys(errors)[0]]?.focus()
    }
  }

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }))
    setFormErrors((current) => {
      if (!current[field]) return current
      const { [field]: _removed, ...remaining } = current
      return remaining
    })
  }

  return <section className="administration-card opportunity-section" aria-labelledby="prospect-opportunities-title">
    <h2 id="prospect-opportunities-title">Opportunités</h2>
    {aggregates.length > 0 && <div className="opportunity-aggregates" aria-label="Valeur des opportunités">
      {aggregates.map((aggregate) => <span key={aggregate.currency_code}>{formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)} pondéré</span>)}
    </div>}
    {canCreate && <form className="opportunity-form" noValidate onSubmit={submit}>
      <h3>Ajouter une opportunité</h3>
      <label htmlFor="opportunity-name">Nom<input id="opportunity-name" ref={(node) => { fieldRefs.current.name = node }} value={form.name} maxLength="160" required disabled={submitting} aria-invalid={Boolean(formErrors.name)} aria-describedby={formErrors.name ? 'opportunity-name-error' : undefined} onChange={(event) => updateForm('name', event.target.value)} /></label>
      <FieldError id="opportunity-name-error" message={formErrors.name} />
      <div className="opportunity-form-grid">
        <div><label htmlFor="opportunity-amount">Montant<input id="opportunity-amount" ref={(node) => { fieldRefs.current.amount = node }} inputMode="decimal" value={form.amount} disabled={submitting} aria-invalid={Boolean(formErrors.amount)} aria-describedby={formErrors.amount ? 'opportunity-amount-error' : undefined} onChange={(event) => updateForm('amount', event.target.value)} /></label><FieldError id="opportunity-amount-error" message={formErrors.amount} /></div>
        <div><label htmlFor="opportunity-currency">Devise<input id="opportunity-currency" ref={(node) => { fieldRefs.current.currency_code = node }} value={form.currency_code} minLength="3" maxLength="3" disabled={submitting} aria-invalid={Boolean(formErrors.currency_code)} aria-describedby={formErrors.currency_code ? 'opportunity-currency-error' : undefined} onChange={(event) => updateForm('currency_code', event.target.value.toUpperCase())} /></label><FieldError id="opportunity-currency-error" message={formErrors.currency_code} /></div>
        <div><label htmlFor="opportunity-probability">Probabilité (%)<input id="opportunity-probability" ref={(node) => { fieldRefs.current.probability = node }} type="number" value={form.probability} disabled={submitting} aria-invalid={Boolean(formErrors.probability)} aria-describedby={formErrors.probability ? 'opportunity-probability-error' : undefined} onChange={(event) => updateForm('probability', event.target.value)} /></label><FieldError id="opportunity-probability-error" message={formErrors.probability} /></div>
        <div><label htmlFor="opportunity-close-date">Échéance<input id="opportunity-close-date" ref={(node) => { fieldRefs.current.expected_close_on = node }} type="date" min={organizationToday(timezone)} value={form.expected_close_on} disabled={submitting} aria-invalid={Boolean(formErrors.expected_close_on)} aria-describedby={formErrors.expected_close_on ? 'opportunity-close-date-error' : undefined} onChange={(event) => updateForm('expected_close_on', event.target.value)} /></label><FieldError id="opportunity-close-date-error" message={formErrors.expected_close_on} /></div>
      </div>
      <button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Enregistrement…' : 'Créer l’opportunité'}</button>
    </form>}
    {opportunities.length ? <ul className="opportunity-list">{opportunities.map((opportunity) => <li key={opportunity.id}>
      <div><strong>{opportunity.name}</strong><span>{stageLabel(opportunity.stage_code, locale)} · {formatMoney(opportunity.amount, opportunity.currency_code, locale)} · {opportunity.probability}%</span><small>Échéance : {formatDate(opportunity.expected_close_on, locale)}{opportunity.overdue ? ' · En retard' : ''}</small></div>
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && <select aria-label={`Étape ${opportunity.name}`} value={opportunity.stage_code} disabled={submitting} onChange={(event) => onTransition(opportunity, event.target.value)}><option value={opportunity.stage_code}>{stageLabel(opportunity.stage_code, locale)}</option>{nextOpenStages(opportunity.stage_code).map((code) => <option value={code} key={code}>{stageLabel(code, locale)}</option>)}</select>}
      {canClose && OPEN_STAGES.includes(opportunity.stage_code) && <div className="opportunity-actions">{['proposal', 'negotiation'].includes(opportunity.stage_code) && <button type="button" className="secondary-button" disabled={submitting} onClick={() => onTransition(opportunity, 'won')}>Gagnée</button>}<button type="button" className="secondary-button" disabled={submitting} onClick={() => { setLossIntent(opportunity); setLossReason('no_need'); setLossNote('') }}>Perdue</button></div>}
      {canReopen && ['won', 'lost'].includes(opportunity.stage_code) && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => { setReopenIntent(opportunity); setReopenReason('customer_reengaged'); setReopenNote('') }}>Réouvrir</button></div>}
      {canAlign && prospect && PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code] !== prospect.stage_code && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => setAlignIntent(opportunity)}>Aligner le pipeline</button></div>}
      {lossIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onTransition(opportunity, 'lost', { reason_code: lossReason, reason_note: lossNote.trim() || undefined }); setLossIntent(null) }}><label htmlFor={`loss-reason-${opportunity.id}`}>Motif de perte<select id={`loss-reason-${opportunity.id}`} value={lossReason} onChange={(event) => setLossReason(event.target.value)}>{LOSS_REASONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>{lossReason === 'other' && <label htmlFor={`loss-note-${opportunity.id}`}>Précisez le motif<input id={`loss-note-${opportunity.id}`} value={lossNote} required maxLength="500" onChange={(event) => setLossNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>Confirmer la perte</button><button className="link-button" type="button" onClick={() => setLossIntent(null)}>Annuler</button></form>}
      {reopenIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onReopen(opportunity, { reason_code: reopenReason, reason_note: reopenNote.trim() || undefined }); setReopenIntent(null) }}><label htmlFor={`reopen-reason-${opportunity.id}`}>Motif de réouverture<select id={`reopen-reason-${opportunity.id}`} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)}>{REOPEN_REASONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>{reopenReason === 'other' && <label htmlFor={`reopen-note-${opportunity.id}`}>Précisez le motif<input id={`reopen-note-${opportunity.id}`} value={reopenNote} required maxLength="500" onChange={(event) => setReopenNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>Confirmer la réouverture</button><button className="link-button" type="button" onClick={() => setReopenIntent(null)}>Annuler</button></form>}
      {alignIntent?.id === opportunity.id && <PipelineAlignment prospect={prospect} opportunity={opportunity} submitting={submitting} onCancel={() => setAlignIntent(null)} onConfirm={async () => { await onAlign(opportunity, PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code]); setAlignIntent(null) }} />}
    </li>)}</ul> : <p className="form-help">Aucune opportunité n’est encore enregistrée.</p>}
  </section>
}

function PipelineAlignment({ prospect, opportunity, submitting, onCancel, onConfirm }) {
  const target = PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code]
  const currentIndex = PIPELINE_SEQUENCE.indexOf(prospect.stage_code)
  const targetIndex = PIPELINE_SEQUENCE.indexOf(target)
  const possible = currentIndex >= 0 && targetIndex >= 0 && Math.abs(currentIndex - targetIndex) === 1
  return <aside className="opportunity-reason-form" aria-label="Alignement du pipeline">
    <p>Le prospect est à l’étape <strong>{PIPELINE_LABELS[prospect.stage_code] ?? 'Étape indisponible'}</strong> ; l’opportunité suggère <strong>{PIPELINE_LABELS[target] ?? 'Étape indisponible'}</strong>. Les deux parcours restent indépendants.</p>
    {possible ? <><button className="secondary-button" type="button" onClick={onConfirm} disabled={submitting}>Confirmer l’alignement</button><button className="link-button" type="button" onClick={onCancel}>Annuler</button></> : <><p className="form-help">Cette transition n’est pas permise directement. Déplacez le prospect étape par étape dans le Kanban.</p><button className="link-button" type="button" onClick={onCancel}>Fermer</button></>}
  </aside>
}

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

function initialEditForm(opportunity) {
  return {
    name: opportunity.name,
    amount: String(opportunity.amount),
    currency_code: opportunity.currency_code,
    probability: String(opportunity.probability),
    expected_close_on: opportunity.expected_close_on,
    owner_membership_id: opportunity.owner_membership_id,
    currencyConfirmed: false,
  }
}

function validateEditForm(form, initial, timezone) {
  const errors = validateCreateForm(form, timezone)
  if (form.expected_close_on === initial.expected_close_on) delete errors.expected_close_on
  if (form.currency_code !== initial.currency_code && !form.currencyConfirmed) {
    errors.currency_code = 'Confirmez le montant avant de modifier la devise.'
  }
  return errors
}

function memberLabel(member) {
  return member.user?.display_name || member.user?.email || 'Membre sans nom'
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

export function OpportunitySection({ prospect, opportunities = [], aggregates = [], members = [], locale = 'fr-CA', timezone, canCreate, canUpdate, canReassign, canClose, canReopen, canAlign, submitting, onCreate, onUpdate, onTransition, onReopen, onAlign }) {
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
  const [editIntent, setEditIntent] = useState(null)
  const [editForm, setEditForm] = useState(null)
  const [editErrors, setEditErrors] = useState({})
  const activeMembers = members.filter((member) => member.status === 'active')

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

  function startEdit(opportunity) {
    setEditIntent(opportunity)
    setEditForm(initialEditForm(opportunity))
    setEditErrors({})
  }

  function updateEditForm(field, value) {
    setEditForm((current) => ({ ...current, [field]: value }))
    setEditErrors((current) => {
      if (!current[field]) return current
      const { [field]: _removed, ...remaining } = current
      return remaining
    })
  }

  async function submitEdit(event, opportunity) {
    event.preventDefault()
    if (!editForm) return
    const inactiveOwner = opportunity.owner_membership_is_active === false
    const errors = inactiveOwner
      ? (editForm.owner_membership_id ? {} : { owner_membership_id: 'Choisissez un responsable actif.' })
      : validateEditForm(editForm, opportunity, timezone)
    if (Object.keys(errors).length) {
      setEditErrors(errors)
      return
    }
    const changes = inactiveOwner
      ? { owner_membership_id: editForm.owner_membership_id }
      : Object.fromEntries(Object.entries({
        name: editForm.name.trim(),
        amount: editForm.amount.trim(),
        currency_code: editForm.currency_code,
        probability: Number(editForm.probability),
        expected_close_on: editForm.expected_close_on,
        ...(canReassign ? { owner_membership_id: editForm.owner_membership_id } : {}),
      }).filter(([field, value]) => field === 'amount' && editForm.currency_code !== opportunity.currency_code
        || value !== opportunity[field]))
    if (Object.keys(changes).length === 0) {
      setEditErrors({ form: 'Aucune modification à enregistrer.' })
      return
    }
    if (await onUpdate(opportunity, changes)) {
      setEditIntent(null)
      setEditForm(null)
      setEditErrors({})
    }
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
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && (opportunity.owner_membership_is_active !== false || canReassign) && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => startEdit(opportunity)}>{opportunity.owner_membership_is_active === false ? 'Réaffecter le responsable' : 'Modifier'}</button></div>}
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && opportunity.owner_membership_is_active === false && !canReassign && <p className="opportunity-owner-warning">Le responsable est désactivé. Un Administrateur ou un Gestionnaire doit réaffecter cette opportunité.</p>}
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && <select aria-label={`Étape ${opportunity.name}`} value={opportunity.stage_code} disabled={submitting || opportunity.owner_membership_is_active === false} onChange={(event) => onTransition(opportunity, event.target.value)}><option value={opportunity.stage_code}>{stageLabel(opportunity.stage_code, locale)}</option>{nextOpenStages(opportunity.stage_code).map((code) => <option value={code} key={code}>{stageLabel(code, locale)}</option>)}</select>}
      {canClose && OPEN_STAGES.includes(opportunity.stage_code) && <div className="opportunity-actions">{['proposal', 'negotiation'].includes(opportunity.stage_code) && <button type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => onTransition(opportunity, 'won')}>Gagnée</button>}<button type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => { setLossIntent(opportunity); setLossReason('no_need'); setLossNote('') }}>Perdue</button></div>}
      {canReopen && ['won', 'lost'].includes(opportunity.stage_code) && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => { setReopenIntent(opportunity); setReopenReason('customer_reengaged'); setReopenNote('') }}>Réouvrir</button></div>}
      {canAlign && prospect && PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code] !== prospect.stage_code && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => setAlignIntent(opportunity)}>Aligner le pipeline</button></div>}
      {editIntent?.id === opportunity.id && editForm && <OpportunityEditForm opportunity={opportunity} form={editForm} errors={editErrors} activeMembers={activeMembers} canReassign={canReassign} submitting={submitting} onChange={updateEditForm} onCancel={() => { setEditIntent(null); setEditForm(null); setEditErrors({}) }} onSubmit={(event) => submitEdit(event, opportunity)} />}
      {lossIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onTransition(opportunity, 'lost', { reason_code: lossReason, reason_note: lossNote.trim() || undefined }); setLossIntent(null) }}><label htmlFor={`loss-reason-${opportunity.id}`}>Motif de perte<select id={`loss-reason-${opportunity.id}`} value={lossReason} onChange={(event) => setLossReason(event.target.value)}>{LOSS_REASONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>{lossReason === 'other' && <label htmlFor={`loss-note-${opportunity.id}`}>Précisez le motif<input id={`loss-note-${opportunity.id}`} value={lossNote} required maxLength="500" onChange={(event) => setLossNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>Confirmer la perte</button><button className="link-button" type="button" onClick={() => setLossIntent(null)}>Annuler</button></form>}
      {reopenIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onReopen(opportunity, { reason_code: reopenReason, reason_note: reopenNote.trim() || undefined }); setReopenIntent(null) }}><label htmlFor={`reopen-reason-${opportunity.id}`}>Motif de réouverture<select id={`reopen-reason-${opportunity.id}`} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)}>{REOPEN_REASONS.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>{reopenReason === 'other' && <label htmlFor={`reopen-note-${opportunity.id}`}>Précisez le motif<input id={`reopen-note-${opportunity.id}`} value={reopenNote} required maxLength="500" onChange={(event) => setReopenNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>Confirmer la réouverture</button><button className="link-button" type="button" onClick={() => setReopenIntent(null)}>Annuler</button></form>}
      {alignIntent?.id === opportunity.id && <PipelineAlignment prospect={prospect} opportunity={opportunity} submitting={submitting} onCancel={() => setAlignIntent(null)} onConfirm={async () => { await onAlign(opportunity, PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code]); setAlignIntent(null) }} />}
    </li>)}</ul> : <p className="form-help">Aucune opportunité n’est encore enregistrée.</p>}
  </section>
}

function OpportunityEditForm({ opportunity, form, errors, activeMembers, canReassign, submitting, onChange, onCancel, onSubmit }) {
  const inactiveOwner = opportunity.owner_membership_is_active === false
  const prefix = `opportunity-edit-${opportunity.id}`
  return <form className="opportunity-edit-form" noValidate onSubmit={onSubmit} aria-label={`Modifier ${opportunity.name}`}>
    <h3>{inactiveOwner ? 'Réaffecter le responsable' : 'Modifier l’opportunité'}</h3>
    {inactiveOwner && <p className="opportunity-owner-warning" role="alert">Le responsable est désactivé. Seule une réaffectation vers un membre actif est permise.</p>}
    {errors.form && <p className="field-error" role="alert">{errors.form}</p>}
    {inactiveOwner ? <OwnerSelect id={`${prefix}-owner`} form={form} errors={errors} activeMembers={activeMembers} disabled={submitting || !canReassign} onChange={onChange} /> : <>
      <label htmlFor={`${prefix}-name`}>Nom<input id={`${prefix}-name`} value={form.name} maxLength="160" required disabled={submitting} aria-invalid={Boolean(errors.name)} onChange={(event) => onChange('name', event.target.value)} /></label><FieldError id={`${prefix}-name-error`} message={errors.name} />
      <div className="opportunity-form-grid">
        <div><label htmlFor={`${prefix}-amount`}>Montant<input id={`${prefix}-amount`} inputMode="decimal" value={form.amount} disabled={submitting} aria-invalid={Boolean(errors.amount)} onChange={(event) => onChange('amount', event.target.value)} /></label><FieldError id={`${prefix}-amount-error`} message={errors.amount} /></div>
        <div><label htmlFor={`${prefix}-currency`}>Devise<input id={`${prefix}-currency`} value={form.currency_code} minLength="3" maxLength="3" disabled={submitting} aria-invalid={Boolean(errors.currency_code)} onChange={(event) => onChange('currency_code', event.target.value.toUpperCase())} /></label><FieldError id={`${prefix}-currency-error`} message={errors.currency_code} /></div>
        <div><label htmlFor={`${prefix}-probability`}>Probabilité (%)<input id={`${prefix}-probability`} type="number" value={form.probability} disabled={submitting} aria-invalid={Boolean(errors.probability)} onChange={(event) => onChange('probability', event.target.value)} /></label><FieldError id={`${prefix}-probability-error`} message={errors.probability} /></div>
        <div><label htmlFor={`${prefix}-date`}>Échéance<input id={`${prefix}-date`} type="date" value={form.expected_close_on} disabled={submitting} aria-invalid={Boolean(errors.expected_close_on)} onChange={(event) => onChange('expected_close_on', event.target.value)} /></label><FieldError id={`${prefix}-date-error`} message={errors.expected_close_on} /></div>
      </div>
      {form.currency_code !== opportunity.currency_code && <label className="opportunity-currency-confirmation"><input type="checkbox" checked={form.currencyConfirmed} disabled={submitting} onChange={(event) => onChange('currencyConfirmed', event.target.checked)} /> J’ai confirmé le montant dans la nouvelle devise. Aucune conversion n’est appliquée.</label>}
      {canReassign && <OwnerSelect id={`${prefix}-owner`} form={form} errors={errors} activeMembers={activeMembers} disabled={submitting} onChange={onChange} />}
    </>}
    {!canReassign && inactiveOwner && <p className="form-help">Seul un Administrateur ou un Gestionnaire peut réaffecter cette opportunité.</p>}
    <div className="opportunity-edit-actions"><button className="secondary-button" type="submit" disabled={submitting || (inactiveOwner && !canReassign)}>Enregistrer</button><button className="link-button" type="button" disabled={submitting} onClick={onCancel}>Annuler</button></div>
  </form>
}

function OwnerSelect({ id, form, errors, activeMembers, disabled, onChange }) {
  return <label htmlFor={id}>Responsable<select id={id} value={form.owner_membership_id || ''} disabled={disabled} aria-invalid={Boolean(errors.owner_membership_id)} onChange={(event) => onChange('owner_membership_id', event.target.value)}><option value="">Choisissez un membre actif</option>{activeMembers.map((member) => <option key={member.membership_id} value={member.membership_id}>{memberLabel(member)}</option>)}</select><FieldError id={`${id}-error`} message={errors.owner_membership_id} /></label>
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

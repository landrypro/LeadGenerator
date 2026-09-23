import { useRef, useState } from 'react'

import { useEscapeKey } from '../../../shared/hooks/useEscapeKey'
import { getOpportunityMessages } from '../opportunityMessages'
import { formatDate, formatMoney, OPPORTUNITY_STAGES, stageLabel } from '../opportunityPresentation'

function initialForm() {
  return { name: '', amount: '', currency_code: 'CAD', probability: '50', expected_close_on: '' }
}

const OPEN_STAGES = OPPORTUNITY_STAGES.slice(0, 4).map(([code]) => code)
const LOSS_REASON_CODES = ['no_need', 'no_budget', 'no_response', 'competitor', 'timing', 'scope_mismatch', 'invalid_or_duplicate', 'other']
const REOPEN_REASON_CODES = ['customer_reengaged', 'additional_information', 'entered_in_error', 'other']
const PIPELINE_BY_OPPORTUNITY_STAGE = { discovery: 'new', qualification: 'qualified', proposal: 'proposal_sent', negotiation: 'negotiation', won: 'won', lost: 'lost' }
const PIPELINE_SEQUENCE = ['new', 'qualifying', 'qualified', 'contacted', 'opportunity', 'proposal_sent', 'negotiation', 'won']

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

function normalizeAmountInput(value, locale) {
  const amount = String(value).trim()
  const decimalSeparator = locale === 'fr-CA' ? ',' : '.'
  const validFormat = locale === 'fr-CA'
    ? /^\d+(?:,\d+)?$/
    : /^\d+(?:\.\d+)?$/
  if (!validFormat.test(amount) || !/[1-9]/.test(amount)) return null
  const [integer, decimals = ''] = amount.split(decimalSeparator)
  if (decimals.length > 4) return null
  return decimals ? `${integer}.${decimals}` : integer
}

function localizeAmountInput(value, locale) {
  const amount = String(value)
  return locale === 'fr-CA' ? amount.replace('.', ',') : amount
}

function validateCreateForm(form, timezone, locale, strings) {
  const errors = {}
  const probability = Number(form.probability)
  const today = organizationToday(timezone)
  if (!form.name.trim()) errors.name = strings.nameRequired
  if (normalizeAmountInput(form.amount, locale) === null) errors.amount = strings.amountInvalid
  if (!/^[A-Z]{3}$/.test(form.currency_code)) errors.currency_code = strings.currencyInvalid
  if (!/^\d+$/.test(form.probability) || !Number.isInteger(probability) || probability < 0 || probability > 100) errors.probability = strings.probabilityInvalid
  if (!form.expected_close_on || form.expected_close_on < today) errors.expected_close_on = strings.closeDateInvalid
  return errors
}

function initialEditForm(opportunity, locale) {
  return {
    name: opportunity.name,
    amount: localizeAmountInput(opportunity.amount, locale),
    currency_code: opportunity.currency_code,
    probability: String(opportunity.probability),
    expected_close_on: opportunity.expected_close_on,
    owner_membership_id: opportunity.owner_membership_id,
    currencyConfirmed: false,
  }
}

function validateEditForm(form, initial, timezone, locale, strings) {
  const errors = validateCreateForm(form, timezone, locale, strings)
  if (form.expected_close_on === initial.expected_close_on) delete errors.expected_close_on
  if (form.currency_code !== initial.currency_code && !form.currencyConfirmed) {
    errors.currency_code = strings.currencyConfirmationRequired
  }
  return errors
}

function memberLabel(member, strings) {
  return member.user?.display_name || member.user?.email || strings.unnamedMember
}

function inlineErrors(fields = {}, strings) {
  const messages = {
    name: strings.nameRequired,
    amount: strings.amountInvalid,
    currency_code: strings.currencyInvalid,
    probability: strings.probabilityInvalid,
    expected_close_on: strings.closeDateInvalid,
  }
  return Object.fromEntries(
    Object.keys(fields)
      .filter((field) => Object.hasOwn(messages, field))
      .map((field) => [field, messages[field]]),
  )
}

function FieldError({ id, message }) {
  return message ? <p id={id} className="field-error" role="alert">{message}</p> : null
}

export function OpportunitySection({ prospect, opportunities = [], aggregates = [], members = [], locale = 'fr-CA', timezone, canCreate, canUpdate, canReassign, canClose, canReopen, canAlign, submitting, onCreate, onUpdate, onTransition, onReopen, onAlign }) {
  const strings = getOpportunityMessages(locale)
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
  const lossTriggerRefs = useRef({})
  const reopenTriggerRefs = useRef({})
  const alignTriggerRefs = useRef({})
  const activeMembers = members.filter((member) => member.status === 'active')

  useEscapeKey(Boolean(lossIntent) && !submitting, closeLossIntent)
  useEscapeKey(Boolean(reopenIntent) && !submitting, closeReopenIntent)
  useEscapeKey(Boolean(alignIntent) && !submitting, closeAlignIntent)

  function restoreActionFocus(refs, opportunityId) {
    window.setTimeout(() => refs.current[opportunityId]?.focus(), 0)
  }

  function closeLossIntent() {
    const opportunityId = lossIntent?.id
    setLossIntent(null)
    if (opportunityId) restoreActionFocus(lossTriggerRefs, opportunityId)
  }

  function closeReopenIntent() {
    const opportunityId = reopenIntent?.id
    setReopenIntent(null)
    if (opportunityId) restoreActionFocus(reopenTriggerRefs, opportunityId)
  }

  function closeAlignIntent() {
    const opportunityId = alignIntent?.id
    setAlignIntent(null)
    if (opportunityId) restoreActionFocus(alignTriggerRefs, opportunityId)
  }

  async function submit(event) {
    event.preventDefault()
    const errors = validateCreateForm(form, timezone, locale, strings)
    if (Object.keys(errors).length) {
      setFormErrors(errors)
      fieldRefs.current[Object.keys(errors)[0]]?.focus()
      return
    }
    setFormErrors({})
    const result = await onCreate({
      ...form,
      amount: normalizeAmountInput(form.amount, locale),
      probability: Number(form.probability),
    })
    if (result === true) {
      setForm(initialForm())
    } else if (result?.fieldErrors) {
      const errors = inlineErrors(result.fieldErrors, strings)
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
    setEditForm(initialEditForm(opportunity, locale))
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
      ? (editForm.owner_membership_id ? {} : { owner_membership_id: strings.ownerRequired })
      : validateEditForm(editForm, opportunity, timezone, locale, strings)
    if (Object.keys(errors).length) {
      setEditErrors(errors)
      return
    }
    const changes = inactiveOwner
      ? { owner_membership_id: editForm.owner_membership_id }
      : Object.fromEntries(Object.entries({
        name: editForm.name.trim(),
        amount: normalizeAmountInput(editForm.amount, locale),
        currency_code: editForm.currency_code,
        probability: Number(editForm.probability),
        expected_close_on: editForm.expected_close_on,
        ...(canReassign ? { owner_membership_id: editForm.owner_membership_id } : {}),
      }).filter(([field, value]) => field === 'amount' && editForm.currency_code !== opportunity.currency_code
        || value !== opportunity[field]))
    if (Object.keys(changes).length === 0) {
      setEditErrors({ form: strings.noChanges })
      return
    }
    if (await onUpdate(opportunity, changes)) {
      setEditIntent(null)
      setEditForm(null)
      setEditErrors({})
    }
  }

  return <section className="administration-card opportunity-section" aria-labelledby="prospect-opportunities-title">
    <h2 id="prospect-opportunities-title">{strings.title}</h2>
    {aggregates.length > 0 && <div className="opportunity-aggregates" aria-label={strings.valueLabel}>
      {aggregates.map((aggregate) => <span key={aggregate.currency_code}>{formatMoney(aggregate.weighted_amount_total, aggregate.currency_code, locale)} {strings.weighted}</span>)}
    </div>}
    {canCreate && <form className="opportunity-form" noValidate onSubmit={submit}>
      <h3>{strings.addTitle}</h3>
      <label htmlFor="opportunity-name">{strings.name}<input id="opportunity-name" ref={(node) => { fieldRefs.current.name = node }} value={form.name} maxLength="160" required disabled={submitting} aria-invalid={Boolean(formErrors.name)} aria-describedby={formErrors.name ? 'opportunity-name-error' : undefined} onChange={(event) => updateForm('name', event.target.value)} /></label>
      <FieldError id="opportunity-name-error" message={formErrors.name} />
      <div className="opportunity-form-grid">
        <div><label htmlFor="opportunity-amount">{strings.amount}<input id="opportunity-amount" ref={(node) => { fieldRefs.current.amount = node }} inputMode="decimal" value={form.amount} disabled={submitting} aria-invalid={Boolean(formErrors.amount)} aria-describedby={formErrors.amount ? 'opportunity-amount-error' : undefined} onChange={(event) => updateForm('amount', event.target.value)} /></label><FieldError id="opportunity-amount-error" message={formErrors.amount} /></div>
        <div><label htmlFor="opportunity-currency">{strings.currency}<input id="opportunity-currency" ref={(node) => { fieldRefs.current.currency_code = node }} value={form.currency_code} minLength="3" maxLength="3" disabled={submitting} aria-invalid={Boolean(formErrors.currency_code)} aria-describedby={formErrors.currency_code ? 'opportunity-currency-error' : undefined} onChange={(event) => updateForm('currency_code', event.target.value.toUpperCase())} /></label><FieldError id="opportunity-currency-error" message={formErrors.currency_code} /></div>
        <div><label htmlFor="opportunity-probability">{strings.probability}<input id="opportunity-probability" ref={(node) => { fieldRefs.current.probability = node }} type="number" value={form.probability} disabled={submitting} aria-invalid={Boolean(formErrors.probability)} aria-describedby={formErrors.probability ? 'opportunity-probability-error' : undefined} onChange={(event) => updateForm('probability', event.target.value)} /></label><FieldError id="opportunity-probability-error" message={formErrors.probability} /></div>
        <div><label htmlFor="opportunity-close-date">{strings.dueDate}<input id="opportunity-close-date" ref={(node) => { fieldRefs.current.expected_close_on = node }} type="date" min={organizationToday(timezone)} value={form.expected_close_on} disabled={submitting} aria-invalid={Boolean(formErrors.expected_close_on)} aria-describedby={formErrors.expected_close_on ? 'opportunity-close-date-error' : undefined} onChange={(event) => updateForm('expected_close_on', event.target.value)} /></label><FieldError id="opportunity-close-date-error" message={formErrors.expected_close_on} /></div>
      </div>
      <button className="primary-button" type="submit" disabled={submitting}>{submitting ? strings.saving : strings.create}</button>
    </form>}
    {opportunities.length ? <ul className="opportunity-list">{opportunities.map((opportunity) => <li key={opportunity.id}>
      <div><strong>{opportunity.name}</strong><span>{stageLabel(opportunity.stage_code, locale)} · {formatMoney(opportunity.amount, opportunity.currency_code, locale)} · {opportunity.probability}%</span><small>{strings.dueDate} : {formatDate(opportunity.expected_close_on, locale)}{opportunity.overdue ? ` · ${strings.overdue}` : ''}</small></div>
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && (opportunity.owner_membership_is_active !== false || canReassign) && <div className="opportunity-actions"><button type="button" className="secondary-button" disabled={submitting} onClick={() => startEdit(opportunity)}>{opportunity.owner_membership_is_active === false ? strings.reassignOwner : strings.edit}</button></div>}
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && opportunity.owner_membership_is_active === false && !canReassign && <p className="opportunity-owner-warning">{strings.ownerInactive}</p>}
      {canUpdate && OPEN_STAGES.includes(opportunity.stage_code) && <select aria-label={strings.stageAria(opportunity.name)} value={opportunity.stage_code} disabled={submitting || opportunity.owner_membership_is_active === false} onChange={(event) => onTransition(opportunity, event.target.value)}><option value={opportunity.stage_code}>{stageLabel(opportunity.stage_code, locale)}</option>{nextOpenStages(opportunity.stage_code).map((code) => <option value={code} key={code}>{stageLabel(code, locale)}</option>)}</select>}
      {canClose && OPEN_STAGES.includes(opportunity.stage_code) && <div className="opportunity-actions">{['proposal', 'negotiation'].includes(opportunity.stage_code) && <button type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => onTransition(opportunity, 'won')}>{strings.won}</button>}<button ref={(node) => { lossTriggerRefs.current[opportunity.id] = node }} type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => { setLossIntent(opportunity); setLossReason('no_need'); setLossNote('') }}>{strings.lost}</button></div>}
      {canReopen && ['won', 'lost'].includes(opportunity.stage_code) && <div className="opportunity-actions"><button ref={(node) => { reopenTriggerRefs.current[opportunity.id] = node }} type="button" className="secondary-button" disabled={submitting || opportunity.owner_membership_is_active === false} onClick={() => { setReopenIntent(opportunity); setReopenReason('customer_reengaged'); setReopenNote('') }}>{strings.reopen}</button></div>}
      {canAlign && prospect && PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code] !== prospect.stage_code && <div className="opportunity-actions"><button ref={(node) => { alignTriggerRefs.current[opportunity.id] = node }} type="button" className="secondary-button" disabled={submitting} onClick={() => setAlignIntent(opportunity)}>{strings.alignPipeline}</button></div>}
      {editIntent?.id === opportunity.id && editForm && <OpportunityEditForm opportunity={opportunity} form={editForm} errors={editErrors} activeMembers={activeMembers} canReassign={canReassign} submitting={submitting} strings={strings} onChange={updateEditForm} onCancel={() => { setEditIntent(null); setEditForm(null); setEditErrors({}) }} onSubmit={(event) => submitEdit(event, opportunity)} />}
      {lossIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onTransition(opportunity, 'lost', { reason_code: lossReason, reason_note: lossNote.trim() || undefined }); setLossIntent(null) }}><label htmlFor={`loss-reason-${opportunity.id}`}>{strings.lossReason}<select autoFocus id={`loss-reason-${opportunity.id}`} value={lossReason} onChange={(event) => setLossReason(event.target.value)}>{LOSS_REASON_CODES.map((code) => <option key={code} value={code}>{strings.lossReasons[code]}</option>)}</select></label>{lossReason === 'other' && <label htmlFor={`loss-note-${opportunity.id}`}>{strings.specifyReason}<input id={`loss-note-${opportunity.id}`} value={lossNote} required maxLength="500" onChange={(event) => setLossNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>{strings.confirmLoss}</button><button className="link-button" type="button" onClick={closeLossIntent}>{strings.cancel}</button></form>}
      {reopenIntent?.id === opportunity.id && <form className="opportunity-reason-form" onSubmit={async (event) => { event.preventDefault(); await onReopen(opportunity, { reason_code: reopenReason, reason_note: reopenNote.trim() || undefined }); setReopenIntent(null) }}><label htmlFor={`reopen-reason-${opportunity.id}`}>{strings.reopenReason}<select autoFocus id={`reopen-reason-${opportunity.id}`} value={reopenReason} onChange={(event) => setReopenReason(event.target.value)}>{REOPEN_REASON_CODES.map((code) => <option key={code} value={code}>{strings.reopenReasons[code]}</option>)}</select></label>{reopenReason === 'other' && <label htmlFor={`reopen-note-${opportunity.id}`}>{strings.specifyReason}<input id={`reopen-note-${opportunity.id}`} value={reopenNote} required maxLength="500" onChange={(event) => setReopenNote(event.target.value)} /></label>}<button className="secondary-button" type="submit" disabled={submitting}>{strings.confirmReopen}</button><button className="link-button" type="button" onClick={closeReopenIntent}>{strings.cancel}</button></form>}
      {alignIntent?.id === opportunity.id && <PipelineAlignment prospect={prospect} opportunity={opportunity} submitting={submitting} strings={strings} onCancel={closeAlignIntent} onConfirm={async () => { await onAlign(opportunity, PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code]); setAlignIntent(null) }} />}
    </li>)}</ul> : <p className="form-help">{strings.empty}</p>}
  </section>
}

function OpportunityEditForm({ opportunity, form, errors, activeMembers, canReassign, submitting, strings, onChange, onCancel, onSubmit }) {
  const inactiveOwner = opportunity.owner_membership_is_active === false
  const prefix = `opportunity-edit-${opportunity.id}`
  return <form className="opportunity-edit-form" noValidate onSubmit={onSubmit} aria-label={strings.editAria(opportunity.name)}>
    <h3>{inactiveOwner ? strings.reassignOwner : strings.editTitle}</h3>
    {inactiveOwner && <p className="opportunity-owner-warning" role="alert">{strings.inactiveOwnerAlert}</p>}
    {errors.form && <p className="field-error" role="alert">{errors.form}</p>}
    {inactiveOwner ? <OwnerSelect id={`${prefix}-owner`} form={form} errors={errors} activeMembers={activeMembers} disabled={submitting || !canReassign} strings={strings} onChange={onChange} /> : <>
      <label htmlFor={`${prefix}-name`}>{strings.name}<input id={`${prefix}-name`} value={form.name} maxLength="160" required disabled={submitting} aria-invalid={Boolean(errors.name)} onChange={(event) => onChange('name', event.target.value)} /></label><FieldError id={`${prefix}-name-error`} message={errors.name} />
      <div className="opportunity-form-grid">
        <div><label htmlFor={`${prefix}-amount`}>{strings.amount}<input id={`${prefix}-amount`} inputMode="decimal" value={form.amount} disabled={submitting} aria-invalid={Boolean(errors.amount)} onChange={(event) => onChange('amount', event.target.value)} /></label><FieldError id={`${prefix}-amount-error`} message={errors.amount} /></div>
        <div><label htmlFor={`${prefix}-currency`}>{strings.currency}<input id={`${prefix}-currency`} value={form.currency_code} minLength="3" maxLength="3" disabled={submitting} aria-invalid={Boolean(errors.currency_code)} onChange={(event) => onChange('currency_code', event.target.value.toUpperCase())} /></label><FieldError id={`${prefix}-currency-error`} message={errors.currency_code} /></div>
        <div><label htmlFor={`${prefix}-probability`}>{strings.probability}<input id={`${prefix}-probability`} type="number" value={form.probability} disabled={submitting} aria-invalid={Boolean(errors.probability)} onChange={(event) => onChange('probability', event.target.value)} /></label><FieldError id={`${prefix}-probability-error`} message={errors.probability} /></div>
        <div><label htmlFor={`${prefix}-date`}>{strings.dueDate}<input id={`${prefix}-date`} type="date" value={form.expected_close_on} disabled={submitting} aria-invalid={Boolean(errors.expected_close_on)} onChange={(event) => onChange('expected_close_on', event.target.value)} /></label><FieldError id={`${prefix}-date-error`} message={errors.expected_close_on} /></div>
      </div>
      {form.currency_code !== opportunity.currency_code && <label className="opportunity-currency-confirmation"><input type="checkbox" checked={form.currencyConfirmed} disabled={submitting} onChange={(event) => onChange('currencyConfirmed', event.target.checked)} /> {strings.confirmCurrencyChange}</label>}
      {canReassign && <OwnerSelect id={`${prefix}-owner`} form={form} errors={errors} activeMembers={activeMembers} disabled={submitting} strings={strings} onChange={onChange} />}
    </>}
    {!canReassign && inactiveOwner && <p className="form-help">{strings.adminReassignmentOnly}</p>}
    <div className="opportunity-edit-actions"><button className="secondary-button" type="submit" disabled={submitting || (inactiveOwner && !canReassign)}>{strings.save}</button><button className="link-button" type="button" disabled={submitting} onClick={onCancel}>{strings.cancel}</button></div>
  </form>
}

function OwnerSelect({ id, form, errors, activeMembers, disabled, strings, onChange }) {
  return <label htmlFor={id}>{strings.owner}<select id={id} value={form.owner_membership_id || ''} disabled={disabled} aria-invalid={Boolean(errors.owner_membership_id)} onChange={(event) => onChange('owner_membership_id', event.target.value)}><option value="">{strings.chooseActiveMember}</option>{activeMembers.map((member) => <option key={member.membership_id} value={member.membership_id}>{memberLabel(member, strings)}</option>)}</select><FieldError id={`${id}-error`} message={errors.owner_membership_id} /></label>
}

function PipelineAlignment({ prospect, opportunity, submitting, strings, onCancel, onConfirm }) {
  const target = PIPELINE_BY_OPPORTUNITY_STAGE[opportunity.stage_code]
  const currentIndex = PIPELINE_SEQUENCE.indexOf(prospect.stage_code)
  const targetIndex = PIPELINE_SEQUENCE.indexOf(target)
  const possible = currentIndex >= 0 && targetIndex >= 0 && Math.abs(currentIndex - targetIndex) === 1
  const currentLabel = strings.pipelineStages[prospect.stage_code] ?? strings.stageUnavailable
  const targetLabel = strings.pipelineStages[target] ?? strings.stageUnavailable
  return <aside className="opportunity-reason-form" aria-label={strings.alignmentLabel}>
    <p>{strings.alignmentSummary(currentLabel, targetLabel)} {strings.independentPaths}</p>
    {possible ? <><button autoFocus className="secondary-button" type="button" onClick={onConfirm} disabled={submitting}>{strings.confirmAlignment}</button><button className="link-button" type="button" onClick={onCancel}>{strings.cancel}</button></> : <><p className="form-help">{strings.transitionNotAllowed}</p><button autoFocus className="link-button" type="button" onClick={onCancel}>{strings.close}</button></>}
  </aside>
}

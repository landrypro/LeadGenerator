import { useState } from 'react'

import { Clock3 } from '../../../icons'
import { taskDueState } from './taskPresentation'

const TEXT = {
  'fr-CA': { create: 'Planifier une tâche', due: 'Échéance', empty: 'Aucune tâche planifiée.', late: 'En retard', reminder: 'Rappel interne', save: 'Créer la tâche', saving: 'Création…', title: 'Titre de la tâche', today: 'Aujourd’hui', upcoming: 'À venir' },
  'en-CA': { create: 'Schedule a task', due: 'Due date', empty: 'No task is scheduled.', late: 'Overdue', reminder: 'Internal reminder', save: 'Create task', saving: 'Creating…', title: 'Task title', today: 'Today', upcoming: 'Upcoming' },
}

const PRIORITIES = {
  'fr-CA': { low: 'Faible', normal: 'Normale', high: 'Haute', urgent: 'Urgente' },
  'en-CA': { low: 'Low', normal: 'Normal', high: 'High', urgent: 'Urgent' },
}

function words(locale) { return TEXT[locale] ?? TEXT['fr-CA'] }

function localValue(value = new Date(Date.now() + 86_400_000)) {
  const offset = value.getTimezoneOffset() * 60_000
  return new Date(value.getTime() - offset).toISOString().slice(0, 16)
}

export function TaskPanel({ tasks, locale = 'fr-CA', timezone, canCreate, submitting, onCreate, onAction }) {
  const copy = words(locale)
  const [title, setTitle] = useState('')
  const [dueAt, setDueAt] = useState(() => localValue())
  const [reminderAt, setReminderAt] = useState('')
  const [priority, setPriority] = useState('normal')

  async function submit(event) {
    event.preventDefault()
    const created = await onCreate({ title: title.trim(), due_at: new Date(dueAt).toISOString(), reminder_at: reminderAt ? new Date(reminderAt).toISOString() : undefined, priority })
    if (created) { setTitle(''); setDueAt(localValue()); setReminderAt(''); setPriority('normal') }
  }

  return <section className="administration-card task-panel" aria-labelledby="prospect-tasks-title">
    <div className="task-panel-heading"><div className="administration-card-icon lime"><Clock3 size={21} /></div><h2 id="prospect-tasks-title">{locale === 'en-CA' ? 'Tasks and next action' : 'Tâches et prochaine action'}</h2></div>
    {canCreate && <form className="task-create-form" onSubmit={submit}>
      <h3>{copy.create}</h3><p className="form-help">{timezone ? `${locale === 'en-CA' ? 'Times are shown in' : 'Les heures sont affichées dans'} ${timezone}.` : ''}</p>
        <label htmlFor="task-title">{copy.title}<input id="task-title" value={title} maxLength="160" required disabled={submitting} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="task-create-grid"><label htmlFor="task-due">{copy.due}<input id="task-due" type="datetime-local" value={dueAt} min={localValue(new Date())} required disabled={submitting} onChange={(event) => setDueAt(event.target.value)} /></label><label htmlFor="task-priority">{locale === 'en-CA' ? 'Priority' : 'Priorité'}<select id="task-priority" value={priority} disabled={submitting} onChange={(event) => setPriority(event.target.value)}>{Object.entries(PRIORITIES[locale] ?? PRIORITIES['fr-CA']).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label htmlFor="task-reminder">{copy.reminder}<input id="task-reminder" type="datetime-local" value={reminderAt} max={dueAt} disabled={submitting} onChange={(event) => setReminderAt(event.target.value)} /></label></div>
      <button className="primary-button" type="submit" disabled={submitting}>{submitting ? copy.saving : copy.save}</button>
    </form>}
    <ul className="prospect-task-list">{tasks.length ? tasks.map((task, index) => <TaskRow key={task.id} task={task} locale={locale} timezone={timezone} isNext={index === 0 && task.status === 'open'} submitting={submitting} onAction={onAction} />) : <li className="form-help">{copy.empty}</li>}</ul>
  </section>
}

export function TaskRow({ task, locale, timezone, isNext = false, reminderDue = false, submitting, onAction }) {
  const dueState = taskDueState(task, locale)
  const dueLabel = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(new Date(task.due_at))
  const [reason, setReason] = useState('')
  const [showReason, setShowReason] = useState('')
  const [showSnooze, setShowSnooze] = useState(false)
  const [snoozedUntil, setSnoozedUntil] = useState(() => localValue(new Date(Date.now() + 3_600_000)))
  function request(action) {
    if (action === 'cancel' || action === 'reopen') { setShowReason(action); return }
    onAction(task, action)
  }
  return <li className={`prospect-task ${task.status}`}><div><strong>{task.title}</strong>{isNext && <span className="next-action-badge">{locale === 'en-CA' ? 'Next action' : 'Prochaine action'}</span>}<small className={`task-due ${dueState.className}`}><time dateTime={task.due_at}>{dueLabel}</time> · {dueState.label} · {(PRIORITIES[locale] ?? PRIORITIES['fr-CA'])[task.priority] ?? task.priority}</small>{task.assigned_membership_is_active === false && <small className="task-assignee-warning">{locale === 'en-CA' ? 'Assignee is inactive' : 'Responsable désactivé'}</small>}</div>
    {task.status === 'open' && <div className="task-actions"><button className="secondary-button" type="button" disabled={submitting} onClick={() => request('complete')}>{locale === 'en-CA' ? 'Complete' : 'Terminer'}</button><button className="link-button" type="button" disabled={submitting} onClick={() => request('cancel')}>{locale === 'en-CA' ? 'Cancel' : 'Annuler'}</button></div>}
    {task.status !== 'open' && <button className="secondary-button" type="button" disabled={submitting} onClick={() => request('reopen')}>{locale === 'en-CA' ? 'Reopen' : 'Rouvrir'}</button>}
    {reminderDue && task.status === 'open' && <div className="task-reminder-actions"><button className="secondary-button" type="button" disabled={submitting} onClick={() => onAction(task, 'acknowledge-reminder')}>{locale === 'en-CA' ? 'Acknowledge reminder' : 'Accuser le rappel'}</button><button className="link-button" type="button" disabled={submitting} onClick={() => setShowSnooze(true)}>{locale === 'en-CA' ? 'Snooze' : 'Reporter'}</button></div>}
    {showReason && <form className="task-reason-form" onSubmit={(event) => { event.preventDefault(); onAction(task, showReason, { reason }); setShowReason(''); setReason('') }}><label htmlFor={`task-reason-${task.id}`}>{locale === 'en-CA' ? 'Reason' : 'Motif'}<input id={`task-reason-${task.id}`} value={reason} minLength="1" maxLength="500" required onChange={(event) => setReason(event.target.value)} /></label><button className="secondary-button" type="submit">{locale === 'en-CA' ? 'Confirm' : 'Confirmer'}</button></form>}
    {showSnooze && <form className="task-reason-form" onSubmit={(event) => { event.preventDefault(); onAction(task, 'snooze-reminder', { reminder_at: new Date(snoozedUntil).toISOString() }); setShowSnooze(false) }}><label htmlFor={`task-snooze-${task.id}`}>{locale === 'en-CA' ? 'New reminder time' : 'Nouvelle heure de rappel'}<input id={`task-snooze-${task.id}`} type="datetime-local" value={snoozedUntil} required onChange={(event) => setSnoozedUntil(event.target.value)} /></label><button className="secondary-button" type="submit">{locale === 'en-CA' ? 'Confirm snooze' : 'Confirmer le report'}</button></form>}
  </li>
}

import { useMemo, useState } from 'react'

import { AlertTriangle, Check, Clock3 } from '../../../icons'

const COPY = {
  'fr-CA': {
    activity: 'Activité',
    add: 'Ajouter une activité',
    call: 'Appel déclaré',
    channel: 'Canal concerné',
    channelOptional: 'Canal concerné (facultatif)',
    correction: 'Corriger',
    correctionReason: 'Motif de la correction',
    correctionTitle: 'Correction append-only',
    correctionDescription: 'La saisie initiale demeure dans la chronologie. Cette nouvelle entrée porte sa correction.',
    direction: 'Sens de l’échange',
    email: 'Courriel déclaré',
    empty: 'Aucune activité n’est encore inscrite dans la chronologie.',
    inbound: 'Entrant',
    internal: 'Interne',
    meeting: 'Réunion déclarée',
    note: 'Note interne',
    noteLabel: 'Détails internes',
    occurredAt: 'Date et heure de l’activité',
    outbound: 'Sortant',
    permissionAllowed: 'Permission du canal : contact autorisé.',
    permissionRestricted: 'Attention : ce canal est restreint. Vérifiez la permission avant tout contact réel.',
    permissionUnknown: 'Permission du canal non déterminée. Vérifiez-la avant tout contact réel.',
    record: 'Enregistrer l’activité',
    recording: 'Enregistrement…',
    stageChanged: 'Étape modifiée',
    selectChannel: 'Ne pas associer de canal',
    sentNothing: 'Cette déclaration n’envoie aucun courriel et ne contacte personne.',
    summary: 'Résumé',
    taskCancelled: 'Tâche annulée',
    taskCompleted: 'Tâche terminée',
    taskCreated: 'Tâche créée',
    taskReopened: 'Tâche rouverte',
    taskReminderAcknowledged: 'Rappel accusé',
    taskReminderSnoozed: 'Rappel reporté',
    taskUnavailable: 'Tâche associée',
    taskUpdated: 'Tâche modifiée',
    timeline: 'Chronologie commerciale',
    type: 'Type d’activité',
    update: 'Enregistrer la correction',
    updating: 'Correction…',
  },
  'en-CA': {
    activity: 'Activity',
    add: 'Add an activity',
    call: 'Logged call',
    channel: 'Related channel',
    channelOptional: 'Related channel (optional)',
    correction: 'Correct',
    correctionReason: 'Reason for correction',
    correctionTitle: 'Append-only correction',
    correctionDescription: 'The original entry stays in the timeline. This new entry records its correction.',
    direction: 'Direction',
    email: 'Logged email',
    empty: 'No activity has been recorded in this timeline yet.',
    inbound: 'Inbound',
    internal: 'Internal',
    meeting: 'Logged meeting',
    note: 'Internal note',
    noteLabel: 'Internal details',
    occurredAt: 'Activity date and time',
    outbound: 'Outbound',
    permissionAllowed: 'Channel permission: contact is allowed.',
    permissionRestricted: 'Caution: this channel is restricted. Check permission before any real contact.',
    permissionUnknown: 'Channel permission is not determined. Check it before any real contact.',
    record: 'Record activity',
    recording: 'Recording…',
    stageChanged: 'Stage changed',
    selectChannel: 'Do not associate a channel',
    sentNothing: 'This record does not send an email or contact anyone.',
    summary: 'Summary',
    taskCancelled: 'Task cancelled',
    taskCompleted: 'Task completed',
    taskCreated: 'Task created',
    taskReopened: 'Task reopened',
    taskReminderAcknowledged: 'Reminder acknowledged',
    taskReminderSnoozed: 'Reminder snoozed',
    taskUnavailable: 'Related task',
    taskUpdated: 'Task updated',
    timeline: 'Sales timeline',
    type: 'Activity type',
    update: 'Save correction',
    updating: 'Saving correction…',
  },
}

const TYPE_LABEL_KEY = { note: 'note', call: 'call', email: 'email', meeting: 'meeting' }
const TASK_EVENT_LABEL_KEY = { created: 'taskCreated', updated: 'taskUpdated', completed: 'taskCompleted', cancelled: 'taskCancelled', reopened: 'taskReopened', reminder_acknowledged: 'taskReminderAcknowledged', reminder_snoozed: 'taskReminderSnoozed' }
const STAGE_LABELS = {
  new: { 'fr-CA': 'Nouveau', 'en-CA': 'New' }, qualifying: { 'fr-CA': 'Qualification', 'en-CA': 'Qualifying' }, qualified: { 'fr-CA': 'Qualifié', 'en-CA': 'Qualified' }, contacted: { 'fr-CA': 'Contacté', 'en-CA': 'Contacted' }, opportunity: { 'fr-CA': 'Opportunité', 'en-CA': 'Opportunity' }, proposal_sent: { 'fr-CA': 'Soumission envoyée', 'en-CA': 'Proposal sent' }, negotiation: { 'fr-CA': 'Négociation', 'en-CA': 'Negotiation' }, won: { 'fr-CA': 'Gagné', 'en-CA': 'Won' }, lost: { 'fr-CA': 'Perdu', 'en-CA': 'Lost' },
}

function copyFor(locale) {
  return COPY[locale] ?? COPY['fr-CA']
}

function localDateTimeValue(value = new Date()) {
  const offset = value.getTimezoneOffset() * 60_000
  return new Date(value.getTime() - offset).toISOString().slice(0, 16)
}

function formatActivityDate(value, locale, timezone) {
  try {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short', timeZone: timezone }).format(new Date(value))
  } catch {
    return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  }
}

function activityDirection(activity, strings) {
  return strings[activity.direction] ?? activity.direction
}

function channelPermissionMessage(channel, strings) {
  const status = channel?.permission?.status
  if (status === 'allowed') return { tone: 'allowed', text: strings.permissionAllowed }
  if (status === 'do_not_contact' || status === 'opted_out') return { tone: 'restricted', text: strings.permissionRestricted }
  return { tone: 'unknown', text: strings.permissionUnknown }
}

function isChannelCompatible(type, channel) {
  if (type === 'call') return channel.channel_type === 'phone'
  if (type === 'email') return channel.channel_type === 'email'
  return false
}

export function ActivityTimeline({
  activities,
  taskEvents = [],
  tasks = [],
  transitions = [],
  channels,
  locale = 'fr-CA',
  timezone,
  canCreate,
  canCorrectAny,
  canCorrectSelf,
  currentUserId,
  submitting,
  onCreate,
  onCorrect,
}) {
  const strings = copyFor(locale)
  const timelineItems = useMemo(() => [
    ...activities.map((activity) => ({ kind: 'activity', occurredAt: activity.occurred_at, item: activity })),
    ...taskEvents.map((event) => ({ kind: 'task-event', occurredAt: event.occurred_at, item: event })),
    ...transitions.map((transition) => ({ kind: 'transition', occurredAt: transition.occurred_at, item: transition })),
  ].sort((left, right) => new Date(right.occurredAt) - new Date(left.occurredAt)), [activities, taskEvents, transitions])
  const tasksById = useMemo(() => new Map(tasks.map((task) => [task.id, task])), [tasks])
  return <section className="administration-card activity-timeline-card" aria-labelledby="prospect-timeline-title">
    <div className="activity-timeline-heading"><div><div className="administration-card-icon lime"><Clock3 size={21} /></div><h2 id="prospect-timeline-title">{strings.timeline}</h2></div></div>
    {canCreate && <ActivityComposer channels={channels} locale={locale} submitting={submitting} onCreate={onCreate} />}
    <ol className="prospect-activity-list" aria-label={strings.timeline}>
      {timelineItems.length ? timelineItems.map(({ kind, item }) => {
        if (kind === 'activity') return <ActivityItem key={`activity-${item.id}`} activity={item} locale={locale} timezone={timezone} strings={strings} canCorrect={canCorrectAny || (canCorrectSelf && item.actor_id === currentUserId)} submitting={submitting} onCorrect={onCorrect} />
        if (kind === 'task-event') return <TaskEventItem key={`task-event-${item.id}`} event={item} task={tasksById.get(item.task_id)} locale={locale} timezone={timezone} strings={strings} />
        return <TransitionItem key={`transition-${item.id}`} transition={item} locale={locale} timezone={timezone} strings={strings} />
      }) : <li className="form-help">{strings.empty}</li>}
    </ol>
  </section>
}

function ActivityComposer({ channels, locale, submitting, onCreate }) {
  const strings = copyFor(locale)
  const [type, setType] = useState('note')
  const [direction, setDirection] = useState('internal')
  const [summary, setSummary] = useState('')
  const [note, setNote] = useState('')
  const [occurredAt, setOccurredAt] = useState(() => localDateTimeValue())
  const [channelId, setChannelId] = useState('')
  const availableChannels = useMemo(() => channels.filter((channel) => isChannelCompatible(type, channel)), [channels, type])
  const selectedChannel = availableChannels.find((channel) => channel.id === channelId)
  const permission = selectedChannel ? channelPermissionMessage(selectedChannel, strings) : null

  function changeType(nextType) {
    setType(nextType)
    setDirection(nextType === 'call' || nextType === 'email' ? 'outbound' : 'internal')
    setChannelId('')
  }

  async function submit(event) {
    event.preventDefault()
    const saved = await onCreate({
      activity_type: type,
      direction,
      summary: summary.trim(),
      note: note.trim() || undefined,
      occurred_at: new Date(occurredAt).toISOString(),
      contact_channel_id: channelId || undefined,
    })
    if (saved) {
      setSummary('')
      setNote('')
      setOccurredAt(localDateTimeValue())
      setChannelId('')
    }
  }

  return <form className="activity-composer" onSubmit={submit}>
    <h3>{strings.add}</h3>
    <div className="activity-composer-grid">
      <label htmlFor="activity-type">{strings.type}<select id="activity-type" value={type} onChange={(event) => changeType(event.target.value)} disabled={submitting}>
        {Object.entries(TYPE_LABEL_KEY).map(([value, key]) => <option value={value} key={value}>{strings[key]}</option>)}
      </select></label>
      <label htmlFor="activity-direction">{strings.direction}<select id="activity-direction" value={direction} onChange={(event) => setDirection(event.target.value)} disabled={submitting || (type !== 'call' && type !== 'email')}>
        <option value="internal">{strings.internal}</option><option value="outbound">{strings.outbound}</option><option value="inbound">{strings.inbound}</option>
      </select></label>
      <label htmlFor="activity-occurred-at">{strings.occurredAt}<input id="activity-occurred-at" type="datetime-local" value={occurredAt} max={localDateTimeValue()} onChange={(event) => setOccurredAt(event.target.value)} required disabled={submitting} /></label>
      {(type === 'call' || type === 'email') && <label htmlFor="activity-channel">{strings.channelOptional}<select id="activity-channel" value={channelId} onChange={(event) => setChannelId(event.target.value)} disabled={submitting}>
        <option value="">{strings.selectChannel}</option>{availableChannels.map((channel) => <option key={channel.id} value={channel.id}>{channel.channel_type} · {channel.value}</option>)}
      </select></label>}
    </div>
      <label htmlFor="activity-summary">{strings.summary}<input id="activity-summary" value={summary} maxLength="160" onChange={(event) => setSummary(event.target.value)} required disabled={submitting} /></label>
    <label htmlFor="activity-note">{strings.noteLabel}<textarea id="activity-note" value={note} maxLength="4000" rows="3" onChange={(event) => setNote(event.target.value)} disabled={submitting} /></label>
    <p className="activity-declarative-notice"><AlertTriangle size={16} />{strings.sentNothing}</p>
    {permission && <p className={`activity-permission-notice ${permission.tone}`} role={permission.tone === 'restricted' ? 'alert' : undefined}>{permission.text}</p>}
    <button className="primary-button" type="submit" disabled={submitting}>{submitting ? strings.recording : strings.record}</button>
  </form>
}

function ActivityItem({ activity, locale, timezone, strings, canCorrect, submitting, onCorrect }) {
  const [correcting, setCorrecting] = useState(false)
  return <li className="prospect-activity-item"><article>
    <div className="activity-item-header"><div><strong>{strings[TYPE_LABEL_KEY[activity.activity_type]] ?? activity.activity_type}</strong><span>{activityDirection(activity, strings)}</span></div><time dateTime={activity.occurred_at}>{formatActivityDate(activity.occurred_at, locale, timezone)}</time></div>
    <p>{activity.summary}</p>{activity.note && <p className="activity-note-content">{activity.note}</p>}
    {activity.correction_of_activity_id && <small className="activity-correction-badge"><Check size={13} />{strings.correctionTitle}</small>}
    {canCorrect && !activity.correction_of_activity_id && <button className="link-button activity-correction-toggle" type="button" onClick={() => setCorrecting((current) => !current)}>{strings.correction}</button>}
    {correcting && <ActivityCorrectionForm activity={activity} strings={strings} submitting={submitting} onCorrect={async (payload) => { if (await onCorrect(activity, payload)) setCorrecting(false) }} />}
  </article></li>
}

function TaskEventItem({ event, task, locale, timezone, strings }) {
  return <li className="prospect-activity-item"><article>
    <div className="activity-item-header"><div><strong>{strings[TASK_EVENT_LABEL_KEY[event.event_type]] ?? event.event_type}</strong><span>{task?.title ?? strings.taskUnavailable}</span></div><time dateTime={event.occurred_at}>{formatActivityDate(event.occurred_at, locale, timezone)}</time></div>
    {event.reason && <p className="activity-note-content">{event.reason}</p>}
  </article></li>
}

function TransitionItem({ transition, locale, timezone, strings }) {
  const fromStage = STAGE_LABELS[transition.from_stage]?.[locale] ?? transition.from_stage
  const toStage = STAGE_LABELS[transition.to_stage]?.[locale] ?? transition.to_stage
  return <li className="prospect-activity-item"><article>
    <div className="activity-item-header"><div><strong>{strings.stageChanged}</strong><span>{`${fromStage} → ${toStage}`}</span></div><time dateTime={transition.occurred_at}>{formatActivityDate(transition.occurred_at, locale, timezone)}</time></div>
  </article></li>
}

function ActivityCorrectionForm({ activity, strings, submitting, onCorrect }) {
  const [summary, setSummary] = useState(activity.summary)
  const [note, setNote] = useState(activity.note ?? '')
  const [occurredAt, setOccurredAt] = useState(() => localDateTimeValue(new Date(activity.occurred_at)))
  const [reason, setReason] = useState('')
  return <form className="activity-correction-form" onSubmit={(event) => { event.preventDefault(); onCorrect({ summary: summary.trim(), note: note.trim() || undefined, occurred_at: new Date(occurredAt).toISOString(), correction_reason: reason.trim() }) }}>
    <h4>{strings.correctionTitle}</h4><p>{strings.correctionDescription}</p>
      <label htmlFor={`activity-correction-summary-${activity.id}`}>{strings.summary}<input id={`activity-correction-summary-${activity.id}`} value={summary} maxLength="160" onChange={(event) => setSummary(event.target.value)} required disabled={submitting} /></label>
    <label htmlFor={`activity-correction-note-${activity.id}`}>{strings.noteLabel}<textarea id={`activity-correction-note-${activity.id}`} value={note} maxLength="4000" rows="2" onChange={(event) => setNote(event.target.value)} disabled={submitting} /></label>
    <label htmlFor={`activity-correction-date-${activity.id}`}>{strings.occurredAt}<input id={`activity-correction-date-${activity.id}`} type="datetime-local" value={occurredAt} max={localDateTimeValue()} onChange={(event) => setOccurredAt(event.target.value)} required disabled={submitting} /></label>
    <label htmlFor={`activity-correction-reason-${activity.id}`}>{strings.correctionReason}<input id={`activity-correction-reason-${activity.id}`} value={reason} maxLength="500" onChange={(event) => setReason(event.target.value)} required disabled={submitting} /></label>
    <button className="secondary-button" type="submit" disabled={submitting}>{submitting ? strings.updating : strings.update}</button>
  </form>
}

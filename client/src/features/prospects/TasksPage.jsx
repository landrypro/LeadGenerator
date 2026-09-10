import { useCallback, useEffect, useRef, useState } from 'react'

import { Check, Clock3, LoaderCircle } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { createRequestId } from '../../shared/ids/requestId'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { prospectApi } from './api/prospectApi'
import { TaskRow } from './components/TaskPanel'

export function TasksPage({ session }) {
  const [tasks, setTasks] = useState([])
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const controllerRef = useRef(null)
  const locale = session.active_organization?.locale ?? 'fr-CA'
  const timezone = session.active_organization?.timezone

  const load = useCallback(async () => {
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    setLoading(true)
    setError('')
    try {
      const [taskPage, reminderPage] = await Promise.all([
        prospectApi.listTasks({ mine: true, status: 'open' }, controller.signal),
        prospectApi.listDueReminders({ mine: true }, controller.signal),
      ])
      setTasks(taskPage.items ?? [])
      setReminders(reminderPage.items ?? [])
    } catch (requestError) {
      if (requestError?.name !== 'AbortError') setError(toUserMessage(requestError, 'Impossible de charger vos tâches.'))
    } finally {
      if (controllerRef.current === controller) controllerRef.current = null
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(); return () => controllerRef.current?.abort() }, [load])

  async function act(task, action, extra = {}) {
    setSubmitting(true)
    setError('')
    try {
      await prospectApi.taskAction(task.id, action, { version: task.version, idempotency_key: createRequestId(), ...extra })
      setSuccess(locale === 'en-CA' ? 'Task updated.' : 'La tâche a été mise à jour.')
      await load()
      return true
    } catch (requestError) {
      setError(toUserMessage(requestError, locale === 'en-CA' ? 'Unable to update the task.' : 'Impossible de modifier la tâche.'))
      return false
    } finally {
      setSubmitting(false)
    }
  }

  const title = locale === 'en-CA' ? 'My tasks' : 'Mes tâches'
  return <main className="administration-page tasks-page" aria-labelledby="tasks-title">
    <header className="administration-page-heading"><p className="eyebrow">{locale === 'en-CA' ? 'Sales workspace' : 'Espace commercial'}</p><h1 id="tasks-title">{title}</h1><p>{locale === 'en-CA' ? 'Open tasks and internal reminders assigned to you.' : 'Vos tâches ouvertes et vos rappels internes.'}</p></header>
    {error && <ErrorBanner><span>{error}</span><button className="link-button" type="button" onClick={load}>{locale === 'en-CA' ? 'Retry' : 'Réessayer'}</button></ErrorBanner>}{success && <div className="success-banner" role="status"><Check size={18} />{success}</div>}
    {loading ? <div className="administration-loading" role="status"><LoaderCircle className="spin" size={20} />{locale === 'en-CA' ? 'Loading tasks…' : 'Chargement des tâches…'}</div> : <div className="tasks-layout"><section className="administration-card" aria-labelledby="due-reminders-title"><div className="administration-card-icon lime"><Clock3 size={21} /></div><h2 id="due-reminders-title">{locale === 'en-CA' ? 'Due reminders' : 'Rappels dus'}</h2><ul className="prospect-task-list">{reminders.length ? reminders.map((task) => <TaskRow key={task.id} task={task} locale={locale} timezone={timezone} reminderDue submitting={submitting} onAction={act} />) : <li className="form-help">{locale === 'en-CA' ? 'No reminder is due.' : 'Aucun rappel n’est dû.'}</li>}</ul></section><section className="administration-card" aria-labelledby="my-open-tasks-title"><h2 id="my-open-tasks-title">{locale === 'en-CA' ? 'Open tasks' : 'Tâches ouvertes'}</h2><ul className="prospect-task-list">{tasks.length ? tasks.map((task, index) => <TaskRow key={task.id} task={task} locale={locale} timezone={timezone} isNext={index === 0} submitting={submitting} onAction={act} />) : <li className="form-help">{locale === 'en-CA' ? 'No open task.' : 'Aucune tâche ouverte.'}</li>}</ul></section></div>}
  </main>
}

const TEXT = {
  'fr-CA': { late: 'En retard', today: 'Aujourd’hui', upcoming: 'À venir' },
  'en-CA': { late: 'Overdue', today: 'Today', upcoming: 'Upcoming' },
}

export function taskDueState(task, locale, now = new Date()) {
  const due = new Date(task.due_at)
  const copy = TEXT[locale] ?? TEXT['fr-CA']
  if (task.is_overdue || due < now) return { className: 'overdue', label: copy.late }
  if (due.toDateString() === now.toDateString()) return { className: 'today', label: copy.today }
  return { className: 'upcoming', label: copy.upcoming }
}

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { axeViolations, formatViolations } from '../../../test/accessibility'
import { ActivityTimeline } from './ActivityTimeline'

const activity = {
  id: 'activity-1', actor_id: 'member-1', activity_type: 'call', direction: 'outbound', summary: 'Appel de suivi', note: 'Message laissé.',
  occurred_at: '2026-09-05T14:00:00Z', correction_of_activity_id: null,
}

const channels = [
  { id: 'phone-1', channel_type: 'phone', value: '+14185550101', permission: { status: 'do_not_contact' } },
  { id: 'email-1', channel_type: 'email', value: 'alex@example.ca', permission: { status: 'allowed' } },
]

describe('ActivityTimeline', () => {
  it('déclare une activité sans envoyer de message et avertit si le canal est restreint', async () => {
    const onCreate = vi.fn().mockResolvedValue(true)
    render(<ActivityTimeline activities={[activity]} channels={channels} locale="fr-CA" timezone="America/Toronto" canCreate canCorrectAny={false} canCorrectSelf={false} submitting={false} onCreate={onCreate} onCorrect={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Type d’activité'), { target: { value: 'call' } })
    fireEvent.change(screen.getByLabelText('Canal concerné (facultatif)'), { target: { value: 'phone-1' } })
    fireEvent.change(screen.getByLabelText('Résumé'), { target: { value: 'Appel consigné' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer l’activité' }))

    expect(screen.getByRole('alert')).toHaveTextContent('ce canal est restreint')
    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ activity_type: 'call', direction: 'outbound', contact_channel_id: 'phone-1', summary: 'Appel consigné' }))
    expect(screen.getByText('Cette déclaration n’envoie aucun courriel et ne contacte personne.')).toBeInTheDocument()
  })

  it('propose une correction append-only et les libellés anglais', async () => {
    const onCorrect = vi.fn().mockResolvedValue(true)
    render(<ActivityTimeline activities={[activity]} channels={channels} locale="en-CA" canCreate={false} canCorrectAny={false} canCorrectSelf currentUserId="member-1" submitting={false} onCreate={vi.fn()} onCorrect={onCorrect} />)

    fireEvent.click(screen.getByRole('button', { name: 'Correct' }))
    fireEvent.change(screen.getByLabelText('Reason for correction'), { target: { value: 'Typo corrected' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save correction' }))

    expect(screen.getByText('The original entry stays in the timeline. This new entry records its correction.')).toBeInTheDocument()
    expect(onCorrect).toHaveBeenCalledWith(activity, expect.objectContaining({ correction_reason: 'Typo corrected' }))
  })

  it('fusionne les transitions du pipeline et les événements de tâche dans la chronologie', () => {
    render(<ActivityTimeline activities={[activity]} taskEvents={[{
      id: 'task-event-1', task_id: 'task-1', event_type: 'completed', occurred_at: '2026-09-05T15:00:00Z', reason: null,
    }]} tasks={[{ id: 'task-1', title: 'Relance QA' }]} transitions={[{
      id: 'transition-1', from_stage: 'new', to_stage: 'qualifying', occurred_at: '2026-09-05T16:00:00Z',
    }]} channels={channels} locale="fr-CA" timezone="America/Toronto" canCreate={false} canCorrectAny={false} canCorrectSelf={false} submitting={false} onCreate={vi.fn()} onCorrect={vi.fn()} />)

    expect(screen.getByText('Étape modifiée')).toBeInTheDocument()
    expect(screen.getByText('Nouveau → Qualification')).toBeInTheDocument()
    expect(screen.getByText('Tâche terminée')).toBeInTheDocument()
    expect(screen.getByText('Relance QA')).toBeInTheDocument()
  })

  it('ne présente aucune violation axe', async () => {
    const { container } = render(<ActivityTimeline activities={[activity]} channels={channels} locale="fr-CA" timezone="America/Toronto" canCreate canCorrectAny canCorrectSelf currentUserId="member-1" submitting={false} onCreate={vi.fn()} onCorrect={vi.fn()} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})

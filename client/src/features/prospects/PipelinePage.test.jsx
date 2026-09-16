import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { prospectApi } from './api/prospectApi'
import { PipelinePage } from './PipelinePage'


vi.mock('./api/prospectApi', () => ({
  prospectApi: { pipelineBoard: vi.fn(), pipelineColumn: vi.fn(), moveStage: vi.fn(), reopen: vi.fn(), listNextActions: vi.fn() },
}))


const stages = [
  { code: 'new', labels: { 'fr-CA': 'Nouveau' }, color_token: 'slate' },
  { code: 'lost', labels: { 'fr-CA': 'Perdu' }, color_token: 'red' },
]
const newProspect = { id: 'prospect-new', internal_alias: 'Prospect à qualifier', priority: 1, version: 3 }
const laterProspect = { id: 'prospect-later', internal_alias: 'Prospect chargé ensuite', priority: 1, version: 1 }
const lostProspect = { id: 'prospect-lost', internal_alias: 'Prospect perdu', priority: 2, version: 4 }
const session = { capabilities: ['pipeline:read', 'pipeline:move', 'pipeline:reopen'] }


describe('PipelinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    prospectApi.pipelineBoard.mockResolvedValue({
      stages,
      columns: { new: [newProspect], lost: [lostProspect] },
      next_cursors: { new: 'next-new', lost: null },
    })
    prospectApi.moveStage.mockResolvedValue({})
    prospectApi.reopen.mockResolvedValue({})
    prospectApi.pipelineColumn.mockResolvedValue({ items: [laterProspect], next_cursor: null })
    prospectApi.listNextActions.mockResolvedValue({ items: [{ prospect_id: 'prospect-new', title: 'Appeler demain' }] })
  })

  it('réouvre un prospect perdu avec une action dédiée et des motifs compréhensibles', async () => {
    render(<PipelinePage session={session} />)

    expect(await screen.findByRole('button', { name: 'Réouvrir' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Gagné/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Réouvrir' }))
    expect(screen.getByRole('dialog', { name: 'Réouvrir le prospect' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Le prospect a repris contact' })).toBeInTheDocument()
    expect(screen.queryByText('customer_reengaged')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la réouverture' }))

    await waitFor(() => expect(prospectApi.reopen).toHaveBeenCalledWith(
      'prospect-lost',
      expect.objectContaining({ version: 4, reason_code: 'customer_reengaged' }),
    ))
  })

  it('demande une précision lorsque le motif autre est retenu', async () => {
    render(<PipelinePage session={session} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Réouvrir' }))
    fireEvent.change(screen.getByLabelText('Motif de réouverture'), { target: { value: 'other' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la réouverture' }))
    expect(await screen.findByText('Précisez le motif de réouverture.')).toBeInTheDocument()
    expect(prospectApi.reopen).not.toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Précisez le motif'), { target: { value: 'Reprise après une recommandation.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la réouverture' }))
    await waitFor(() => expect(prospectApi.reopen).toHaveBeenCalledWith(
      'prospect-lost',
      expect.objectContaining({ reason_code: 'other', reason_note: 'Reprise après une recommandation.' }),
    ))
  })

  it('marque un prospect perdu avec des motifs compréhensibles', async () => {
    render(<PipelinePage session={session} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Marquer perdu' }))
    expect(screen.getByRole('dialog', { name: 'Marquer le prospect comme perdu' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Le budget n’est pas disponible' })).toBeInTheDocument()
    expect(screen.queryByText('no_budget')).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Motif de perte'), { target: { value: 'no_budget' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la perte' }))

    await waitFor(() => expect(prospectApi.moveStage).toHaveBeenCalledWith(
      'prospect-new',
      expect.objectContaining({ to_stage: 'lost', version: 3, reason_code: 'no_budget' }),
    ))
  })

  it('charge une seconde page pour une colonne, jusqu’à la limite de 50 cartes', async () => {
    render(<PipelinePage session={session} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Charger plus' }))
    await waitFor(() => expect(prospectApi.pipelineColumn).toHaveBeenCalledWith(
      'new',
      { cursor: 'next-new', searchText: '' },
    ))
    expect(await screen.findByText('Prospect chargé ensuite')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Charger plus' })).not.toBeInTheDocument()
  })

  it('affiche la prochaine action fournie par le serveur sans modifier le déplacement', async () => {
    render(<PipelinePage session={{ ...session, capabilities: [...session.capabilities, 'tasks:read'] }} />)

    expect(await screen.findByText('Prochaine action : Appeler demain')).toBeInTheDocument()
    expect(prospectApi.listNextActions).toHaveBeenCalled()
  })
})

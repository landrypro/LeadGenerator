import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { axeViolations, formatViolations } from '../../../test/accessibility'
import { OpportunitySection } from './OpportunitySection'

const opportunity = {
  id: 'opportunity-1', name: 'Renouvellement', amount: '12500.5000', currency_code: 'CAD', probability: 40,
  stage_code: 'proposal', expected_close_on: '2026-10-15', overdue: false, version: 1,
}

describe('OpportunitySection', () => {
  it('normalise la virgule décimale fr-CA avant la création', async () => {
    const onCreate = vi.fn().mockResolvedValue(true)
    render(<OpportunitySection locale="fr-CA" canCreate submitting={false} onCreate={onCreate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'OPP-17 FR' } })
    fireEvent.change(screen.getByLabelText('Montant'), { target: { value: '1250,50' } })
    fireEvent.change(screen.getByLabelText('Échéance'), { target: { value: '2099-10-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’opportunité' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({
      amount: '1250.50',
    })))
  })

  it('accepte le point décimal en-CA et refuse une virgule ambiguë', async () => {
    const onCreate = vi.fn().mockResolvedValue(true)
    const { rerender } = render(<OpportunitySection locale="en-CA" canCreate submitting={false} onCreate={onCreate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'OPP-17 EN' } })
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '1250.50' } })
    fireEvent.change(screen.getByLabelText('Due date'), { target: { value: '2099-10-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create opportunity' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ amount: '1250.50' })))

    onCreate.mockClear()
    rerender(<OpportunitySection locale="en-CA" canCreate submitting={false} onCreate={onCreate} onTransition={vi.fn()} onReopen={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'OPP-17 EN' } })
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '1250,50' } })
    fireEvent.change(screen.getByLabelText('Due date'), { target: { value: '2099-10-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create opportunity' }))

    expect(onCreate).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Amount')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByText('Enter an amount greater than zero, with no more than four decimal places.')).toBeInTheDocument()
  })

  it('traduit tout le parcours opportunité en en-CA', () => {
    const onTransition = vi.fn()
    render(<OpportunitySection locale="en-CA" prospect={{ stage_code: 'new' }} opportunities={[opportunity]} canCreate canUpdate canClose canAlign submitting={false} onCreate={vi.fn()} onUpdate={vi.fn()} onTransition={onTransition} onReopen={vi.fn()} onAlign={vi.fn()} />)

    expect(screen.getByRole('heading', { name: 'Opportunities' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Add an opportunity' })).toBeInTheDocument()
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Amount')).toBeInTheDocument()
    expect(screen.getByLabelText('Currency')).toBeInTheDocument()
    expect(screen.getByLabelText('Probability (%)')).toBeInTheDocument()
    expect(screen.getByLabelText('Due date')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Won' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Lost' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Align pipeline' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByRole('heading', { name: 'Edit opportunity' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    fireEvent.click(screen.getByRole('button', { name: 'Align pipeline' }))
    expect(screen.getByLabelText('Pipeline alignment')).toBeInTheDocument()
    expect(screen.getByText('This transition is not allowed directly. Move the prospect one stage at a time in the Kanban.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))

    fireEvent.click(screen.getByRole('button', { name: 'Lost' }))
    expect(screen.getByLabelText('Loss reason')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'A competitor’s offer was selected' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm loss' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    expect(screen.queryByText('Perdue')).not.toBeInTheDocument()
    expect(screen.queryByText('Motif de perte')).not.toBeInTheDocument()
  })

  it('traduit la réouverture en en-CA', () => {
    const closedOpportunity = { ...opportunity, stage_code: 'lost', probability: 0 }
    render(<OpportunitySection locale="en-CA" opportunities={[closedOpportunity]} canReopen submitting={false} onCreate={vi.fn()} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen' }))
    expect(screen.getByLabelText('Reopen reason')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'New information is available' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm reopening' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('signale précisément un montant invalide sans envoyer de commande', () => {
    const onCreate = vi.fn()
    render(<OpportunitySection canCreate submitting={false} onCreate={onCreate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'Renouvellement' } })
    fireEvent.change(screen.getByLabelText('Montant'), { target: { value: '-1' } })
    fireEvent.change(screen.getByLabelText('Échéance'), { target: { value: '2099-10-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’opportunité' }))

    expect(onCreate).not.toHaveBeenCalled()
    expect(screen.getByText('Saisissez un montant supérieur à zéro, avec au plus quatre décimales.')).toBeInTheDocument()
    expect(screen.getByLabelText('Montant')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Montant')).toHaveFocus()
  })

  it('rend une erreur API sous le champ de devise concerné', async () => {
    const onCreate = vi.fn().mockResolvedValue({ fieldErrors: { currency_code: 'La devise est invalide.' } })
    render(<OpportunitySection canCreate submitting={false} onCreate={onCreate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Nom'), { target: { value: 'Renouvellement' } })
    fireEvent.change(screen.getByLabelText('Montant'), { target: { value: '100' } })
    fireEvent.change(screen.getByLabelText('Devise'), { target: { value: 'ZZZ' } })
    fireEvent.change(screen.getByLabelText('Échéance'), { target: { value: '2099-10-15' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer l’opportunité' }))

    await waitFor(() => expect(onCreate).toHaveBeenCalled())
    expect(screen.getByText('Saisissez un code de devise ISO à trois lettres, par exemple CAD ou USD.')).toBeInTheDocument()
    expect(screen.getByLabelText('Devise')).toHaveAttribute('aria-invalid', 'true')
  })

  it('demande un motif compréhensible avant de déclarer une opportunité perdue', async () => {
    const onTransition = vi.fn().mockResolvedValue(true)
    render(<OpportunitySection opportunities={[opportunity]} canClose canUpdate submitting={false} onCreate={vi.fn()} onTransition={onTransition} onReopen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Perdue' }))
    fireEvent.change(screen.getByLabelText('Motif de perte'), { target: { value: 'competitor' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la perte' }))

    expect(onTransition).toHaveBeenCalledWith(opportunity, 'lost', expect.objectContaining({ reason_code: 'competitor' }))
  })

  it('ferme le formulaire de perte avec Échap et restaure le focus sans mutation', async () => {
    const onTransition = vi.fn()
    render(<OpportunitySection opportunities={[opportunity]} canClose canUpdate submitting={false} onCreate={vi.fn()} onTransition={onTransition} onReopen={vi.fn()} />)

    const lossButton = screen.getByRole('button', { name: 'Perdue' })
    lossButton.focus()
    fireEvent.click(lossButton)
    expect(screen.getByLabelText('Motif de perte')).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByLabelText('Motif de perte')).not.toBeInTheDocument())
    await waitFor(() => expect(lossButton).toHaveFocus())
    expect(onTransition).not.toHaveBeenCalled()
  })

  it('ferme le formulaire de réouverture avec Échap et restaure le focus sans mutation', async () => {
    const closedOpportunity = { ...opportunity, stage_code: 'lost', probability: 0 }
    const onReopen = vi.fn()
    render(<OpportunitySection opportunities={[closedOpportunity]} canReopen submitting={false} onCreate={vi.fn()} onTransition={vi.fn()} onReopen={onReopen} />)

    const reopenButton = screen.getByRole('button', { name: 'Réouvrir' })
    reopenButton.focus()
    fireEvent.click(reopenButton)
    expect(screen.getByLabelText('Motif de réouverture')).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByLabelText('Motif de réouverture')).not.toBeInTheDocument())
    await waitFor(() => expect(reopenButton).toHaveFocus())
    expect(onReopen).not.toHaveBeenCalled()
  })

  it('ferme l’alignement avec Échap et restaure le focus sans mutation', async () => {
    const onAlign = vi.fn()
    render(<OpportunitySection prospect={{ stage_code: 'new' }} opportunities={[opportunity]} canAlign submitting={false} onCreate={vi.fn()} onTransition={vi.fn()} onReopen={vi.fn()} onAlign={onAlign} />)

    const alignButton = screen.getByRole('button', { name: 'Aligner le pipeline' })
    alignButton.focus()
    fireEvent.click(alignButton)
    expect(screen.getByRole('button', { name: 'Fermer' })).toHaveFocus()

    fireEvent.keyDown(window, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByLabelText('Alignement du pipeline')).not.toBeInTheDocument())
    await waitFor(() => expect(alignButton).toHaveFocus())
    expect(onAlign).not.toHaveBeenCalled()
  })

  it('exige la confirmation du montant avant un changement de devise', async () => {
    const onUpdate = vi.fn().mockResolvedValue(true)
    render(<OpportunitySection opportunities={[opportunity]} canUpdate submitting={false} onCreate={vi.fn()} onUpdate={onUpdate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    fireEvent.change(screen.getByLabelText('Devise'), { target: { value: 'USD' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    expect(onUpdate).not.toHaveBeenCalled()
    expect(screen.getByText('Confirmez le montant avant de modifier la devise.')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('J’ai confirmé le montant dans la nouvelle devise. Aucune conversion n’est appliquée.'))
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(opportunity, expect.objectContaining({
      amount: '12500.5000', currency_code: 'USD',
    })))
  })

  it('normalise la virgule décimale fr-CA lors d’une modification', async () => {
    const onUpdate = vi.fn().mockResolvedValue(true)
    render(<OpportunitySection locale="fr-CA" opportunities={[opportunity]} canUpdate submitting={false} onCreate={vi.fn()} onUpdate={onUpdate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Modifier' }))
    expect(screen.getByLabelText('Montant')).toHaveValue('12500,5000')
    fireEvent.change(screen.getByLabelText('Montant'), { target: { value: '1250,50' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(opportunity, expect.objectContaining({
      amount: '1250.50',
    })))
  })

  it('ne permet qu’une réaffectation isolée lorsque le responsable est désactivé', async () => {
    const inactiveOpportunity = { ...opportunity, owner_membership_id: 'disabled-member', owner_membership_is_active: false }
    const onUpdate = vi.fn().mockResolvedValue(true)
    render(<OpportunitySection opportunities={[inactiveOpportunity]} members={[{ membership_id: 'active-member', status: 'active', user: { display_name: 'Alex Gestionnaire' } }]} canUpdate canReassign submitting={false} onCreate={vi.fn()} onUpdate={onUpdate} onTransition={vi.fn()} onReopen={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Réaffecter le responsable' }))
    expect(screen.getByText('Le responsable est désactivé. Seule une réaffectation vers un membre actif est permise.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Responsable'), { target: { value: 'active-member' } })
    fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(onUpdate).toHaveBeenCalledWith(inactiveOpportunity, { owner_membership_id: 'active-member' }))
  })

  it('ne présente aucune violation axe', async () => {
    const { container } = render(<OpportunitySection opportunities={[opportunity]} canCreate canClose canUpdate canReopen submitting={false} onCreate={vi.fn()} onTransition={vi.fn()} onReopen={vi.fn()} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})

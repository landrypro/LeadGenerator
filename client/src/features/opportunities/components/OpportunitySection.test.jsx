import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { axeViolations, formatViolations } from '../../../test/accessibility'
import { OpportunitySection } from './OpportunitySection'

const opportunity = {
  id: 'opportunity-1', name: 'Renouvellement', amount: '12500.5000', currency_code: 'CAD', probability: 40,
  stage_code: 'proposal', expected_close_on: '2026-10-15', overdue: false, version: 1,
}

describe('OpportunitySection', () => {
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

  it('ne présente aucune violation axe', async () => {
    const { container } = render(<OpportunitySection opportunities={[opportunity]} canCreate canClose canUpdate canReopen submitting={false} onCreate={vi.fn()} onTransition={vi.fn()} onReopen={vi.fn()} />)
    expect(formatViolations(await axeViolations(container))).toEqual([])
  })
})

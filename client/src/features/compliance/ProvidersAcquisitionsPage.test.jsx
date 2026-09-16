import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { complianceApi } from './api/complianceApi'
import { ProvidersAcquisitionsPage } from './ProvidersAcquisitionsPage'


vi.mock('./api/complianceApi', () => ({
  complianceApi: {
    listProviders: vi.fn(), listAcquisitions: vi.fn(), createProvider: vi.fn(), declareAcquisition: vi.fn(),
  },
}))


describe('ProvidersAcquisitionsPage', () => {
  beforeEach(() => {
    complianceApi.listProviders.mockResolvedValue({ items: [{ id: 'provider-1', label: 'Registre public', source_kind: 'open_data', status: 'active', allowed_territories: ['CA-QC'], allowed_purposes: ['commercial_follow_up'], allowed_data_categories: ['business_identity'], version: 1 }] })
    complianceApi.listAcquisitions.mockResolvedValue({ items: [] })
    complianceApi.createProvider.mockResolvedValue({ id: 'provider-2', label: 'Fournisseur QA', source_kind: 'csv', status: 'draft' })
    complianceApi.declareAcquisition.mockResolvedValue({ id: 'acquisition-1', source_label: 'Lot QA', territory: 'CA-QC', obtained_at: '2026-08-25T12:00:00Z', data_categories: ['business_identity'], status: 'approved' })
  })

  it('présente les fournisseurs et les protège par les capacités', async () => {
    render(<ProvidersAcquisitionsPage session={{ capabilities: ['providers:read', 'providers:manage', 'acquisitions:declare'] }} />)

    expect(await screen.findByText('Registre public')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Créer le brouillon' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Acquisitions' })).toBeInTheDocument()
  })

  it('réinitialise le formulaire fournisseur après une création réussie', async () => {
    render(<ProvidersAcquisitionsPage session={{ capabilities: ['providers:read', 'providers:manage'] }} />)

    await screen.findByText('Registre public')
    fireEvent.change(screen.getByLabelText('Nom du fournisseur'), { target: { value: 'Fournisseur QA' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le brouillon' }))

    await waitFor(() => expect(complianceApi.createProvider).toHaveBeenCalledWith({ source_kind: 'csv', label: 'Fournisseur QA' }))
    expect(await screen.findByText(/Fournisseur créé en brouillon/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Nom du fournisseur')).toHaveValue('')
    expect(screen.queryByText(/Cannot read properties of null/i)).not.toBeInTheDocument()
  })

  it('réinitialise le formulaire acquisition après une déclaration réussie', async () => {
    render(<ProvidersAcquisitionsPage session={{ capabilities: ['providers:read', 'acquisitions:declare'] }} />)

    await screen.findByText('Registre public')
    fireEvent.click(screen.getByRole('tab', { name: 'Acquisitions' }))
    fireEvent.change(screen.getByLabelText('Libellé de la source'), { target: { value: 'Lot QA' } })
    fireEvent.change(screen.getByLabelText('Date d’obtention'), { target: { value: '2026-08-25' } })
    fireEvent.click(screen.getByRole('button', { name: 'Déclarer l’acquisition' }))

    await waitFor(() => expect(complianceApi.declareAcquisition).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/Acquisition déclarée et approuvée/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Libellé de la source')).toHaveValue('')
    expect(screen.queryByText(/Cannot read properties of null/i)).not.toBeInTheDocument()
  })
})

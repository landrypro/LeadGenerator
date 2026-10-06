import { useCallback, useEffect, useState } from 'react'

import { Check, LoaderCircle, Settings2 } from '../../icons'
import { toUserMessage } from '../../shared/api/errors'
import { ErrorBanner } from '../../shared/ui/Feedback'
import { automationApi } from './api/automationApi'


const COPY = {
  'fr-CA': {
    eyebrow: 'ADMINISTRATION', title: 'Automatisation', intro: 'Pilotez l’accès de l’organisation aux fonctions Automation sans déclencher de Playbook ni d’action CRM.',
    loading: 'Chargement des paramètres Automation…', unavailable: 'Paramètres Automation indisponibles.', retry: 'Réessayer', organization: 'Organisation active', global: 'Déploiement global', enabled: 'Activée', suspended: 'Suspendue', globalEnabled: 'Disponible', globalDisabled: 'Désactivé par le serveur', effective: 'État effectif', effectiveOn: 'Disponible pour cette organisation', effectiveOff: 'Non disponible', version: 'Version de configuration', generation: 'Génération de suspension', updated: 'Dernière mise à jour',
    activate: 'Activer l’Automatisation', suspend: 'Suspendre l’Automatisation', confirm: 'Confirmer', cancel: 'Annuler', confirmEnable: 'Confirmez l’activation pour cette organisation. Aucun Playbook ne sera activé automatiquement.', confirmDisable: 'Confirmez la suspension pour cette organisation. Les actions déjà préparées restent consultables.', saving: 'Enregistrement…', saved: 'Paramètres Automation enregistrés.', stale: 'La configuration a changé. Rechargez la page avant de réessayer.', error: 'Impossible de modifier les paramètres Automation.', boundary: 'Garde-fous', boundaryText: 'Cette commande ne crée aucune tâche, ne modifie aucun prospect et n’envoie aucune communication externe.',
  },
  'en-CA': {
    eyebrow: 'ADMINISTRATION', title: 'Automation', intro: 'Control this organization’s access to Automation without activating a Playbook or creating a CRM effect.',
    loading: 'Loading Automation settings…', unavailable: 'Automation settings unavailable.', retry: 'Try again', organization: 'Active organization', global: 'Global rollout', enabled: 'Enabled', suspended: 'Suspended', globalEnabled: 'Available', globalDisabled: 'Disabled by server', effective: 'Effective state', effectiveOn: 'Available for this organization', effectiveOff: 'Unavailable', version: 'Configuration version', generation: 'Suspension generation', updated: 'Last updated',
    activate: 'Enable Automation', suspend: 'Suspend Automation', confirm: 'Confirm', cancel: 'Cancel', confirmEnable: 'Confirm enablement for this organization. No Playbook will be activated automatically.', confirmDisable: 'Confirm suspension for this organization. Existing prepared plans remain viewable.', saving: 'Saving…', saved: 'Automation settings saved.', stale: 'The configuration changed. Reload before trying again.', error: 'Unable to change Automation settings.', boundary: 'Safeguards', boundaryText: 'This command creates no task, changes no prospect, and sends no external communication.',
  },
}


function formatDate(value, locale) {
  if (!value) return '—'
  try { return new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) } catch { return value }
}


export function AutomationSettingsPage({ session, onAutomationAvailabilityChanged }) {
  const locale = session.active_organization?.locale === 'en-CA' ? 'en-CA' : 'fr-CA'
  const copy = COPY[locale]
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [pendingValue, setPendingValue] = useState(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async (signal) => {
    setLoading(true)
    setError('')
    try {
      const nextSettings = await automationApi.getSettings(signal)
      setSettings(nextSettings)
      onAutomationAvailabilityChanged?.(nextSettings.effective_enabled === true)
    } catch (cause) { if (cause?.name !== 'AbortError') setError(toUserMessage(cause, copy.unavailable)) }
    finally { if (!signal?.aborted) setLoading(false) }
  }, [copy.unavailable, onAutomationAvailabilityChanged])

  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
    return () => controller.abort()
  }, [load, locale])

  async function confirmChange() {
    if (!settings?.item || pendingValue === null || saving) return
    setSaving(true); setError(''); setNotice('')
    try {
      const updated = await automationApi.updateSettings(pendingValue, settings.item.version)
      setSettings(current => ({ ...current, ...updated }))
      onAutomationAvailabilityChanged?.(updated.effective_enabled === true)
      setPendingValue(null)
      setNotice(copy.saved)
    } catch (cause) {
      if (cause?.code === 'automation_settings_version_conflict') setError(copy.stale)
      else setError(toUserMessage(cause, copy.error))
    } finally { setSaving(false) }
  }

  if (loading && !settings) return <main className="administration-page automation-settings-page" aria-live="polite"><div className="administration-loading"><LoaderCircle className="spin" size={20} /> {copy.loading}</div></main>
  if (!settings) return <main className="administration-page automation-settings-page" aria-labelledby="automation-settings-error-title"><section className="route-status-card"><p className="eyebrow">{copy.eyebrow}</p><h1 id="automation-settings-error-title">{copy.unavailable}</h1><p>{error}</p><button className="secondary-button" type="button" onClick={() => load()}>{copy.retry}</button></section></main>

  const item = settings.item
  const enabled = item.automation_enabled === true
  const globalEnabled = settings.global_enabled === true
  const effectiveEnabled = settings.effective_enabled === true
  const canManage = session.capabilities?.includes('automation:settings:manage') === true

  return <main className="administration-page automation-settings-page" aria-labelledby="automation-settings-title">
    <header className="administration-page-heading">
      <p className="eyebrow">{copy.eyebrow}</p>
      <h1 id="automation-settings-title">{copy.title}</h1>
      <p>{copy.intro}</p>
    </header>
    {error && <ErrorBanner><span>{error}</span></ErrorBanner>}
    {notice && <div className="success-banner" role="status"><Check size={18} /><span>{notice}</span></div>}
    <div className="organization-grid automation-settings-grid">
      <section className="administration-card" aria-labelledby="automation-settings-summary-title">
        <div className="administration-card-icon"><Settings2 size={22} /></div>
        <h2 id="automation-settings-summary-title">{copy.organization}</h2>
        <dl className="account-details organization-details">
          <div><dt>{copy.organization}</dt><dd>{session.active_organization?.name ?? '—'}</dd></div>
          <div><dt>{copy.effective}</dt><dd><span className={`organization-status ${effectiveEnabled ? 'active' : 'suspended'}`}>{effectiveEnabled ? copy.effectiveOn : copy.effectiveOff}</span></dd></div>
          <div><dt>{copy.version}</dt><dd>{item.version}</dd></div>
          <div><dt>{copy.generation}</dt><dd>{item.suspension_generation}</dd></div>
          <div><dt>{copy.updated}</dt><dd>{formatDate(item.updated_at, locale)}</dd></div>
        </dl>
      </section>
      <section className="administration-card automation-settings-control" aria-labelledby="automation-settings-control-title">
        <h2 id="automation-settings-control-title">{copy.global}</h2>
        <p className="administration-empty">{globalEnabled ? copy.globalEnabled : copy.globalDisabled}</p>
        <p className="automation-settings-state"><span className={`organization-status ${enabled ? 'active' : 'suspended'}`}>{enabled ? copy.enabled : copy.suspended}</span></p>
        {canManage && settings.global_enabled !== false && <>
          <button className="primary-button organization-submit" type="button" disabled={saving || pendingValue !== null} onClick={() => setPendingValue(!enabled)}>
            {enabled ? copy.suspend : copy.activate}
          </button>
          {pendingValue !== null && <div className="automation-settings-confirm" role="group" aria-label={copy.confirm}>
            <p>{pendingValue ? copy.confirmEnable : copy.confirmDisable}</p>
            <div className="button-row"><button className="primary-button" type="button" disabled={saving} onClick={confirmChange}>{saving ? copy.saving : copy.confirm}</button><button className="secondary-button" type="button" disabled={saving} onClick={() => setPendingValue(null)}>{copy.cancel}</button></div>
          </div>}
        </>}
        <div className="automation-settings-boundary"><strong>{copy.boundary}</strong><span>{copy.boundaryText}</span></div>
      </section>
    </div>
  </main>
}

import { useEffect, useMemo, useState } from 'react'

import { ErrorBanner } from '../../../shared/ui/Feedback'
import { ConfirmationDialog } from './ConfirmationDialog'


const ROLE_LABELS = Object.freeze({ admin: Object.freeze({ 'fr-CA': 'Administrateur', 'en-CA': 'Administrator' }), manager: Object.freeze({ 'fr-CA': 'Gestionnaire', 'en-CA': 'Manager' }), sales: Object.freeze({ 'fr-CA': 'Commercial', 'en-CA': 'Sales' }) })


export function MemberEditor({ busy, conflictVersion, error, locale = 'fr-CA', member, onCancel, onReload, onSubmit }) {
  const copy = locale === 'en-CA' ? { edit: 'Edit', close: 'Close', newer: 'A newer version is available', conflict: 'Your entry was not applied. Loaded version: {version}. Current version: {conflictVersion}.', reload: 'Reload the list before continuing', role: 'Role', status: 'Status', active: 'Active', disabled: 'Disabled', saving: 'Saving…', save: 'Save member', confirmTitle: 'Confirm sensitive change', confirm: 'Confirm change', warningBoth: 'will disable this member and remove their Administrator role', warningDisable: 'will disable this member', warningRole: 'will remove their Administrator role', sessions: 'Affected sessions will be invalidated by the server.' } : { edit: 'Modifier', close: 'Fermer', newer: 'Une version plus récente existe', conflict: 'Votre saisie n’a pas été appliquée. Version chargée : {version}. Version actuelle : {conflictVersion}.', reload: 'Recharger la liste avant de continuer', role: 'Rôle', status: 'État', active: 'Actif', disabled: 'Désactivé', saving: 'Enregistrement…', save: 'Enregistrer le membre', confirmTitle: 'Confirmer la modification sensible', confirm: 'Confirmer la modification', warningBoth: 'désactivera ce membre et retirera son rôle Administrateur', warningDisable: 'désactivera ce membre', warningRole: 'retirera son rôle Administrateur', sessions: 'Les sessions concernées seront invalidées par le serveur.' }
  const [draft, setDraft] = useState({ role: member.role, status: member.status })
  const [confirmation, setConfirmation] = useState(null)

  useEffect(() => {
    setDraft({ role: member.role, status: member.status })
    setConfirmation(null)
  }, [member])

  const changes = useMemo(() => {
    const next = {}
    if (draft.role !== member.role) next.role = draft.role
    if (draft.status !== member.status) next.status = draft.status
    return next
  }, [draft, member])
  const hasChanges = Object.keys(changes).length > 0

  function submit(event) {
    event.preventDefault()
    if (!hasChanges || busy) return
    const disablesMember = member.status !== 'disabled' && draft.status === 'disabled'
    const removesAdministrator = member.role === 'admin' && draft.role !== 'admin'
    if (disablesMember || removesAdministrator) {
      setConfirmation({ changes, disablesMember, removesAdministrator })
      return
    }
    onSubmit(changes)
  }

  return <section className="member-editor" aria-labelledby="member-editor-title">
    <div className="member-editor-heading">
      <div>
        <h2 id="member-editor-title">{copy.edit} {member.user.display_name}</h2>
        <p>{member.user.email}</p>
      </div>
      <button className="text-button" type="button" onClick={onCancel} disabled={busy}>{copy.close}</button>
    </div>

    {error && <ErrorBanner compact><span>{error}</span></ErrorBanner>}
    {conflictVersion && <div className="conflict-banner" role="alert">
      <h3>{copy.newer}</h3>
      <p>{copy.conflict.replace('{version}', member.version).replace('{conflictVersion}', conflictVersion)}</p>
      <button className="secondary-button" type="button" onClick={onReload}>{copy.reload}</button>
    </div>}

    <form className="member-edit-form" onSubmit={submit}>
      <label htmlFor={`member-role-${member.membership_id}`}>{copy.role}</label>
      <select id={`member-role-${member.membership_id}`} value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value })}>
        {Object.entries(ROLE_LABELS).map(([value, labels]) => <option key={value} value={value}>{labels[locale]}</option>)}
      </select>
      <label htmlFor={`member-status-${member.membership_id}`}>{copy.status}</label>
      <select id={`member-status-${member.membership_id}`} value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
        <option value="active">{copy.active}</option>
        <option value="disabled">{copy.disabled}</option>
      </select>
      <button className="primary-button" type="submit" disabled={!hasChanges || busy}>
        {busy ? copy.saving : copy.save}
      </button>
    </form>

    {confirmation && <ConfirmationDialog
      title={copy.confirmTitle}
      confirmLabel={copy.confirm}
      busy={busy}
      onCancel={() => setConfirmation(null)}
      onConfirm={() => onSubmit(confirmation.changes)}
    >
      <p>
        {locale === 'en-CA' ? 'This action ' : 'Cette action '}{confirmation.disablesMember && confirmation.removesAdministrator
          ? copy.warningBoth : confirmation.disablesMember ? copy.warningDisable : copy.warningRole}.
        {copy.sessions}
      </p>
    </ConfirmationDialog>}
  </section>
}


export { ROLE_LABELS }

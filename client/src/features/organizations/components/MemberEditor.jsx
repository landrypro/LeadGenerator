import { useEffect, useMemo, useState } from 'react'

import { ConfirmationDialog } from './ConfirmationDialog'


const ROLE_LABELS = { admin: 'Administrateur', manager: 'Gestionnaire', sales: 'Commercial' }


export function MemberEditor({ busy, conflictVersion, error, member, onCancel, onReload, onSubmit }) {
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
        <h2 id="member-editor-title">Modifier {member.user.display_name}</h2>
        <p>{member.user.email}</p>
      </div>
      <button className="text-button" type="button" onClick={onCancel} disabled={busy}>Fermer</button>
    </div>

    {error && <div className="error-banner compact" role="alert"><span>{error}</span></div>}
    {conflictVersion && <div className="conflict-banner" role="alert">
      <h3>Une version plus récente existe</h3>
      <p>Votre saisie n’a pas été appliquée. Version chargée : {member.version}. Version actuelle : {conflictVersion}.</p>
      <button className="secondary-button" type="button" onClick={onReload}>Recharger la liste avant de continuer</button>
    </div>}

    <form className="member-edit-form" onSubmit={submit}>
      <label htmlFor={`member-role-${member.membership_id}`}>Rôle</label>
      <select id={`member-role-${member.membership_id}`} value={draft.role} onChange={(event) => setDraft({ ...draft, role: event.target.value })}>
        {Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </select>
      <label htmlFor={`member-status-${member.membership_id}`}>État</label>
      <select id={`member-status-${member.membership_id}`} value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>
        <option value="active">Actif</option>
        <option value="disabled">Désactivé</option>
      </select>
      <button className="primary-button" type="submit" disabled={!hasChanges || busy}>
        {busy ? 'Enregistrement…' : 'Enregistrer le membre'}
      </button>
    </form>

    {confirmation && <ConfirmationDialog
      title="Confirmer la modification sensible"
      confirmLabel="Confirmer la modification"
      busy={busy}
      onCancel={() => setConfirmation(null)}
      onConfirm={() => onSubmit(confirmation.changes)}
    >
      <p>
        Cette action {confirmation.disablesMember && confirmation.removesAdministrator
          ? 'désactivera ce membre et retirera son rôle Administrateur'
          : confirmation.disablesMember ? 'désactivera ce membre' : 'retirera son rôle Administrateur'}.
        Les sessions concernées seront invalidées par le serveur.
      </p>
    </ConfirmationDialog>}
  </section>
}


export { ROLE_LABELS }

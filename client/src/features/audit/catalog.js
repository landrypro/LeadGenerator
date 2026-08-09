export const TENANT_ACTIONS = Object.freeze([
  ['organization.updated', 'Organisation modifiée'],
  ['account.organization_preference_changed', 'Organisation active changée'],
  ['membership.role_changed', 'Rôle d’un membre modifié'],
  ['membership.status_changed', 'État d’un membre modifié'],
  ['invitation.created', 'Invitation créée'],
  ['invitation.resend_requested', 'Renvoi d’invitation demandé'],
  ['invitation.delivery_completed', 'Livraison d’invitation terminée'],
  ['invitation.revoked', 'Invitation révoquée'],
  ['invitation.accepted', 'Invitation acceptée'],
  ['organization.activated', 'Organisation activée'],
])

export const PLATFORM_ACTIONS = Object.freeze([
  ['organization.provisioned', 'Organisation provisionnée'],
  ['organization.initial_invitation.created', 'Invitation initiale créée'],
  ['organization.initial_invitation.resend_requested', 'Renvoi initial demandé'],
  ['organization.initial_invitation.delivery_completed', 'Livraison initiale terminée'],
  ['organization.initial_invitation.revoked', 'Invitation initiale révoquée'],
])

export const ENTITY_TYPES = Object.freeze([
  ['organization', 'Organisation'],
  ['membership', 'Appartenance'],
  ['invitation', 'Invitation'],
  ['user', 'Compte'],
])

const ACTION_LABELS = Object.freeze(Object.fromEntries([...TENANT_ACTIONS, ...PLATFORM_ACTIONS]))
const ROLE_LABELS = Object.freeze({ admin: 'Administrateur', manager: 'Gestionnaire', sales: 'Commercial' })
const STATUS_LABELS = Object.freeze({
  active: 'Actif',
  disabled: 'Désactivé',
  pending: 'En attente',
  sent: 'Envoyée',
  failed: 'Échec',
})
const FIELD_LABELS = Object.freeze({ name: 'Nom', locale: 'Langue', timezone: 'Fuseau horaire' })
const DELIVERY_KIND_LABELS = Object.freeze({ initial: 'Initiale', resend: 'Renvoi' })


export function actionLabel(action) {
  return ACTION_LABELS[action] ?? 'Événement non pris en charge'
}


export function metadataRows(event) {
  if (event.schema_version !== 1 || !ACTION_LABELS[event.action]) return []
  const metadata = event.metadata ?? {}
  let rows
  switch (event.action) {
    case 'organization.updated':
      rows = [['Champs modifiés', safeArray(metadata.changed_fields).map((value) => FIELD_LABELS[value]).filter(Boolean).join(', ')]]
      break
    case 'account.organization_preference_changed':
      rows = [
        ['Ancienne appartenance', shortId(metadata.previous_membership_id)],
        ['Nouvelle appartenance', shortId(metadata.new_membership_id)],
      ]
      break
    case 'membership.role_changed':
      rows = [['Ancien rôle', ROLE_LABELS[metadata.previous_role]], ['Nouveau rôle', ROLE_LABELS[metadata.new_role]]]
      break
    case 'membership.status_changed':
      rows = [['Ancien état', STATUS_LABELS[metadata.previous_status]], ['Nouvel état', STATUS_LABELS[metadata.new_status]]]
      break
    case 'invitation.created':
    case 'organization.initial_invitation.created':
      rows = [
        ['Rôle proposé', ROLE_LABELS[metadata.role]],
        ['Livraison', STATUS_LABELS[metadata.delivery_status]],
      ]
      break
    case 'invitation.resend_requested':
    case 'organization.initial_invitation.resend_requested':
      rows = [['Tentative de livraison', shortId(metadata.delivery_attempt_id)]]
      break
    case 'invitation.delivery_completed':
    case 'organization.initial_invitation.delivery_completed':
      rows = [
        ['Résultat', STATUS_LABELS[metadata.delivery_status]],
        ['Type de livraison', DELIVERY_KIND_LABELS[metadata.delivery_kind]],
        ['Tentative', shortId(metadata.delivery_attempt_id)],
      ]
      break
    default:
      return []
  }
  return rows.filter(([, value]) => Boolean(value))
}


export function entityTypeLabel(entityType) {
  return Object.fromEntries(ENTITY_TYPES)[entityType] ?? 'Entité'
}


export function shortId(value) {
  return typeof value === 'string' && value ? value.slice(0, 8) : ''
}


function safeArray(value) {
  return Array.isArray(value) ? value : []
}

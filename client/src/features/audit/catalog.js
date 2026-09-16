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
  ['prospect.created', 'Prospect créé'],
  ['prospect.updated', 'Prospect modifié'],
  ['prospect.archived', 'Prospect archivé'],
  ['prospect.stage_changed', 'Étape commerciale modifiée'],
  ['pipeline.stage_settings_updated', 'Paramètres d’étape modifiés'],
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
  ['prospect', 'Prospect'],
  ['pipeline_stage_setting', 'Paramètre d’étape'],
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
const PROSPECT_FIELD_LABELS = Object.freeze({
  internal_alias: 'Nom interne',
  owner_id: 'Responsable',
  priority: 'Priorité',
  retention_review_at: 'Date de revue',
  stage_code: 'Étape commerciale',
  industry_label: 'Secteur',
  segment_code: 'Segment',
  size_band: 'Taille',
  address_line_1: 'Adresse',
  address_line_2: 'Complément d’adresse',
  city: 'Ville',
  region: 'Région',
  postal_code: 'Code postal',
  country_code: 'Pays',
  tags: 'Étiquettes',
})
const PROSPECT_ORIGIN_LABELS = Object.freeze({
  connector: 'Connecteur',
  google_place: 'Google Places',
  import: 'Import CSV',
  manual: 'Saisie manuelle',
  open_data: 'Données ouvertes',
})
const PIPELINE_STAGE_LABELS = Object.freeze({
  new: 'Nouveau',
  qualifying: 'Qualification',
  qualified: 'Qualifié',
  contacted: 'Contacté',
  opportunity: 'Opportunité',
  proposal_sent: 'Soumission envoyée',
  negotiation: 'Négociation',
  won: 'Gagné',
  lost: 'Perdu',
})
const LOSS_REASON_LABELS = Object.freeze({
  no_need: 'Pas de besoin',
  no_budget: 'Sans budget',
  no_response: 'Sans réponse',
  competitor: 'Concurrent retenu',
  timing: 'Moment inadapté',
  outside_territory: 'Hors territoire',
  invalid_or_duplicate: 'Invalide ou doublon',
  other: 'Autre',
})
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
    case 'prospect.created':
      rows = [['Provenance', PROSPECT_ORIGIN_LABELS[metadata.origin]]]
      break
    case 'prospect.updated':
      rows = [['Champs modifiés', safeArray(metadata.changed_fields).map((value) => PROSPECT_FIELD_LABELS[value]).filter(Boolean).join(', ')]]
      break
    case 'prospect.stage_changed':
      rows = [
        ['Étape précédente', PIPELINE_STAGE_LABELS[metadata.from_stage]],
        ['Nouvelle étape', PIPELINE_STAGE_LABELS[metadata.to_stage]],
        ['Version', versionChange(metadata.from_version, metadata.resulting_version)],
        ['Motif de perte', LOSS_REASON_LABELS[metadata.reason_code]],
      ]
      break
    case 'pipeline.stage_settings_updated':
      rows = [
        ['Étape', PIPELINE_STAGE_LABELS[metadata.stage_code]],
        ['Champs modifiés', safeArray(metadata.changed_fields).map((value) => ({ color_token: 'Couleur', labels: 'Libellés' })[value]).filter(Boolean).join(', ')],
      ]
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


function versionChange(fromVersion, resultingVersion) {
  return Number.isInteger(fromVersion) && Number.isInteger(resultingVersion)
    ? `${fromVersion} → ${resultingVersion}`
    : ''
}

# Incrément 2.5.1 — Modèle de données et migrations

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 2.5 — Socle prospects, conformité et conservation |
| Incrément | 2.5.1 — Modèle de données et migrations |
| Statut | Validé par le responsable produit |
| Validation produit | 14 août 2026 — validation des seize décisions de la section 10 |
| Prérequis | 2.4.5 clôturée ; migration `20260813_0008 (head)` |
| Dépendances | PostgreSQL, SQLAlchemy, Alembic, RLS et audit 2.4 |
| Hors périmètre | UI, appel Google, import, Kanban, facturation et connecteurs |

Ce document définit le premier lot technique de 2.5. Il crée le modèle persistant et les ports nécessaires aux lots
suivants, sans exposer encore de parcours commercial complet.

## 1. Objectifs

2.5.1 doit fournir :

- les tables locataires des prospects, contacts, canaux et provenance ;
- les clés, contraintes, index et relations empêchant les incohérences métier ;
- les politiques RLS et privilèges du rôle Web ;
- les ports applicatifs pour les futurs cas d’utilisation ;
- l’écriture d’audit atomique pour toute mutation du lot ;
- une migration réversible sur base vide, avec vérification `alembic check`.

## 2. Invariants du modèle

1. Toutes les tables métier portent `organization_id` et sont protégées par RLS.
2. Un prospect est un établissement suivi ; un contact est une personne ; un canal est une coordonnée exploitable.
3. Un canal appartient à exactement un prospect ou un contact, jamais aux deux.
4. Toute donnée persistante qui sera utilisée comme coordonnée possède une provenance référencée.
5. `google_place_id` est nullable et unique par organisation pour les prospects actifs.
6. Aucun champ descriptif Google n’est ajouté comme donnée CRM persistante dans ce lot.
7. Les valeurs de permission ne sont pas fusionnées avec la provenance.
8. Les suppressions métier sont logiques (`archived_at`) ; aucune purge physique n’est introduite.
9. Les versions optimistes (`version`) sont présentes sur les agrégats modifiables.
10. Toute mutation passe par un service applicatif et une unité de travail transactionnelle.
11. Le rôle Web n’a aucun privilège DDL ni DML direct hors fonctions/ports autorisés.
12. Les politiques RLS ne dépendent jamais d’un filtre fourni par le client.
13. Les identifiants et dates sont générés côté serveur.
14. Les contraintes de longueur, format et normalisation sont vérifiées en base et dans le domaine.
15. Chaque mutation produit au plus un événement d’audit métier dans la même transaction.
16. Une migration échouée est atomique et ne laisse pas un schéma partiellement installé.

## 3. Schéma relationnel

### 3.1 `prospects`

Colonnes minimales : `id`, `organization_id`, `google_place_id`, `internal_alias`, `origin`, `source_label`,
`acquisition_record_id` nullable, `owner_id` nullable, `stage_code` (`new` par défaut), `priority`, `version`,
`retention_review_at`, `created_at`, `updated_at`, `archived_at`.

Contraintes : alias non vide et borné, origine dans un enum contrôlé, version positive, FK organisation/propriétaire,
unicité partielle active sur `(organization_id, google_place_id)` et index organisation/étape/propriétaire/revue.

### 3.2 `contacts`

Colonnes minimales : `id`, `organization_id`, `prospect_id`, `display_name`, `role_label`, `provenance_id`, `version`,
`created_at`, `updated_at`, `archived_at`.

Le prospect parent doit appartenir à la même organisation. L’archivage du parent ne supprime pas le contact et doit
être visible dans les requêtes de conformité.

### 3.3 `contact_channels`

Colonnes minimales : `id`, `organization_id`, `prospect_id` nullable, `contact_id` nullable, `channel_type`, `value`,
`value_normalized`, `provenance_id`, `purpose`, `obtained_at`, `verified_at`, `created_by`, `version`, `archived_at`.

Une contrainte impose exactement une cible (`prospect_id XOR contact_id`). `channel_type` vaut au minimum `email` ou
`phone`. La valeur normalisée est indexée sans être exposée dans les logs.

### 3.4 `provenance_records`

Colonnes minimales : `id`, `organization_id`, `source_kind`, `source_label`, `provider_id` nullable, `evidence_ref`,
`purpose`, `territory`, `obtained_at`, `verified_at`, `attested_by`, `created_at`.

La provenance est une référence interne ; elle ne contient pas le fichier brut ni le contenu d’un secret. Le domaine
refuse `source_kind=google_maps` pour une provenance de canal ou de coordonnée persistante.

### 3.5 Référentiel préparatoire

Les FK suivantes sont préparées pour les incréments ultérieurs : `source_providers`, `acquisition_records` et
`contact_permissions`. Si elles sont créées en 2.5.1, elles restent minimales, versionnées et sans écran de gestion.
La décision de créer ces référentiels maintenant ou dans 2.5.3 est soumise à validation ci-dessous.

## 4. RLS et privilèges

- contexte de session obligatoire : `app.organization_id` et, pour les opérations plateforme autorisées, un contexte
  explicitement séparé ;
- politiques `SELECT/INSERT/UPDATE` limitées à l’organisation active ;
- aucune politique permissive par défaut et aucun `USING (true)` sur une table locataire ;
- tests avec deux organisations : lecture, insertion, modification et jointure inter-organisation doivent être refusées ;
- les fonctions de contexte sont protégées contre la modification par le rôle Web ;
- les privilèges effectifs sont inspectés via `information_schema`, `pg_roles` et `pg_policies`.

## 5. Ports applicatifs et unité de travail

Introduire les interfaces suivantes sans implémentation mémoire de production :

- `ProspectRepository` : création, lecture par organisation, recherche par `google_place_id`, archivage optimiste ;
- `ContactRepository` et `ContactChannelRepository` : rattachement, recherche normalisée, archivage ;
- `ProvenanceRepository` : création et consultation d’une preuve ;
- `AuditRecorder` : événement append-only dans la transaction courante ;
- `UnitOfWork` : transaction, commit et rollback explicites ;
- `OrganizationContext` : organisation active validée côté serveur.

Les adaptateurs SQLAlchemy ne doivent pas être importés dans le domaine. Les routes ne manipulent pas directement les
modèles ORM et les sorties passent par des mappers explicites.

## 6. Migration Alembic

La migration doit :

1. créer les tables et types nécessaires dans un ordre compatible avec les FK ;
2. créer les index et contraintes avant d’activer les politiques RLS ;
3. activer RLS et les politiques locataires ;
4. accorder uniquement les privilèges prévus aux rôles migration, Web et RLS ;
5. fournir un `downgrade` symétrique réservé aux bases de test vides ;
6. être vérifiée par `upgrade head`, `current`, `check`, downgrade contrôlé puis reconstruction ;
7. ne pas modifier les migrations historiques 2.1 à 2.4.

Une révision dédiée, numérotée après `20260813_0008`, sera utilisée. Le numéro exact est attribué par Alembic au moment
de l’implémentation et reporté dans le rapport.

## 7. Audit et sécurité des données

Événements minimaux : `prospect.created`, `prospect.updated`, `prospect.archived`, `contact.created`,
`channel.created`, `provenance.recorded`. Les métadonnées contiennent uniquement identifiants, types et résultats ;
jamais la valeur d’un canal, un fichier, un jeton ou une clé Google.

Les lectures de listes et les erreurs de contrainte sont `no-store`. Aucune donnée du modèle n’est écrite dans
`localStorage`, `sessionStorage` ou une autre mémoire navigateur.

## 8. Tests obligatoires

- migration vierge, reconstruction et `alembic check` ;
- contraintes FK, XOR de cible, unicité active et version optimiste ;
- RLS sur deux organisations et privilèges effectifs du rôle Web ;
- refus d’une provenance absente et d’une provenance Google pour un canal ;
- atomicité mutation + audit sur commit et rollback ;
- absence de données sensibles dans les événements et journaux ;
- tests de ports/adaptateurs sans dépendance inverse ;
- Ruff, mypy et pytest sans `skip` ;
- non-régression complète des tests 2.4 et des règles Google existantes.

## 9. Critères de sortie

2.5.1 est terminé lorsque la migration est reconstruite sur base vide, les privilèges/RLS sont prouvés, les ports et
adaptateurs sont testés, les événements d’audit sont atomiques, les contrôles statiques sont verts et le rapport est
à jour. Aucun écran, import ou appel Google nouveau ne doit être requis pour déclarer ce lot terminé.

## 10. Seize décisions proposées à validation

1. 2.5.1 reste un lot backend/base sans changement visuel.
2. Les tables `prospects`, `contacts`, `contact_channels` et `provenance_records` sont créées dans cette migration.
3. Les référentiels `source_providers`, `acquisition_records` et `contact_permissions` sont créés minimalement dès 2.5.1.
4. Toutes les tables locataires portent `organization_id` et sont protégées par RLS.
5. La contrainte d’unicité active du `google_place_id` est `(organization_id, google_place_id)`.
6. Un canal possède exactement une cible : établissement ou personne.
7. Une provenance est obligatoire pour toute coordonnée persistante.
8. `google_maps` est interdit comme provenance d’une coordonnée persistante.
9. Les suppressions sont logiques et aucune purge physique n’est livrée.
10. Les agrégats utilisent une version optimiste côté domaine et base.
11. Les repositories, `UnitOfWork`, contexte d’organisation et audit sont définis par ports applicatifs.
12. Les modèles ORM restent confinés aux adaptateurs PostgreSQL.
13. Le rôle Web ne reçoit aucun DDL et aucun accès inter-organisation implicite.
14. La migration est réversible uniquement sur base de test vide et ne modifie pas l’historique.
15. Toute mutation de ce lot écrit son audit dans la même transaction.
16. Le passage à 2.5.2 exige migration, RLS, audit, tests et contrôles statiques verts, sans test ignoré.

## 11. Décision de sortie

- **Go implémentation 2.5.1** : les seize décisions sont validées ;
- **No-Go** : une décision reste ouverte ou une dépendance de sécurité n’est pas acceptée.

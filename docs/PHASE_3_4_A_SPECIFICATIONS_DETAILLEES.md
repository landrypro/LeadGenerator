# Phase 3.4-A — Spécifications détaillées : domaine et persistance des opportunités

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3.4 — Opportunités |
| Sous-lot | 3.4-A — Domaine et persistance |
| Version | 1.2 — implémentation et validation technique terminées |
| Prérequis | Décisions 3.4 validées ; tête de départ Alembic `20260905_0019` |
| Statut | Implémenté et techniquement validé le 10 septembre 2026 ; verrou local 3.4-A vert |
| Date | 10 septembre 2026 |

## 1. Objet et limites

Ce sous-lot définit le socle persistant des opportunités : objets métier, invariants purs, capacités, modèles
SQLAlchemy, ports, dépôts PostgreSQL et migration additive `20260910_0020`.

Il ne livre ni route HTTP, ni cas d’utilisation, ni audit applicatif, ni métrique, ni écran React, ni alignement du
pipeline prospect. Ces éléments appartiennent aux sous-lots 3.4-B à 3.4-D. Le GO d’implémentation 3.4-A a été reçu
le 10 septembre 2026 ; la réalisation et son état de vérification sont consignés dans le rapport associé.

La source fonctionnelle reste
[`PHASE_3_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_4_SPECIFICATIONS_DETAILLEES.md). Ce document en donne la
traduction technique sans introduire de nouvelle décision produit.

## 2. Livrables techniques attendus

- `backend/app/domain/opportunity.py` : énumérations, vues, brouillon de création et validations pures ;
- capacités `opportunities:*` dans `backend/app/domain/identity.py` ;
- ports `OpportunityRepository` et `OpportunityEventRepository` ;
- modèles `OpportunityModel` et `OpportunityEventModel`, exportés par `models/__init__.py` ;
- dépôts PostgreSQL branchés au `ProspectUnitOfWork` ;
- migration `20260910_0020_opportunity_foundation.py` ;
- tests de domaine, de contraintes SQL et d’isolation réelle PostgreSQL.

Les tables sont créées et sécurisées avant l’exposition de toute route navigateur.

## 3. Contrat de domaine

### 3.1 Codes et objets stables

Le domaine définit les `StrEnum` suivants :

| Type | Codes |
| --- | --- |
| `OpportunityStageCode` | `discovery`, `qualification`, `proposal`, `negotiation`, `won`, `lost` |
| `OpportunityEventType` | `created`, `updated`, `stage_changed`, `reopened` |
| `OpportunityLossReasonCode` | `no_need`, `no_budget`, `no_response`, `competitor`, `timing`, `scope_mismatch`, `invalid_or_duplicate`, `other` |
| `OpportunityReopenReasonCode` | `entered_in_error`, `customer_reengaged`, `additional_information`, `other` |

Les étapes ouvertes sont `discovery`, `qualification`, `proposal`, `negotiation`. Les étapes terminales sont `won` et
`lost`. Les libellés bilingues ne sont pas persistés : les codes restent des identifiants internes stables.

Les dataclasses gelées sont :

- `OpportunityDraft` : prospect, responsable, nom, `amount: Decimal`, devise, probabilité, date d’échéance et clé
  d’idempotence ;
- `OpportunityView` : données commerciales, tenant, prospect, responsable, état, version et horodatages ;
- `OpportunityEventView` : tenant, prospect, opportunité, acteur, type, étapes, versions, codes des champs modifiés,
  motif, clé et empreinte d’idempotence ;
- `OpportunityValidationError`, sans révéler de ressource d’une autre organisation.

### 3.2 Valeurs commerciales

`amount` est exclusivement un `Decimal`. Un `float`, zéro, une valeur négative, non finie ou ayant plus de quatre
décimales est rejeté avant persistance. L’intervalle accepté est `0.0001` à `999999999999999.9999`.

Le nom est normalisé par la routine CRM commune, non vide et limité à 160 caractères. Il est strictement interne :
aucun contenu Google, CSV ou d’acquisition ne le préremplit.

La devise est une chaîne ASCII de trois lettres majuscules présente dans une liste ISO 4217 contrôlée par le backend.
`CAD` est la valeur proposée, jamais une conversion. Les devises ne sont ni converties ni additionnées ; la valeur
pondérée est calculée à la lecture par `amount × probability / 100`, avec `Decimal`, quantifiée à quatre décimales et
jamais stockée.

`probability` est un entier de 0 à 100. Une création démarre en `discovery` avec une valeur proposée de 10, mais peut
recevoir explicitement une autre valeur valide. Un changement d’étape n’ajuste jamais automatiquement la probabilité.

`expected_close_on` est une `date` civile, sans heure. À la création, elle ne peut précéder le jour courant résolu dans
le fuseau de l’organisation. Le domaine reçoit ce jour de l’horloge applicative et ne consulte pas l’horloge système.
Le retard est dérivé à la lecture : il n’a ni colonne, ni transition, ni rappel automatique.

Le responsable est l’identifiant d’une appartenance active du même tenant. Le dépôt vérifie son existence, son tenant et
son statut dans la transaction. Une désactivation ne réaffecte rien automatiquement.

### 3.3 Cohérence d’état

| État | Probabilité | Motif de perte | `closed_at` |
| --- | ---: | --- | --- |
| Étape ouverte | 0 à 100 | absent | `NULL` |
| `won` | exactement 100 | absent | UTC non nul |
| `lost` | exactement 0 | code valide, note exigée pour `other` | UTC non nul |

La note de perte fait 1 à 500 caractères après normalisation et est absente hors de `lost`. Elle reste une donnée métier
visible seulement dans le détail autorisé ; audit minimisé, métriques et journaux structurés l’excluront.

Les règles de graphe, de fermeture et de réouverture seront exécutées par 3.4-B. Le schéma de 3.4-A rend toutefois les
états persistés incohérents impossibles.

## 4. Capacités et matrice de rôles

| Capacité | Administrateur | Gestionnaire | Commercial | Contrat futur |
| --- | --- | --- | --- | --- |
| `opportunities:read` | Oui | Oui | Oui | Commercial limité à ses opportunités |
| `opportunities:create` | Oui | Oui | Oui | Commercial crée pour lui-même |
| `opportunities:update` | Oui | Oui | Oui | Seulement si responsable actif |
| `opportunities:close` | Oui | Oui | Oui | Seulement si responsable actif |
| `opportunities:reopen` | Oui | Oui | Non | Réouverture interdite au Commercial |

La RLS isole le tenant. Elle ne remplace jamais les vérifications de rôle et de responsabilité du cas d’utilisation.

## 5. Schéma relationnel

### 5.1 Table `opportunities`

| Colonne | Type | Règle |
| --- | --- | --- |
| `id` | `UUID` | clé primaire générée serveur |
| `organization_id` | `UUID` | non nul, clé locataire |
| `prospect_id` | `UUID` | FK composite vers le prospect du même tenant |
| `owner_membership_id` | `UUID` | FK composite vers une appartenance du même tenant |
| `name` | `VARCHAR(160)` | texte CRM, 1 à 160 caractères |
| `amount` | `NUMERIC(19,4)` | positif et fini |
| `currency_code` | `CHAR(3)` | format majuscule ; ISO vérifiée par domaine |
| `probability` | `SMALLINT` | entier 0 à 100 |
| `stage_code` | `VARCHAR(32)` | six codes système |
| `expected_close_on` | `DATE` | non nul |
| `loss_reason_code`, `loss_reason_note` | `VARCHAR(64)`, `VARCHAR(500)` | seulement en perte |
| `closed_at` | `TIMESTAMPTZ` | seulement dans un état terminal |
| `created_by` | `UUID` | FK `users.id`, acteur interne |
| `version` | `INTEGER` | positif, défaut 1 |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | UTC, défaut serveur à la création |

Les références locataires sont :

- `(organization_id, prospect_id)` vers `prospects(organization_id, id)` ;
- `(organization_id, owner_membership_id)` vers `memberships(organization_id, id)` ;
- uniques `(organization_id, id)` et `(organization_id, prospect_id, id)` pour les références composites ultérieures.

Il n’existe aucune unicité sur `name`, aucun champ facture/devis/client, aucune source Google, aucun montant converti,
aucune valeur pondérée et aucun état Kanban du prospect.

Les contraintes SQL nommées comprennent au minimum :

```text
ck_opportunities_name_length
ck_opportunities_amount_positive_and_finite
ck_opportunities_currency_format
ck_opportunities_probability_range
ck_opportunities_stage_code_allowed
ck_opportunities_version_positive
ck_opportunities_loss_reason_note_length
ck_opportunities_terminal_state_consistency
```

La contrainte de montant teste `amount > 0` et `amount <> 'NaN'::numeric`, car PostgreSQL ordonne `NaN` au-dessus des
valeurs numériques ordinaires. `NUMERIC(19,4)` borne le stockage ; le domaine refuse une cinquième décimale pour éviter
un arrondi silencieux.

La contrainte terminale impose : aucune date ni aucun motif à l’étape ouverte, 100 et aucun motif pour `won`, 0, date et
motif admis pour `lost`. Le code `other` impose une note non vide.

### 5.2 Table append-only `opportunity_events`

| Colonne | Type | Règle |
| --- | --- | --- |
| `id` | `UUID` | clé primaire, résultat stable d’idempotence |
| `organization_id`, `prospect_id`, `opportunity_id` | `UUID` | référence composite au même tenant, prospect et opportunité |
| `actor_id` | `UUID` | FK `users.id` |
| `event_type` | `VARCHAR(32)` | type borné |
| `from_stage`, `to_stage` | `VARCHAR(32)` | six codes, cohérents avec le type |
| `from_version`, `resulting_version` | `INTEGER` | séquence de version positive |
| `changed_fields` | `JSONB` | objet de codes, sans valeurs commerciales |
| `reason_code`, `reason_note` | `VARCHAR(64)`, `VARCHAR(500)` | lorsque le parcours l’exige |
| `idempotency_key`, `command_fingerprint` | `VARCHAR(128)` | non nuls, opaques |
| `occurred_at` | `TIMESTAMPTZ` | UTC non nul |

La FK `(organization_id, prospect_id, opportunity_id)` pointe vers
`opportunities(organization_id, prospect_id, id)`. Elle interdit l’attachement d’un événement à l’opportunité d’un
autre prospect, y compris dans le même tenant.

Les contraintes couvrent les types, les étapes, la séquence de versions, le type objet de `changed_fields`, les longueurs
de motifs et la cohérence minimale type/étapes. Le graphe détaillé reste dans 3.4-B, jamais caché dans un déclencheur.

L’unicité `(organization_id, event_type, idempotency_key)` détecte le rejeu dans le tenant. L’empreinte permet à 3.4-B
de renvoyer le résultat historique pour une commande identique ou un conflit stable si la clé est réemployée avec une
charge différente. L’événement ne recopie ni nom, ni montant, ni devise, ni valeur pondérée.

### 5.3 Index

- `(organization_id, prospect_id, stage_code, expected_close_on, id)` pour la fiche prospect ;
- `(organization_id, owner_membership_id, stage_code, expected_close_on, id)` pour le portefeuille ;
- index partiel sur les étapes ouvertes, avec `expected_close_on` dans ses clés ; aucune expression dépendante de
  `CURRENT_DATE` n’est employée dans le prédicat ;
- `(organization_id, opportunity_id, occurred_at DESC, id DESC)` pour l’historique ;
- index unique d’idempotence ci-dessus.

## 6. Migration, RLS et privilèges

La migration `20260910_0020_opportunity_foundation.py` définit :

```python
revision = "20260910_0020"
down_revision = "20260905_0019"
```

Son `upgrade()` crée uniquement les deux tables, leurs contraintes, index et sécurité. Il ne modifie ni prospects ni
étapes Kanban et ne crée aucune opportunité artificielle. Son `downgrade()` retire d’abord `opportunity_events`, puis
`opportunities`, sans toucher les autres tables CRM.

Pour chaque table, la migration active et force RLS et crée une politique `FOR ALL TO prospect_app` :

```sql
USING (organization_id = app_private.current_organization_id())
WITH CHECK (organization_id = app_private.current_organization_id())
```

Elle révoque les droits de `PUBLIC` et de `prospect_app`, puis accorde :

| Table | Droits applicatifs |
| --- | --- |
| `opportunities` | `SELECT`, `INSERT`, `UPDATE` |
| `opportunity_events` | `SELECT`, `INSERT` |

Aucun `DELETE` n’est accordé. Aucun `UPDATE` ni `DELETE` n’est accordé sur `opportunity_events`, garantissant
l’append-only au niveau du rôle applicatif.

## 7. Dépôts et unité de travail

`OpportunityRepository` expose lecture par identifiant, liste tenant/prospect, insertion, verrouillage, mise à jour
versionnée et vérification du responsable actif. `OpportunityEventRepository` expose insertion append-only, lecture
chronologique et recherche d’idempotence. Ils sont disponibles dans `ProspectUnitOfWork` avec le `TenantContext` existant.

La primitive de mise à jour utilise `WHERE id = :id AND version = :expected_version RETURNING *`. L’absence de résultat
sera interprétée ultérieurement comme conflit ou invisibilité, jamais comme une réussite silencieuse. Les dépôts ne
calculent pas en `float`, ne déplacent pas le Kanban et n’émettent pas l’audit applicatif.

## 8. Tests obligatoires de sortie 3.4-A

### 8.1 Domaine

- accepte `Decimal("1250.2500")` et calcule exactement la valeur pondérée ;
- rejette `float`, zéro, négatif, `NaN`, infini et cinquième décimale ;
- rejette nom vide ou trop long, devise mal formée/non admise et probabilité hors bornes ;
- applique la date de création selon le calendrier de l’organisation, sans horloge système ;
- valide les trois états de la section 3.3, dont `lost/other` sans note refusé.

### 8.2 PostgreSQL réel

- `alembic upgrade head` depuis `20260905_0019`, puis `alembic current` à `20260910_0020` ;
- `alembic check` sans dérive ;
- insertion SQL refusée pour `NaN`, montant non positif, devise minuscule, probabilité invalide, clôture incohérente et
  note hors bornes ;
- FK composites refusant prospect, responsable ou événement inter-organisation ;
- FK ternaire refusant un événement dont le prospect diffère de celui de l’opportunité ;
- unicité d’idempotence effective ;
- `prospect_app` incapable de modifier/supprimer un événement ou de supprimer une opportunité.

### 8.3 Isolation réelle

Avec deux organisations et le rôle applicatif réel : A ne lit pas les lignes de B ; A ne peut ni créer ni rattacher une
opportunité au prospect ou membre de B ; un identifiant de B n’est pas modifiable par A ; RLS et `FORCE ROW LEVEL
SECURITY` sont vérifiés sur les deux tables. Les doubles en mémoire ne constituent pas une preuve suffisante.

Après implémentation, Ruff, format Ruff, mypy, tests unitaires et tests PostgreSQL ciblés doivent être verts, sans
`skip`. Le verrou global reste réservé à 3.4-D.

État final : Ruff, format Ruff, mypy, migration/reconstruction Alembic, 289 tests backend réels et 162 tests frontend
sont verts, sans échec ni skip. La tête vérifiée est `20260910_0020`. L’historique des corrections et les preuves sont
détaillés dans
[`PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_A_RAPPORT_IMPLEMENTATION.md).

## 9. Décision de sortie

Les seize décisions produit 3.4 sont validées et le GO explicite pour **l’implémentation de 3.4-A — Domaine et
persistance** a été donné le 10 septembre 2026. Le domaine, les capacités, les modèles, les ports, les dépôts et la
migration ont été livrés et validés sur PostgreSQL réel. Le verrou local 3.4-A est vert ; aucun GO pour 3.4-B n’est
implicitement accordé.

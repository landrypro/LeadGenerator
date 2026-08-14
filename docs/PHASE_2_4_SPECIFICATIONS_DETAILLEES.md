# Phase 2.4 — Spécifications détaillées de l’audit transactionnel

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.4 — Audit transactionnel |
| Version | 1.1 |
| Date | 9 août 2026 |
| Statut | 2.4.1 à 2.4.3 implémentés et recette cumulée conforme — Azure à confirmer |
| Validation produit | 9 août 2026 — seize décisions validées |
| Prérequis | 2.3.5-E officiellement clôturé le 9 août 2026 |
| Migration SQL prévue | Une révision Alembic après `20260802_0005` |
| Marché initial | Canada |

## 1. Objectif

2.4 rend chaque modification métier sensible explicable, attribuable et atomique. Il introduit un journal d’audit
append-only, isolé entre organisations, consultable selon les capacités et alimenté dans la même transaction
PostgreSQL que l’opération observée.

L’audit n’est ni un journal technique, ni un outil analytique, ni une copie des objets métier. Il conserve des codes
stables, des identifiants internes et des métadonnées minimales. Il prépare les écritures de 2.5 : établissements,
contacts, provenance, imports, connecteurs et politiques de conservation.

## 2. Résultat attendu

À la fin de 2.4 :

- chaque mutation couverte écrit au moins un événement dans sa transaction PostgreSQL ;
- un rollback métier ne laisse aucun événement et un échec d’audit annule la mutation ;
- le rôle Web ne peut ni modifier ni supprimer un événement ;
- Admin et Manager consultent uniquement l’audit de leur organisation active ;
- l’Administrateur de plateforme consulte uniquement les événements de portée plateforme ;
- la plateforme ne reçoit aucun accès implicite à l’audit locataire ;
- les organisations peuvent être suspendues et réactivées avec raison, version et audit ;
- toutes les invitations, y compris acceptées et révoquées, deviennent consultables ;
- aucun mot de passe, cookie, jeton, courriel invité, contenu Google, coordonnée, note ou preuve brute n’entre dans
  `metadata` ;
- les écrans sont paginés, accessibles, `no-store` et sans export.

## 3. Invariants hérités non négociables

1. L’organisation active et l’acteur proviennent de la session serveur.
2. Une commande locataire ne reçoit jamais librement `organization_id` du navigateur.
3. Le rôle PostgreSQL Web reste non propriétaire, non superutilisateur et sans `BYPASSRLS`.
4. Chaque transaction pose `actor_id`, `organization_id` éventuel et `request_id` avec une portée locale.
5. RLS reste activé et forcé pour toute table locataire.
6. Les mutations utilisent cookie `HttpOnly`, CSRF, JSON strict, capacités serveur et verrouillage optimiste.
7. La plateforme et les organisations restent deux périmètres d’autorisation distincts.
8. Les réponses d’identité, d’administration et d’audit portent `Cache-Control: no-store`.
9. Aucun secret ou contenu métier sensible n’est écrit dans les journaux techniques.
10. Google reste limité à un Text Search, vingt résultats, aucun contact, aucune pagination et aucune persistance.
11. Une suspension bloque tout appel Google avant d’atteindre le fournisseur.
12. Aucun audit, curseur ou filtre sensible n’est conservé dans le stockage Web.

## 4. Périmètre

### 4.1 Inclus

- table `audit_events` et primitive SQL append-only ;
- table d’idempotence des changements d’état d’organisation ;
- port `AuditRecorder` et modèle d’événement applicatif ;
- politique centralisée de métadonnées par code d’action ;
- adaptation des unités de travail locataire et plateforme ;
- couverture des mutations sensibles déjà livrées ;
- consultation locataire et plateforme par curseur ;
- écrans `/app/audit` et `/app/platform/audit` ;
- suspension et réactivation versionnées des organisations ;
- consultation des invitations actives et terminales ;
- tests unitaires, PostgreSQL réel, API, frontend, accessibilité et non-régression.

### 4.2 Explicitement exclu

- audit cryptographiquement scellé, WORM ou ancré dans un service externe ;
- export CSV, Excel ou PDF du journal ;
- recherche plein texte dans les métadonnées ;
- conservation d’adresse IP, empreinte d’appareil ou géolocalisation ;
- collecte du corps des requêtes ou réponses ;
- historique reconstitué artificiellement pour les opérations antérieures à 2.4 ;
- purge ou durée définitive de conservation des audits ;
- prospects, contacts, imports, connecteurs, abonnements et facturation ;
- audit détaillé des lectures ordinaires ;
- journal de sécurité persistant des échecs de connexion ou accès refusés ;
- modification des limites ou champs Google ;
- refonte graphique générale ou bilinguisme complet.

## 5. Distinction des journaux

| Type | Finalité | Exemples | Transaction métier |
| --- | --- | --- | --- |
| Audit métier | Expliquer une modification persistante réussie | rôle modifié, invitation révoquée, organisation suspendue | Même transaction |
| Journal technique | Exploiter et diagnostiquer | route, statut, durée, code d’erreur | Non |
| Journal de sécurité | Détecter un comportement hostile ou refusé | échecs agrégés, CSRF invalide | Hors 2.4 |
| Compteur d’usage | Quotas et coûts | recherche Google, carte, résolution de lieu | Hors audit métier |

Un refus ou une transaction annulée ne produit pas d’événement métier prétendant qu’une modification a réussi. Ces
tentatives alimentent uniquement les mécanismes techniques ou de sécurité minimisés prévus.

## 6. Acteurs et capacités

| Fonction | Plateforme | Admin | Manager | Sales |
| --- | :---: | :---: | :---: | :---: |
| Lire l’audit plateforme | Oui | Non | Non | Non |
| Lire l’audit de l’organisation active | Avec appartenance autorisée seulement | Oui | Oui | Non |
| Suspendre/réactiver une organisation | Oui | Non | Non | Non |
| Lire l’historique complet des invitations | Non | Oui | Non | Non |
| Modifier ou supprimer un événement | Non | Non | Non | Non |

Capacités utilisées ou ajoutées :

- `audit:read`, déjà attribuée à Admin et Manager ;
- `platform:audit:read`, attribuée au seul Administrateur de plateforme ;
- `platform:organizations:update_status`, attribuée au seul Administrateur de plateforme ;
- `invitations:read`, conservée pour l’Administrateur locataire.

La capacité plateforme ne permet jamais de lire les événements `tenant`. Un Administrateur de plateforme également
membre passe par la route locataire et son organisation active comme tout autre membre.

## 7. Modèle d’événement applicatif

L’objet immuable `AuditEventDraft` comprend :

- `scope` : `tenant` ou `platform` ;
- `action` : code stable, par exemple `membership.role_changed` ;
- `entity_type` et `entity_id` interne éventuel ;
- `actor_kind` : `user` ou `system` ;
- `actor_id`, obligatoire pour `user` ;
- `organization_id`, obligatoire pour `tenant` et renseigné si une organisation est la cible plateforme ;
- `request_id` provenant du middleware ;
- `correlation_id`, égal au `request_id` pour une requête simple et réutilisable par un futur worker ;
- `source` : `api`, `cli` ou `worker` ;
- `metadata`, construite par une politique typée et jamais par une route HTTP arbitraire ;
- `schema_version`, initialement `1`.

Le port applicatif expose :

```python
class AuditRecorder(Protocol):
    async def record(self, event: AuditEventDraft) -> UUID: ...
```

L’implémentation partage la session SQLAlchemy de l’unité de travail courante. Elle n’ouvre ni transaction ni
connexion indépendante et ne fait jamais de `commit()`.

## 8. Schéma PostgreSQL

### 8.1 Table `audit_events`

| Colonne | Type/règle |
| --- | --- |
| `id` | UUID, clé primaire, généré par l’application |
| `scope` | `VARCHAR`, `tenant` ou `platform` |
| `organization_id` | UUID nullable uniquement pour une portée plateforme sans cible organisation |
| `actor_kind` | `VARCHAR`, `user` ou `system` |
| `actor_id` | UUID nullable uniquement pour `system` |
| `action` | `VARCHAR(96)`, code stable validé |
| `entity_type` | `VARCHAR(64)`, code stable validé |
| `entity_id` | UUID nullable |
| `request_id` | `VARCHAR(128)`, obligatoire |
| `correlation_id` | `VARCHAR(128)`, obligatoire |
| `source` | `VARCHAR(16)`, `api`, `cli` ou `worker` |
| `metadata` | JSONB objet, `{}` par défaut, 8 Kio maximum |
| `schema_version` | `SMALLINT`, strictement positif |
| `occurred_at` | `TIMESTAMPTZ`, valeur serveur UTC |

Contraintes :

- `organization_id IS NOT NULL` pour `scope = 'tenant'` ;
- `actor_id IS NOT NULL` pour `actor_kind = 'user'` ;
- `action` et `entity_type` respectent une grammaire ASCII bornée ;
- `metadata` est un objet JSON et `octet_length(metadata::text) <= 8192` ;
- clés étrangères vers organisation et acteur en `ON DELETE RESTRICT` ;
- aucune colonne `updated_at` ou `deleted_at`.

Index minimaux :

- `(scope, organization_id, occurred_at DESC, id DESC)` ;
- `(scope, organization_id, entity_type, entity_id, occurred_at DESC, id DESC)` ;
- `(scope, actor_id, occurred_at DESC, id DESC)` ;
- `(request_id)` ;
- index plateforme partiel sur `(occurred_at DESC, id DESC)` pour `scope = 'platform'`.

### 8.2 Table `organization_status_operations`

Cette table protège les suspensions/réactivations contre les réponses réseau ambiguës :

- `id` UUID fourni comme `operation_id` ;
- `organization_id`, `requested_status`, `expected_version` ;
- `reason_code`, référence externe optionnelle strictement bornée ;
- `requested_by`, `resulting_version`, `created_at` ;
- empreinte canonique de la commande pour détecter un UUID réutilisé avec un autre contenu ;
- unicité globale de `id` et aucune donnée libre ou sensible.

La ligne d’opération, le changement d’organisation et l’audit sont écrits dans la même transaction.

## 9. Append-only et privilèges SQL

- le rôle de migration possède le schéma ; le rôle Web n’en est jamais propriétaire ;
- le rôle Web n’a aucun `INSERT`, `UPDATE`, `DELETE` ou `TRUNCATE` direct sur `audit_events` ;
- l’ajout passe uniquement par `app_private.append_audit_event`, fonction `SECURITY DEFINER` exécutable par le rôle
  Web après révocation du droit `PUBLIC` ;
- la fonction possède un `search_path` fixe, qualifie chaque objet SQL et appartient à un rôle non-login distinct du
  rôle Web ;
- la fonction valide contexte local, portée, acteur, organisation, formats et taille ;
- aucune fonction applicative de modification ou suppression n’est créée ;
- `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY` sont actifs ;
- toute maintenance future utilise un rôle distinct et une procédure documentée.

`organization_status_operations` applique également RLS et n’est accessible qu’au travers des cas d’utilisation
plateforme. Le rôle Web ne peut pas y modifier une intention déjà créée.

Les tests inspectent `information_schema`, `pg_roles`, `has_table_privilege` et les politiques avec le rôle réel.

## 10. Isolation RLS des lectures

L’unité de travail pose `app.audit_scope` côté serveur :

- `tenant` pour `/api/audit-events`, avec organisation active ;
- `platform` pour `/api/platform/audit-events`, après vérification plateforme.

La politique locataire exige `scope = 'tenant'`, l’organisation courante, `app.audit_scope = 'tenant'` et une
appartenance active Admin ou Manager. La politique plateforme exige `scope = 'platform'`,
`app.audit_scope = 'platform'` et le rôle `platform_admin` réel en base.

Sans contexte, avec un contexte incomplet ou une autre organisation, la requête retourne zéro ligne. Les routes ne
révèlent jamais l’existence d’un événement hors périmètre.

## 11. Politique de métadonnées

`AuditMetadataPolicy` associe chaque `action` à une liste blanche de clés, types et valeurs. Une clé inconnue est
rejetée avant l’écriture ; elle n’est pas supprimée silencieusement.

| Action | Métadonnées autorisées |
| --- | --- |
| `organization.updated` | `changed_fields` uniquement |
| `account.organization_preference_changed` | appartenances précédente et nouvelle, par identifiants internes |
| `membership.role_changed` | `previous_role`, `new_role` |
| `membership.status_changed` | `previous_status`, `new_status` |
| `invitation.created` | `role`, `invitation_kind`, `delivery_status` |
| `invitation.resend_requested` | identifiant interne de tentative, sans destinataire |
| `invitation.delivery_completed` | `delivery_status`, `delivery_kind`, identifiant interne de tentative |
| `organization.suspended` | `reason_code`, `operation_id`, référence externe bornée éventuelle |
| `organization.reactivated` | `reason_code`, `operation_id` |

Toujours interdits :

- nom, courriel ou téléphone d’une personne ;
- mot de passe, hachage, cookie, CSRF, jeton d’invitation ou de session ;
- clé, requête, réponse, nom, adresse, catégorie, coordonnées ou contact Google ;
- contenu de note, formulaire, fichier, preuve de consentement ou message ;
- secret, jeton OAuth, donnée bancaire ou contenu de réseau social ;
- adresse IP ou empreinte d’appareil dans 2.4 ;
- valeurs avant/après complètes d’une entité.

Les libellés sont reconstruits depuis les codes et catalogues frontend, pas stockés dans l’événement.

## 12. Catalogue minimal des actions

### Portée locataire

- `organization.updated` ;
- `account.organization_preference_changed` ;
- `membership.role_changed` ;
- `membership.status_changed` ;
- `invitation.created` ;
- `invitation.resend_requested` ;
- `invitation.delivery_completed` ;
- `invitation.revoked` ;
- `invitation.accepted` ;
- `organization.activated` lors de l’acceptation initiale.

### Portée plateforme

- `organization.provisioned` ;
- `organization.initial_invitation.created` ;
- `organization.initial_invitation.resend_requested` ;
- `organization.initial_invitation.delivery_completed` ;
- `organization.initial_invitation.revoked` ;
- `organization.suspended` ;
- `organization.reactivated`.

Une opération composite peut produire plusieurs événements avec le même `request_id`. Chaque événement correspond à
une transition autonome ; aucun événement générique supplémentaire n’est produit sans valeur métier.

`account.organization_preference_changed` décrit uniquement la préférence persistée dans PostgreSQL. La rotation du
cookie et de la session Redis reste un fait technique afin de ne pas annoncer un changement de session qui aurait
échoué après le commit. De même, une demande de livraison et son résultat final sont deux transitions distinctes :
l’audit ne marque jamais un courriel « envoyé » avant la finalisation réelle de la tentative.

Les futurs codes 2.5 sont ajoutés au registre sans modifier les anciens : établissement créé, contact créé,
provenance déclarée, import confirmé, ligne mise en quarantaine, connecteur révoqué et politique modifiée.

## 13. Sémantique transactionnelle

Ordre obligatoire d’une mutation :

1. ouvrir l’unité de travail avec contexte serveur ;
2. verrouiller et relire l’état nécessaire ;
3. valider capacité, version et transition ;
4. effectuer la modification métier ;
5. enregistrer les événements via `AuditRecorder` ;
6. valider la transaction une seule fois ;
7. effectuer ensuite seulement les effets externes conçus comme post-commit.

Si l’étape 5 échoue, l’étape 4 est annulée. Si le résultat du commit est inconnu, le client recharge l’état et ne
rejoue pas automatiquement une nouvelle intention.

Les hooks ORM globaux, middleware HTTP et files asynchrones ne créent pas les événements métier de 2.4 : ils ne
connaissent ni l’intention ni la bonne frontière transactionnelle.

## 14. Authentification, refus et événements techniques

Connexions, déconnexions, échecs agrégés, CSRF invalides et accès refusés restent des événements de sécurité ou logs
techniques dans 2.4. Ils ne sont pas forcés dans `audit_events`, car leur source de vérité est la session Redis et non
une mutation PostgreSQL atomique.

La spécification générale est ainsi raffinée : `audit_events` décrit les changements métier validés ; un futur
journal de sécurité pourra couvrir les tentatives sans exposer les identifiants essayés.

## 15. API de consultation

### 15.1 Routes

- `GET /api/audit-events` exige `audit:read` et l’organisation active ;
- `GET /api/platform/audit-events` exige `platform:audit:read` et retourne seulement `scope = 'platform'`.

### 15.2 Paramètres

- `limit` : 50 par défaut, 100 maximum ;
- `cursor` : opaque, versionné et lié au tri et aux filtres ;
- `occurred_from` et `occurred_to` : UTC, intervalle maximal de 90 jours ;
- `action`, choisi dans le registre ;
- `entity_type` et `entity_id` ;
- `actor_id`, uniquement interne et visible dans le périmètre.

Sans dates, la fenêtre initiale couvre trente jours. Le tri est `occurred_at DESC, id DESC`. Aucun total exact,
recherche libre, courriel ou filtre de métadonnée n’est proposé.

```json
{
  "items": [{
    "id": "uuid",
    "occurred_at": "2026-08-09T15:00:00Z",
    "action": "membership.role_changed",
    "entity_type": "membership",
    "entity_id": "uuid",
    "actor": {"id": "uuid", "display_name": "Gestionnaire"},
    "request_id": "request-id",
    "metadata": {"previous_role": "sales", "new_role": "manager"},
    "schema_version": 1
  }],
  "next_cursor": null
}
```

Le courriel de l’acteur est absent. Chaque réponse porte `Cache-Control: no-store` et `X-Request-ID`.

## 16. Suspension et réactivation plateforme

Routes :

- `POST /api/platform/organizations/{organization_id}/suspend` ;
- `POST /api/platform/organizations/{organization_id}/reactivate`.

```json
{
  "operation_id": "uuid",
  "version": 3,
  "reason_code": "customer_request",
  "external_reference": "TICKET-123"
}
```

Raisons initiales : `customer_request`, `billing`, `security`, `compliance`, `administrative`, `other`.
`external_reference` est optionnelle, limitée à 64 caractères sûrs et n’est pas une note libre.

Règles :

- seules `active -> suspended` et `suspended -> active` sont autorisées ;
- une organisation `provisioning` ne peut être suspendue par ces routes ;
- la version est obligatoire ; un conflit retourne `409` avec l’état courant minimisé ;
- même `operation_id` et même empreinte : même résultat, sans seconde mutation ni second événement ;
- même UUID avec autre contenu : `409 idempotency_conflict` ;
- la suspension ne supprime ni membres, invitations, données ni historique ;
- la réactivation ne réactive aucune appartenance ou invitation désactivée/révoquée ;
- dès le commit, aucune route locataire ou Google ne peut utiliser l’organisation ;
- un utilisateur peut basculer vers une autre organisation active ;
- la plateforme n’obtient aucun accès aux données locataires.

L’activité de l’organisation est relue côté serveur pour toute opération sensible ; une session ou un cache ancien ne
peut autoriser un accès après suspension.

## 17. Historique des invitations

L’historique vient de `user_invitations`, source de vérité de l’état, et non d’une reconstruction de l’audit.

`GET /api/organization/invitations` accepte :

- `state=open|active|expired|accepted|revoked|all`, `open` par défaut ;
- `limit` de 25 par défaut, 100 maximum ;
- un curseur stable `created_at, id` ;
- aucun total exact.

Seul `invitations:read` révèle destinataire et historique complet. L’audit lu par Manager montre actions et identifiants
d’invitation, jamais le courriel. Renvoi et Révocation restent conditionnés à `invitations:manage` et à l’état.

Les invitations antérieures restent visibles selon leur état actuel, mais leurs transitions passées ne sont pas
inventées dans l’audit.

## 18. Interface utilisateur

### 18.1 Audit locataire

- `/app/audit`, visible avec `audit:read` ;
- filtres période, action, type d’entité et acteur ;
- chronologie avec libellés centralisés ;
- détail limité aux métadonnées autorisées ;
- « Charger la suite », sans pagination numérique ni total fictif ;
- états chargement, vide, erreur, rafraîchissement et fin ;
- aucun export, impression spéciale ou stockage navigateur.

### 18.2 Plateforme

- `/app/platform/audit` avec `platform:audit:read` ;
- Suspendre/Réactiver avec confirmation explicite ;
- raison obligatoire et `operation_id` généré par intention ;
- même `operation_id` conservé après réponse ambiguë ;
- rechargement après conflit ;
- aucune donnée locataire dans la vue plateforme.

### 18.3 Invitations

- filtre « En cours / Tout l’historique » ;
- états Acceptée, Révoquée et Expirée distingués ;
- aucune action sur invitation terminale ;
- pagination accessible et focus restauré après mutation.

Les codes sont mappés dans des catalogues centralisés afin de préparer `fr-CA` et `en-CA`, sans imposer le chantier
bilingue complet à 2.4.

## 19. Erreurs publiques

| Situation | Réponse |
| --- | --- |
| Session absente | `401` |
| Capacité absente | `403` |
| Ressource hors organisation ou inconnue | `404` |
| Transition ou version invalide | `409` |
| Réutilisation divergente d’`operation_id` | `409 idempotency_conflict` |
| Filtre, curseur ou période invalide | `422` |
| PostgreSQL/audit indisponible | `503` avec `request_id` |

Aucune erreur n’expose SQL, politique RLS, métadonnée refusée, existence inter-organisation ou contenu sensible.

## 20. Conservation et exploitation

- aucun événement antérieur n’est fabriqué ;
- aucune suppression d’audit n’est exécutée en 2.4 ;
- la durée définitive reste configurable et à valider juridiquement/opérationnellement ;
- taille, croissance et latence de la table sont surveillées ;
- aucun partitionnement n’est ajouté avant mesure de volume ;
- sauvegardes, restauration et accès privilégiés font partie du dossier d’exploitation ;
- l’application seule ne peut rendre inviolable une action d’administrateur de base ; scellement externe/WORM reste
  une évolution distincte.

## 21. Tests obligatoires

### 21.1 Unitaires

- validation des actions et types d’entité ;
- listes blanches, types, taille et clés inconnues des métadonnées ;
- interdiction des champs sensibles et Google ;
- curseur et cohérence des filtres ;
- transitions de statut ;
- empreinte d’idempotence plateforme ;
- mappage des codes sans texte libre.

### 21.2 PostgreSQL réel

- migration depuis `20260802_0005`, base vide, `alembic current/check` et downgrade jetable ;
- événement absent après rollback et présent après succès ;
- échec d’append annulant le métier ;
- plusieurs événements sous un `request_id` ;
- rôle Web sans DML direct et modification/suppression refusées ;
- fonction append sans droit `PUBLIC`, avec propriétaire attendu et `search_path` fixe ;
- RLS entre deux organisations, sans contexte et avec mauvais scope ;
- plateforme incapable de lire le locataire et réciproquement ;
- métadonnée invalide/surdimensionnée rejetée ;
- contraintes et index nommés présents.

### 21.3 Cas d’utilisation et API

- chaque mutation du catalogue produit le bon événement ;
- aucun événement sur refus, validation ou conflit avant mutation ;
- acceptation initiale produisant invitation acceptée et organisation activée atomiquement ;
- filtres, ordre, curseur, fenêtre et limite ;
- `401`, `403`, `404`, `409`, `422`, `503` et `no-store` ;
- suspension bloquant administration locataire et Google avant fournisseur ;
- réactivation conservant les appartenances désactivées ;
- rejeu idempotent et UUID divergent ;
- historique incluant acceptées/révoquées sans rétro-audit inventé.

### 21.4 Frontend

- gardes des routes locataire et plateforme ;
- absence pour Sales et plateforme non autorisée ;
- filtres, chargement progressif et remise à zéro ;
- détails limités aux clés autorisées ;
- confirmation de statut et intention ambiguë ;
- historique et absence d’action terminale ;
- clavier, focus, régions live, 320 px, 200 % et axe ;
- absence d’audit, curseur, filtre ou `operation_id` dans les stockages Web.

### 21.5 Régression

- authentification, provisioning, invitations, rôles, changement d’organisation et administration ;
- un Text Search, vingt résultats, aucun contact, aucune pagination ;
- carte protégée et attribution Google Maps ;
- aucun fournisseur réel dans les tests automatiques ;
- Ruff, mypy, pytest réel zéro `skip`, ESLint, audit npm, Vitest, axe et build.

## 22. Découpage d’implémentation proposé

### 2.4.1 — Schéma et primitive append-only

- migration, table, contraintes, index, RLS et privilèges ;
- modèle, politique, port et adaptateur PostgreSQL ;
- tests d’atomicité, immutabilité et isolation.

État au 9 août 2026 : code implémenté sous la révision `20260809_0006`. Les contrôles sans infrastructure sont verts ;
la reconstruction et les trois tests PostgreSQL réels restent obligatoires avant le GO de 2.4.2. Le rapport est
disponible dans [`PHASE_2_4_1_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_1_RAPPORT_IMPLEMENTATION.md).

### 2.4.2 — Couverture des mutations existantes

- organisation, membres, invitations, provisioning, activation et changement de contexte ;
- aucune modification visuelle ;
- tests événement par événement et rollback.

État au 9 août 2026 : les seize décisions des spécifications détaillées sont validées et l’implémentation est
autorisée. Le contrat se trouve dans
[`PHASE_2_4_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_2_SPECIFICATIONS_DETAILLEES.md). La recette manuelle cumulée de
2.4.1 et 2.4.2 est différée, sur décision produit, à la fin de 2.4.3 ; les contrôles automatisés par incrément restent
obligatoires.

### 2.4.3 — Consultation et interfaces d’audit

- API locataire/plateforme, curseurs et filtres ;
- routes React, clients, hooks et composants accessibles ;
- catalogues préparant le bilinguisme.

État au 9 août 2026 : les spécifications détaillées et les seize décisions ont été validées puis implémentées. Le
contrat et les preuves sont disponibles dans
[`PHASE_2_4_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_3_SPECIFICATIONS_DETAILLEES.md) et
[`PHASE_2_4_3_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_3_RAPPORT_IMPLEMENTATION.md). La recette utilisateur cumulée de
2.4.1 à 2.4.3 a été validée le 9 août 2026. Par décision produit, le passage Azure est reporté au verrou final de la
phase 2.4 et ne bloque pas le GO de 2.4.4.

### 2.4.4 — Suspension, réactivation et historique

- opérations idempotentes ;
- mutations plateforme et blocage immédiat ;
- historique complet des invitations ;
- interface et tests de concurrence/résultat ambigu.

État au 13 août 2026 : les spécifications détaillées ont été validées puis implémentées. Le contrat et les preuves sont
disponibles dans
[`PHASE_2_4_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_4_SPECIFICATIONS_DETAILLEES.md) et
[`PHASE_2_4_4_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_4_RAPPORT_IMPLEMENTATION.md).

### 2.4.5 — Verrou qualité et documentation

- régression complète locale et Azure ;
- revue du schéma et des privilèges réels ;
- documentation technique, utilisateur et exploitation ;
- trois critiques, deux revues et Go/No-Go avant 2.5.

Les décisions détaillées et les critères de preuve sont définis dans
[`PHASE_2_4_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_5_SPECIFICATIONS_DETAILLEES.md). Les seize décisions ont été
validées par le responsable produit le 13 août 2026. L'implémentation du verrou et son Go/No-Go conditionnel sont
documentés dans [`PHASE_2_4_5_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_5_RAPPORT_IMPLEMENTATION.md).

## 23. Critique experte préalable

### 23.1 Architecture

Risque : middleware ou session indépendante produisant un audit mensonger après rollback. Réponse : appel explicite
dans le cas d’utilisation et session SQLAlchemy partagée.

Risque résiduel : oubli lors d’une future mutation. Réponse : registre d’actions, tests contractuels et revue de toute
nouvelle commande à partir de 2.4.

### 23.2 Sécurité et confidentialité

Risque : `metadata` devient un dépôt de données personnelles. Réponse : liste blanche typée, limite DB de 8 Kio,
aucun dictionnaire libre depuis les routes et tests négatifs.

Risque résiduel : un administrateur PostgreSQL reste puissant. Réponse : rôles séparés, sauvegardes et procédures ;
scellement externe hors V1.

### 23.3 Exploitation et produit

Risque : promettre un passé inexistant ou surcharger la table. Réponse : aucune reconstruction, pagination, index et
métriques de croissance.

Risque résiduel : durée de conservation non chiffrée. Réponse : aucune purge en 2.4 et décision avant production.

## 24. Seize décisions validées

1. Une table `audit_events` avec portées `tenant` et `platform`, strictement filtrées.
2. Aucun historique rétroactif ; seules les opérations postérieures à l’activation sont auditées.
3. Écriture explicite via `AuditRecorder` dans la même session et transaction que le métier.
4. Aucun DML direct du rôle Web ; primitive SQL append-only contrôlée.
5. Codes stables, identifiants internes, `request_id`, `correlation_id` et `schema_version`.
6. `metadata` sur liste blanche par action, 8 Kio maximum, sans donnée sensible, Google ou texte libre.
7. Isolation plateforme/locataire sans accès locataire implicite pour la plateforme.
8. Lecture locataire pour Admin/Manager, plateforme pour le rôle plateforme, aucune pour Sales.
9. Pagination `(occurred_at, id)`, 50 par défaut, 100 maximum et fenêtre de 90 jours.
10. Audit des mutations validées seulement ; refus et authentification relèvent des journaux de sécurité.
11. Couverture immédiate des mutations organisation, membre, invitation et provisioning existantes.
12. Suspension/réactivation versionnées et idempotentes avec `operation_id` et raison obligatoire.
13. Blocage immédiat du locataire et de Google après suspension, sans suppression ni réactivation implicite.
14. Historique d’invitations lu depuis les enregistrements métier, jamais reconstruit depuis l’audit.
15. Vues sans export ni stockage Web, accessibles et préparées pour les futurs catalogues bilingues.
16. Cinq sous-incréments, infrastructure réelle zéro `skip`, trois critiques, deux revues et GO avant 2.5.

Ces seize décisions ont été validées par le responsable produit le 9 août 2026. Elles constituent le contrat
normatif de l’incrément 2.4 ; toute dérogation doit être documentée et validée avant son implémentation.

## 25. Définition de « terminé »

2.4 est terminé uniquement si :

- les seize décisions validées sont respectées ou leurs dérogations documentées avant le code ;
- la migration reconstruit une base vide et passe `alembic check` ;
- audit et métier sont atomiques pour chaque cas couvert ;
- le rôle Web ne peut modifier, supprimer, tronquer ou insérer directement ;
- RLS prouve l’isolation locataire et plateforme ;
- aucun champ interdit n’est accepté ;
- APIs et écrans respectent capacités, curseurs, `no-store` et accessibilité ;
- la suspension bloque immédiatement locataire et appels facturables ;
- l’historique montre les états terminaux sans inventer le passé ;
- Google et l’absence de stockage navigateur n’ont pas régressé ;
- suites locales et Azure vertes avec zéro test d’infrastructure ignoré ;
- trois critiques et deux revues sans défaut bloquant ;
- GO produit explicite pour 2.5.

## 26. Références internes

- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_4_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_4_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_4_QA_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_QA_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_QA_DEPLOIEMENT_ORACLE.md`](PHASE_2_4_QA_DEPLOIEMENT_ORACLE.md)

## 27. Références techniques

- PostgreSQL Row Security Policies : https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- PostgreSQL Privileges : https://www.postgresql.org/docs/current/ddl-priv.html
- PostgreSQL `SET LOCAL` : https://www.postgresql.org/docs/current/sql-set.html
- PostgreSQL JSON Types : https://www.postgresql.org/docs/current/datatype-json.html
- SQLAlchemy — transactions et sessions : https://docs.sqlalchemy.org/en/20/orm/session_transaction.html
- OWASP Logging Cheat Sheet : https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

# Phase 2.4.2 — Spécifications détaillées de la couverture des mutations existantes

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.4.2 — Couverture des mutations existantes |
| Version | 1.1 |
| Date | 9 août 2026 |
| Statut | Implémenté — recette fonctionnelle différée à la fin de 2.4.3 |
| Validation produit | 9 août 2026 — seize décisions validées |
| Prérequis code | 2.4.1 implémenté sous `20260809_0006` |
| Validation produit 2.4.1 | Recette manuelle regroupée à la fin de 2.4.3 |
| Migration prévue | `20260809_0007`, après `20260809_0006` |
| Changement visuel | Aucun |
| Rapport | `PHASE_2_4_2_RAPPORT_IMPLEMENTATION.md` |

## 1. Objectif

2.4.2 branche le journal append-only de 2.4.1 sur toutes les mutations métier sensibles déjà livrées : organisation,
membres, invitations, provisioning, acceptation et changement d’organisation active.

Le résultat attendu est transactionnel : une transition PostgreSQL réussie produit exactement les événements prévus
dans la même transaction ; un événement impossible à écrire annule la transition. Les refus, conflits, lectures,
rejeux idempotents et opérations sans changement ne produisent aucun nouvel événement.

## 2. Décision de validation différée

Le responsable produit a choisi de regrouper ses tests fonctionnels manuels à la fin de 2.4.3, lorsque les événements
seront consultables dans l’API et l’interface.

Cette décision diffère uniquement la recette humaine. Elle ne diffère pas :

- les tests unitaires de chaque cas d’utilisation ;
- les tests PostgreSQL réels d’atomicité et d’idempotence ;
- la reconstruction Alembic et `alembic check` ;
- les tests de non-régression API et frontend ;
- Ruff, mypy, pytest, ESLint, Vitest, audit npm et build.

Un défaut de 2.4.1 ou 2.4.2 découvert avant 2.4.3 est corrigé dans son lot d’origine. Le GO d’implémentation de 2.4.3
ne vaut pas validation rétroactive des invariants PostgreSQL.

## 3. Invariants hérités

1. Le journal reste append-only et le rôle Web ne reçoit aucun DML direct.
2. `AuditRecorder` utilise la session PostgreSQL de la mutation et n’effectue jamais de `commit()`.
3. L’acteur, l’organisation et le `request_id` viennent uniquement du contexte serveur.
4. Les capacités sont contrôlées avant l’ouverture de toute mutation.
5. Les fonctions SQL conservent verrouillage, versions, RLS et règles d’idempotence existantes.
6. `metadata` est construite par `AuditMetadataPolicy`, jamais depuis un dictionnaire HTTP.
7. Aucun nom, courriel, téléphone, secret, jeton, donnée Google ou texte libre n’est audité.
8. Un refus ou un rollback ne produit aucun événement métier.
9. Un rejeu idempotent retourne le résultat existant sans ajouter d’événement.
10. Les effets Redis, SMTP et navigateur restent hors transaction PostgreSQL.
11. Google demeure à un Text Search, vingt résultats, aucun contact ni pagination.
12. Aucun historique antérieur à l’activation de 2.4.2 n’est reconstruit.

## 4. Périmètre

### 4.1 Inclus

- modification de l’organisation active ;
- changement de rôle ou de statut d’une appartenance ;
- création, renvoi, finalisation de livraison et révocation d’une invitation membre ;
- provisioning d’une organisation et de sa première invitation ;
- renvoi, finalisation et révocation de l’invitation initiale ;
- acceptation par un nouveau compte ou un compte existant ;
- activation initiale de l’organisation ;
- changement de préférence d’organisation active ;
- atomicité, rejeu, rollback, concurrence et absence de données interdites ;
- mise à jour des contrats de ports, unités de travail et fonctions SQL nécessaires.

### 4.2 Exclu

- API et écrans de consultation de l’audit, livrés en 2.4.3 ;
- suspension, réactivation et historique complet des invitations, livrés en 2.4.4 ;
- audit des connexions, déconnexions, CSRF invalides et refus d’accès ;
- audit des lectures ordinaires et appels Google ;
- événements de prospects, contacts, imports, Kanban, facturation ou connecteurs ;
- audit du bootstrap et de la réinitialisation de l’Administrateur de plateforme ;
- file de messages, outbox, changement visuel ou nouvelle route HTTP ;
- rétro-audit des données et opérations déjà présentes.

## 5. Architecture transactionnelle retenue

### 5.1 Problème actuel

Les adaptateurs `SqlAlchemyOrganizationAdministrationGateway` et `SqlAlchemyProvisioningGateway` ouvrent et valident
actuellement leurs propres unités de travail. Un cas d’utilisation ne peut donc pas effectuer la mutation, appeler
`AuditRecorder`, puis valider les deux une seule fois.

Ajouter l’audit après le retour du gateway créerait deux transactions et violerait l’atomicité. Ajouter l’audit dans
un middleware, un hook ORM ou une connexion séparée créerait le même défaut.

### 5.2 Solution

Les mutations auditées passent par des unités de travail applicatives spécialisées :

- `TenantAuditedUnitOfWork` pour organisation, membres et invitations membre ;
- `PlatformAuditedUnitOfWork` pour provisioning et invitations initiales ;
- `InvitationAcceptanceUnitOfWork` pour les acceptations avant authentification complète ;
- `ActorAuditedUnitOfWork` pour la préférence d’organisation active.

Chaque unité de travail expose des opérations métier liées à sa session et un `AuditRecorder` lié à la même session.
Le cas d’utilisation :

1. contrôle la capacité et valide la commande avant la transaction ;
2. ouvre l’unité de travail avec le contexte serveur ;
3. exécute l’opération métier ;
4. construit les événements à partir du résultat de transition typé ;
5. appelle explicitement `AuditRecorder.record()` dans un ordre déterministe ;
6. appelle une seule fois `commit()` ;
7. exécute ensuite les effets externes prévus.

Les méthodes d’adaptateur appelées dans cette unité de travail ne créent ni session ni transaction et ne font aucun
`commit()`. Les gateways de lecture peuvent conserver leur forme actuelle.

### 5.3 Contrat indicatif

```python
class TenantAuditedUnitOfWork(UnitOfWork, Protocol):
    mutations: TenantMutationGateway
    audit: AuditRecorder
```

Le nom exact peut être ajusté pendant l’implémentation, mais les propriétés suivantes sont normatives : même session,
transaction unique, orchestration explicite par le cas d’utilisation et absence de dépendance SQLAlchemy dans
l’application.

## 6. Faits de transition

Les fonctions SQL retournent un résultat typé contenant uniquement les faits minimaux nécessaires à l’audit :

- code `updated`, `created`, `replayed`, `unchanged`, `revoked`, `already_revoked`, `accepted` ou erreur métier ;
- identifiants internes des entités réellement modifiées ;
- valeurs codifiées avant/après nécessaires à la politique ;
- liste des champs d’organisation effectivement modifiés ;
- identifiant et type de tentative de livraison ;
- indicateur `transitioned` lors d’une finalisation idempotente ;
- appartenance précédente et nouvelle pour le changement de préférence.

Ces faits ne contiennent jamais de courriel, jeton, mot de passe, nom d’organisation, contenu de message ou réponse
brute. Ils ne sont pas renvoyés par l’API : l’adaptateur les traduit vers les résultats applicatifs existants.

## 7. Matrice normative des événements

| Transition réellement effectuée | Portée | Événement(s) | `entity_type` / `entity_id` | Métadonnées |
| --- | --- | --- | --- | --- |
| Organisation modifiée | tenant | `organization.updated` | `organization` / organisation | `changed_fields` réellement changés |
| Rôle d’un membre modifié | tenant | `membership.role_changed` | `membership` / appartenance | `previous_role`, `new_role` |
| Statut d’un membre modifié | tenant | `membership.status_changed` | `membership` / appartenance | `previous_status`, `new_status` |
| Rôle et statut modifiés ensemble | tenant | les deux événements précédents | même appartenance | métadonnées propres à chaque action |
| Invitation membre créée | tenant | `invitation.created` | `invitation` / nouvelle invitation | rôle, `member`, `pending` |
| Invitation expirée remplacée à la création | tenant | `invitation.revoked`, puis `invitation.created` | ancienne, puis nouvelle invitation | `{}`, puis métadonnées de création |
| Invitation membre renvoyée | tenant | `invitation.revoked`, puis `invitation.resend_requested` | ancienne, puis nouvelle invitation | `{}`, puis `delivery_attempt_id` |
| Livraison membre finalisée | tenant | `invitation.delivery_completed` | invitation livrée | statut, type de livraison, tentative |
| Invitation membre révoquée explicitement | tenant | `invitation.revoked` | invitation | `{}` |
| Organisation provisionnée | platform | `organization.provisioned`, puis `organization.initial_invitation.created` | organisation, puis invitation | `{}`, puis rôle Admin, type initial, `pending` |
| Invitation initiale renvoyée | platform | `organization.initial_invitation.revoked`, puis `organization.initial_invitation.resend_requested` | ancienne, puis nouvelle invitation | `{}`, puis `delivery_attempt_id` |
| Livraison initiale finalisée | platform | `organization.initial_invitation.delivery_completed` | invitation initiale | statut, type de livraison, tentative |
| Invitation initiale révoquée explicitement | platform | `organization.initial_invitation.revoked` | invitation initiale | `{}` |
| Invitation membre acceptée | tenant | `invitation.accepted` | invitation | `{}` |
| Invitation initiale acceptée | tenant | `invitation.accepted`, puis `organization.activated` | invitation, puis organisation | `{}`, `{}` |
| Préférence d’organisation modifiée | tenant, nouvelle organisation | `account.organization_preference_changed` | `user` / acteur | appartenances précédente et nouvelle |

Tous les événements d’une commande partagent `request_id`, `correlation_id`, acteur et source. Chaque événement reçoit
son propre UUID. La source est `api` et `actor_kind` vaut `user` pour toutes les transitions de 2.4.2.

L’ordre de la table est l’ordre d’appel au recorder. Les consommateurs regroupent les événements composites avec
`correlation_id` et ne déduisent pas une causalité générale de deux événements voisins dans le journal.

## 8. Règles par famille de mutation

### 8.1 Organisation

- `unchanged`, conflit de version, organisation absente ou inactive : zéro événement ;
- `changed_fields` contient seulement les champs dont la valeur persistée change réellement parmi `name`, `locale`
  et `timezone` ;
- aucune ancienne ou nouvelle valeur libre n’est auditée ;
- l’échec de l’audit annule l’incrément de version et toute modification.

### 8.2 Membres

- une commande modifiant rôle et statut produit deux événements, pas un événement générique ;
- une commande ne modifiant qu’un champ produit un seul événement ;
- `unchanged`, conflit, membre absent et protection du dernier Admin : zéro événement ;
- l’incrément de version utilisateur et les événements sont dans la même transaction ;
- la révocation des sessions Redis intervient après le commit et n’est pas auditée comme mutation métier ;
- un échec Redis ne supprime pas l’audit validé, conformément au comportement existant.

### 8.3 Invitations et courriel

Une création ou un renvoi utilise deux transactions métier distinctes autour du fournisseur SMTP :

1. création de l’invitation et de la tentative, événements `created` ou `resend_requested`, puis commit ;
2. envoi SMTP hors transaction ;
3. finalisation `sent` ou `failed`, événement `delivery_completed`, puis second commit.

L’audit ne contient jamais le destinataire, le lien, le jeton ou le message. Il ne marque jamais `sent` avant la
finalisation PostgreSQL.

Si le fournisseur échoue normalement, la finalisation `failed` et son événement sont validés. Si la finalisation
elle-même échoue, le cas d’utilisation conserve l’erreur de résultat inconnu : l’événement de demande reste présent,
mais aucun faux événement de livraison terminée n’est créé.

### 8.4 Acceptation d’invitation

L’acceptation par un nouveau compte commence sans acteur authentifié. Après validation du jeton et création du compte
dans la transaction, l’unité de travail pose comme contexte d’audit l’UUID du nouvel utilisateur, l’organisation
acceptée et le `request_id` serveur. La fonction append-only vérifie alors l’utilisateur et son appartenance active.

Pour un compte existant, l’acteur authentifié doit être celui auquel l’invitation correspond ; le contexte locataire
est posé seulement après que la fonction d’acceptation a retourné l’organisation validée.

Une acceptation initiale produit atomiquement l’appartenance, l’acceptation, l’activation et deux événements. Une
acceptation membre produit l’appartenance, l’acceptation et un événement. Jeton invalide, expiré, révoqué, déjà
accepté, compte incompatible ou contrainte d’unicité : zéro événement.

La sélection automatique de l’organisation acceptée ne produit pas en plus
`account.organization_preference_changed` : elle appartient à la transition d’acceptation déjà auditée. Cette action
est réservée au changement explicite d’organisation, ce qui évite d’inventer une appartenance précédente pour un
nouveau compte.

### 8.5 Changement d’organisation

- l’événement appartient à la nouvelle organisation active ;
- l’entité est l’utilisateur interne ;
- les métadonnées contiennent les UUID des appartenances précédente et nouvelle, jamais les noms d’organisation ;
- choisir l’appartenance déjà active est un no-op sans événement ni incrément de version ;
- la préférence PostgreSQL et l’audit sont atomiques ;
- la rotation de session Redis reste post-commit et technique ;
- si Redis échoue, l’audit décrit uniquement la préférence persistée, pas une rotation de session réussie.

## 9. Rejeux et idempotence

Les opérations déjà idempotentes conservent leurs UUID de commande :

- provisioning : `creation_request_id` ;
- création membre : `invitation_request_id` ;
- renvoi : `resend_request_id`.

Premier passage et transition réelle : événements prévus. Même UUID et même empreinte : réponse existante, aucun
nouvel événement. Même UUID et autre contenu : conflit, aucun événement.

La déduplication d’audit repose sur la décision transactionnelle du métier, pas sur une contrainte unique générique
dans `audit_events`, car une même commande peut légitimement produire plusieurs actions.

Les finalisations de livraison deviennent explicitement idempotentes. Le premier passage `pending -> sent|failed`
produit un événement. Un rejeu cohérent retourne `transitioned=false` sans événement ; un rejeu divergent est refusé.

## 10. Concurrence et verrouillage

- les verrous `FOR UPDATE` existants sont conservés ;
- les faits avant/après sont capturés sous le même verrou que la mutation ;
- aucun SELECT préalable hors transaction ne sert de source à l’audit ;
- deux mises à jour concurrentes : seule la gagnante produit des événements ;
- deux renvois concurrents : seule l’intention acceptée produit révocation et demande de renvoi ;
- une acceptation et une révocation concurrentes ne peuvent toutes deux produire un événement de succès ;
- l’écriture séquentielle de plusieurs événements reste dans la transaction unique.

## 11. Migration `20260809_0007`

La révision remplace les fonctions concernées afin qu’elles retournent les faits minimaux et une sémantique de
transition explicite. Elle ne modifie ni ne réécrit les événements 2.4.1.

Exigences :

- `down_revision = 20260809_0006` ;
- `CREATE OR REPLACE FUNCTION` lorsque la signature reste compatible ;
- nouvelle signature et révocation explicite de l’ancienne si nécessaire ;
- propriétaire `prospect_rls_definer`, `search_path` fixe et droit `PUBLIC` révoqué ;
- aucun droit de table supplémentaire pour `prospect_app` ;
- downgrade restaurant exactement les contrats précédant 2.4.2 ;
- downgrade refusé s’il rendrait ambiguë une opération en cours ou détruirait des données ;
- `alembic upgrade`, reconstruction depuis zéro et `alembic check` verts.

## 12. Gestion des erreurs

Une erreur de politique ou d’écriture d’audit est traduite en erreur de service contrôlée et provoque le rollback.
Les réponses n’exposent ni SQL, ni nom de contrainte, ni métadonnée, ni contenu PostgreSQL.

| Situation | Effet métier | Audit | Réponse existante |
| --- | --- | --- | --- |
| Validation/capacité refusée | aucun | aucun | `403` ou `422` |
| Ressource absente/inactive | aucun | aucun | `404` ou erreur contrôlée existante |
| Version ou idempotence en conflit | aucun | aucun | `409` |
| No-op ou rejeu cohérent | aucun nouveau changement | aucun nouvel événement | réponse actuelle |
| Audit invalide/indisponible avant commit | rollback | aucun | `503` contrôlé |
| Commit au résultat inconnu | état à réconcilier | jamais de rejeu automatique | erreur de résultat inconnu |
| Effet externe post-commit en échec | mutation conservée | événement de demande conservé | comportement existant |

Toutes les réponses d’administration et d’identité restent `Cache-Control: no-store` avec `X-Request-ID`.

## 13. Compatibilité API et interface

- aucune nouvelle route, propriété de requête ou propriété de réponse ;
- aucun changement de libellé, navigation, écran, formulaire ou permission visible ;
- les identifiants d’idempotence existants gardent leur format ;
- aucun UUID d’audit n’est exposé dans les réponses de mutation ;
- aucun événement, filtre ou curseur n’est stocké dans le navigateur ;
- les tests React existants doivent rester inchangés ou être adaptés uniquement à un changement de doubles de test,
  jamais à un changement visuel.

## 14. Observabilité technique

Les logs techniques peuvent signaler un échec d’enregistrement avec `request_id`, action prévue et type d’entité.
Ils ne consignent jamais `metadata`, destinataire, jeton ou corps de commande.

Métriques recommandées sans cardinalité d’identifiants :

- nombre d’événements écrits par code d’action ;
- nombre de rollbacks dus à l’audit ;
- nombre de rejeux sans nouvel événement ;
- durée de l’étape d’audit dans la transaction.

L’ajout d’un système de métriques persistant reste optionnel en 2.4.2 ; aucun nouveau fournisseur n’est requis.

## 15. Tests unitaires

Chaque cas d’utilisation prouve :

- l’action, la portée, l’entité, l’acteur, le `request_id` et les métadonnées exactes ;
- zéro événement sur refus, erreur, conflit, no-op et rejeu ;
- un ou deux événements selon la matrice ;
- l’ordre mutation, audit(s), commit, effet externe ;
- aucun commit si un recorder échoue ;
- aucun effet SMTP avant le premier commit ;
- session Redis révoquée ou tournée uniquement après commit ;
- acceptation nouveau compte avec contexte d’acteur établi après création ;
- absence de courriel, jeton, mot de passe, donnée Google ou texte libre.

Les fakes d’unité de travail exposent une chronologie d’appels afin que les tests ne se limitent pas à compter les
événements.

## 16. Tests PostgreSQL réels

La suite réelle couvre au minimum :

- chaque ligne de la matrice des événements ;
- mutation et événement visibles après commit ;
- mutation et événement absents après échec du recorder ;
- fonction métier réussie puis rollback volontaire ;
- une commande composite avec deux événements et un seul commit ;
- deux organisations et deux acteurs sans fuite ;
- acceptation nouveau compte et activation atomiques ;
- rôle et statut modifiés ensemble ;
- création remplaçant une invitation expirée ;
- renvoi et révocation concurrents ;
- finalisation cohérente rejouée sans doublon et finalisation divergente refusée ;
- idempotence du provisioning, de la création et du renvoi ;
- aucun événement sur conflit de version, dernier Admin, refus et no-op ;
- métadonnées strictement égales aux listes blanches ;
- `request_id` et `correlation_id` cohérents ;
- aucun privilège supplémentaire accordé au rôle Web.

Les tests tournent sous `prospect_app`; seules la préparation et les assertions globales utilisent le rôle de migration.

## 17. Tests de régression

- authentification, déconnexion et restauration de session ;
- provisioning, renvoi, révocation et acceptation ;
- modification d’organisation et de membre ;
- protection du dernier Administrateur ;
- changement d’organisation et résultat ambigu Redis ;
- historique courant des invitations ;
- recherche Google, carte, attribution et limites actuelles ;
- aucune nouvelle route d’export ou persistance navigateur ;
- réponses, statuts et enveloppes d’erreur inchangés ;
- zéro fournisseur Google ou SMTP réel dans les tests automatiques ordinaires.

## 18. Contrôles qualité

Obligatoires pendant l’implémentation :

- Ruff et Ruff format ;
- mypy strict ;
- pytest complet avec PostgreSQL, Redis et Mailpit réels, zéro `skip` dans le verrou ;
- reconstruction Alembic, `current` et `check` ;
- inspection des privilèges et fonctions réelles ;
- audit npm sans vulnérabilité haute ;
- ESLint, Vitest avec axe et build Vite ;
- contrôles d’absence de stockage navigateur et de secrets ;
- `git diff --check`.

## 19. Critères d’acceptation

2.4.2 est acceptable techniquement lorsque :

- toutes les transitions réelles produisent exactement la matrice prévue ;
- métier et audit partagent une transaction et un commit uniques ;
- un échec d’audit annule le métier ;
- refus, no-op et rejeux ne créent aucun événement ;
- les effets externes restent post-commit ;
- aucune donnée interdite n’apparaît en base, log ou réponse ;
- la compatibilité API et visuelle est préservée ;
- migration, infrastructure réelle et contrôles qualité sont verts.

La recette produit reste volontairement différée. La clôture fonctionnelle cumulée 2.4.1–2.4.3 aura lieu après la
livraison des interfaces de consultation.

## 20. Séquencement d’implémentation recommandé

1. ports d’unités de travail auditées et fakes chronologiques ;
2. adaptation SQL des résultats de transition sous `20260809_0007` ;
3. organisation et membres ;
4. changement d’organisation ;
5. invitations membre et livraison ;
6. provisioning et invitations initiales ;
7. acceptation nouveau compte et compte existant ;
8. tests PostgreSQL, régression et documentation.

Chaque sous-étape reste sans changement visuel et doit garder les tests précédents verts.

## 21. Critique experte préalable

### 21.1 Architecture

Risque : conserver les commits dans les gateways rendrait l’audit non atomique. Réponse : propriété de transaction
remontée dans les unités de travail applicatives et commit unique orchestré par le cas d’utilisation.

Risque résiduel : refactor transversal de plusieurs ports. Réponse : séparer lectures et mutations, adapter les tests
avant chaque famille et interdire toute modification de réponse HTTP.

### 21.2 Idempotence et effets externes

Risque : un rejeu ajoute un second audit ou annonce un courriel envoyé deux fois. Réponse : événement créé seulement
sur `transitioned=true`, deux transactions explicites autour de SMTP et finalisation idempotente.

Risque résiduel : crash après SMTP mais avant finalisation. Réponse : état `pending` réconciliable et absence de faux
succès ; une outbox durable reste hors 2.4.2.

### 21.3 Confidentialité

Risque : les fonctions retournent des faits contenant des données personnelles. Réponse : résultats minimaux codifiés,
adaptateurs typés et tests inspectant récursivement métadonnées, réponses et logs.

Risque résiduel : une future action peut élargir la politique. Réponse : registre fermé, revue obligatoire et test
négatif pour toute nouvelle clé.

## 22. Seize décisions validées

1. La recette manuelle de 2.4.1 et 2.4.2 est regroupée à la fin de 2.4.3, sans reporter les tests automatisés.
2. La transaction est pilotée par le cas d’utilisation au moyen d’une unité de travail auditée.
3. Mutation et `AuditRecorder` partagent exactement la même session PostgreSQL et un seul commit.
4. Les gateways de mutation n’ouvrent plus leur propre transaction et ne font plus de commit.
5. Les fonctions SQL retournent seulement des faits de transition codifiés, jamais de donnée personnelle ou libre.
6. Refus, conflit, no-op, rollback et rejeu idempotent ne créent aucun nouvel événement.
7. Une modification simultanée de rôle et statut produit deux événements corrélés.
8. Un remplacement ou renvoi audite la révocation de l’ancienne invitation puis la création ou demande de renvoi.
9. Provisionner produit deux événements plateforme : organisation et invitation initiale.
10. Accepter l’invitation initiale produit deux événements locataires : acceptation et activation.
11. Le changement d’organisation est audité dans la nouvelle organisation avec les deux appartenances internes.
12. SMTP sépare demande et finalisation en deux transactions auditées, sans faux statut `sent`.
13. Une finalisation rejouée à l’identique ne crée pas de doublon ; une finalisation divergente est refusée.
14. Redis et SMTP restent post-commit et leurs faits techniques ne sont pas ajoutés au journal métier.
15. Une nouvelle migration `20260809_0007` adapte les fonctions sans modifier les événements existants ni les droits Web.
16. Aucun changement API ou visuel ; tests PostgreSQL réels et verrou qualité restent obligatoires avant 2.4.3.

Ces seize décisions ont été validées par le responsable produit le 9 août 2026. Elles constituent le contrat normatif
de 2.4.2 ; toute dérogation doit être documentée et validée avant son implémentation.

## 23. Définition de « terminé »

2.4.2 est terminé lorsque :

- les seize décisions sont validées ou les dérogations documentées avant le code ;
- chaque mutation de la matrice est couverte ;
- aucune mutation réussie couverte ne peut exister sans son audit ;
- aucune tentative échouée ne prétend avoir réussi dans l’audit ;
- les replays et finalisations sont sans doublon ;
- l’acceptation anonyme établit son contexte d’audit sans faire confiance au navigateur ;
- la migration reconstruit une base vide et `alembic check` est vert ;
- les tests réels et les contrôles qualité passent sans `skip` ;
- le rapport d’implémentation documente les preuves et risques résiduels ;
- 2.4.3 peut consommer le journal sans migration corrective ni rétro-audit.

## 24. Références internes

- [`PHASE_2_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_4_1_RAPPORT_IMPLEMENTATION.md`](PHASE_2_4_1_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md)

## 25. Références techniques

- PostgreSQL — transactions : https://www.postgresql.org/docs/current/tutorial-transactions.html
- PostgreSQL — verrouillage explicite : https://www.postgresql.org/docs/current/explicit-locking.html
- PostgreSQL — sécurité des fonctions : https://www.postgresql.org/docs/current/sql-createfunction.html
- SQLAlchemy — gestion des transactions : https://docs.sqlalchemy.org/en/20/orm/session_transaction.html

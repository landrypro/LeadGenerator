# Phase 3.4-B — Cas d’utilisation et API des opportunités

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3.4 — Opportunités |
| Sous-lot | 3.4-B — Cas d’utilisation et API |
| Version | 1.0 |
| Prérequis | 3.4-A techniquement validé ; Alembic `20260910_0020 (head)` ; verrou local 3.4-A vert |
| Source de décision | Seize décisions de la section 17 de `PHASE_3_4_SPECIFICATIONS_DETAILLEES.md`, validées le 10 septembre 2026 |
| Statut | Implémentation backend techniquement validée ; verrou qualité local vert |
| Date | 10 septembre 2026 |

## 1. Objet et résultat attendu

Le sous-lot 3.4-B transforme le domaine et la persistance livrés en 3.4-A en contrats applicatifs et HTTP utilisables.
Il couvre la création, la modification, les transitions, les issues gagnée/perdue, la réouverture, les lectures de
portefeuille et l’historique. Chaque commande est locataire, autorisée, versionnée lorsque nécessaire, idempotente et
atomique avec son événement métier et son audit minimisé.

À la sortie, l’API fournit à 3.4-C toutes les données nécessaires aux écrans sans déplacer implicitement le prospect dans
le Kanban et sans mélanger des devises différentes.

## 2. Périmètre du sous-lot

### 2.1 Inclus

- cas d’utilisation de création, modification, transition et réouverture ;
- portefeuille, détail, historique et liste par prospect ;
- valeur pondérée calculée côté serveur et agrégats exacts par devise ;
- contrôle de responsabilité, capacités, organisation active et archivage du prospect ;
- concurrence optimiste, rejeu idempotent et transaction PostgreSQL unique ;
- erreurs publiques stables, réponses sans cache, métriques bornées et journaux structurés ;
- tests API, transactionnels, concurrents et multi-organisation sur PostgreSQL réel.

### 2.2 Hors périmètre

- composants React, navigation, formulaires et accessibilité, livrés en 3.4-C ;
- fusion des événements dans la chronologie commerciale 3.3, livrée en 3.4-C ;
- action d’alignement du Kanban : elle réemploiera l’API pipeline 3.2 dans 3.4-C et ne fait pas partie de la transaction
  d’opportunité ;
- conversion monétaire, suppression d’opportunité, import/export, automatisation, devis et facturation ;
- nouvelle migration : 3.4-B étend les ports, dépôts, cas d’utilisation et routes au-dessus de `20260910_0020`.

Si l’implémentation révèle une lacune de schéma, elle doit être documentée avant toute migration additionnelle ; le
sous-lot ne modifie pas silencieusement la révision 3.4-A déjà validée.

## 3. Principes applicatifs communs

### 3.1 Contexte de sécurité

Chaque cas d’utilisation reçoit un contexte résolu depuis la session serveur : `organization_id`, `actor_id`,
`membership_id`, rôle, capacités et langue effective. Aucun de ces attributs n’est accepté dans le corps client.

Les lectures et mutations vérifient successivement l’authentification, l’organisation active, la capacité puis la portée
de responsabilité. Une ressource absente ou appartenant à une autre organisation retourne le même `404` afin de ne pas
confirmer son existence.

### 3.2 Portée des rôles

| Opération | Administrateur | Gestionnaire | Commercial |
| --- | --- | --- | --- |
| Lister et lire | Toute l’organisation | Toute l’organisation | Opportunités dont il est responsable |
| Créer | Pour tout membre actif | Pour tout membre actif | Pour sa propre appartenance active |
| Modifier | Toutes les opportunités actives | Toutes les opportunités actives | Ses opportunités, si son appartenance est active |
| Changer d’étape ou clore | Oui | Oui | Oui sur ses opportunités, si son appartenance est active |
| Réaffecter | Oui, vers un membre actif | Oui, vers un membre actif | Non |
| Rouvrir | Oui | Oui | Non |

Une opportunité dont le responsable est désactivé reste lisible. La seule mutation alors permise est une réaffectation
isolée, effectuée par un Administrateur ou un Gestionnaire vers une appartenance active de la même organisation. Le corps
ne peut contenir aucun autre changement. Une fois la réaffectation confirmée, les règles normales s’appliquent.

### 3.3 Temps, décimaux et textes

- `expected_close_on` est une chaîne ISO `YYYY-MM-DD`, interprétée dans le fuseau IANA de l’organisation ;
- `amount` et `weighted_amount` sont toujours des chaînes décimales canoniques à quatre décimales ;
- aucun calcul métier ne passe par `float` ;
- `overdue` est vrai seulement si l’opportunité est ouverte et si `expected_close_on` précède le jour courant de
  l’organisation ;
- les textes sont normalisés, bornés et rendus comme texte ; aucun contenu Google n’est réhydraté ou prérempli.

## 4. Cas d’utilisation de commande

### 4.1 Création

`CreateOpportunity` reçoit un prospect, un brouillon et une clé d’idempotence. Il doit :

1. charger et verrouiller le prospect dans l’organisation active ;
2. refuser un prospect archivé ou placé dans une étape Kanban terminale ;
3. déterminer le responsable autorisé et vérifier son appartenance active ;
4. valider nom, montant, devise, probabilité et échéance selon le jour de l’organisation ;
5. créer l’opportunité en `discovery`, version `1`, sans issue ni `closed_at` ;
6. créer l’événement `created` et l’audit `opportunity.created` ;
7. valider le tout dans une transaction unique.

Le Commercial omet `owner_membership_id` ou fournit sa propre appartenance. Toute autre valeur est refusée. Administrateur
et Gestionnaire doivent fournir une appartenance active de l’organisation.

### 4.2 Modification

`UpdateOpportunity` exige la version lue et accepte uniquement : `name`, `amount`, `currency_code`, `probability`,
`expected_close_on` et `owner_membership_id`.

- les champs d’étape, d’issue, de clôture, de création et d’organisation ne sont jamais modifiables par cette commande ;
- un changement de devise exige que `amount` soit présent dans le même corps ; aucune conversion n’est effectuée ;
- une échéance déjà dépassée peut rester inchangée lors d’une autre correction, mais une échéance explicitement modifiée
  doit être le jour courant de l’organisation ou une date future ;
- une opportunité terminale est en lecture seule jusqu’à sa réouverture ;
- un corps vide ou ne produisant aucun changement est refusé et n’incrémente pas la version ;
- `changed_fields` contient uniquement les codes des champs réellement modifiés, jamais leurs valeurs.

### 4.3 Transition et issue

`TransitionOpportunity` reçoit `version`, `to_stage`, les éventuels `reason_code` et `reason_note`, puis une clé
d’idempotence.

| Situation | Règle |
| --- | --- |
| Étape ouverte vers étape ouverte | Avance ou recul d’un seul cran ; aucun motif accepté |
| `proposal` ou `negotiation` vers `won` | Probabilité forcée à `100`, `closed_at` fixé en UTC, aucun motif accepté |
| Toute étape ouverte vers `lost` | Probabilité forcée à `0`, motif de perte obligatoire, `closed_at` fixé en UTC |
| Depuis `won` ou `lost` | Refus par la route de transition ; utiliser la réouverture |

`other` exige une note normalisée de 1 à 500 caractères. Pour les sept autres motifs de perte, la note est facultative
dans la même limite. Une transition n’écrit ni le prospect ni son étape Kanban.

### 4.4 Réouverture

`ReopenOpportunity` est réservé à `opportunities:reopen`. Le serveur détermine la cible :

- `won` revient à `negotiation` ;
- `lost` revient à la dernière étape ouverte trouvée dans l’historique ;
- si cet historique ne permet pas de la déterminer, la cible est `discovery`.

La commande exige `version`, `reason_code`, `probability` et `idempotency_key`. `probability` redevient une valeur ouverte
explicite entre 0 et 100, car la clôture précédente avait imposé 0 ou 100 ; l’API ne reconstitue pas silencieusement une
ancienne valeur financière. Le détail expose la cible et la probabilité suggérée de cette cible pour aider 3.4-C.

Les motifs admis sont `entered_in_error`, `customer_reengaged`, `additional_information` et `other`. `other` exige une
note de 1 à 500 caractères. La réouverture remet `loss_reason_code`, `loss_reason_note` et `closed_at` à `NULL`, conserve
l’événement terminal historique, incrémente la version et ajoute `reopened`.

## 5. Contrats HTTP de mutation

| Méthode et route | Corps minimal | Réponse de succès |
| --- | --- | --- |
| `POST /api/prospects/{prospect_id}/opportunities` | champs métier + `idempotency_key` | `201`, détail version `1` |
| `PATCH /api/opportunities/{opportunity_id}` | `version`, au moins un champ modifiable, `idempotency_key` | `200`, détail mis à jour |
| `POST /api/opportunities/{opportunity_id}/stage-transitions` | `version`, `to_stage`, motifs éventuels, `idempotency_key` | `200`, détail et événement |
| `POST /api/opportunities/{opportunity_id}/reopen` | `version`, motif, probabilité, `idempotency_key` | `200`, détail et événement |

La clé d’idempotence est une chaîne opaque non vide de 1 à 128 caractères ; un UUID est recommandé aux clients. Le corps
est JSON strict : champs inconnus, valeurs `null` interdites pour les champs obligatoires et nombres JSON utilisés pour
`amount` sont refusés.

Exemple de création :

```json
{
  "name": "Renouvellement 2027",
  "amount": "12500.0000",
  "currency_code": "CAD",
  "probability": 25,
  "expected_close_on": "2026-12-15",
  "owner_membership_id": "b1b4c1bf-c7fa-4c2c-9485-d95b79cf1acf",
  "idempotency_key": "21bba8a8-659e-4e67-9703-3650e212dbd0"
}
```

Exemple de perte :

```json
{
  "version": 4,
  "to_stage": "lost",
  "reason_code": "no_budget",
  "reason_note": "Budget reporté au prochain exercice",
  "idempotency_key": "b31f400e-52e6-4467-92a3-828bd10f9e1e"
}
```

## 6. Rejeu, concurrence et atomicité

### 6.1 Empreinte de commande

L’empreinte SHA-256 est calculée côté serveur sur une forme canonique comprenant l’organisation, l’acteur, l’opération,
la ressource cible et le corps métier normalisé. Elle ne dépend ni de l’ordre des clés JSON ni de la représentation
localisée d’un montant ou d’une date.

Une clé est unique par organisation et type d’événement, conformément à 3.4-A :

- même clé et même empreinte : restitution du résultat déjà validé, sans nouvel événement, audit ni version ;
- même clé et empreinte différente : `409 opportunity_idempotency_conflict` ;
- deux premières exécutions concurrentes de la même commande : une transaction crée le résultat, l’autre le relit après
  la contrainte d’unicité et restitue ce même résultat.

Le rejeu d’une création conserve le statut `201` et la même représentation métier. Les autres rejeux conservent `200`.

### 6.2 Version optimiste

Toutes les mutations d’une opportunité existante exigent un entier `version > 0`. La mise à jour SQL porte la condition
`WHERE id = :id AND version = :expected_version` et incrémente la version une seule fois. Zéro ligne modifiée après une
lecture autorisée produit `409 opportunity_version_conflict` avec `fields.current_version` ; la réponse ne divulgue
aucune autre modification concurrente.

Deux commandes différentes partant de la même version produisent exactement un succès et un conflit. Une commande
idempotente déjà validée est reconnue avant le contrôle de version afin que son rejeu reste un succès stable.

### 6.3 Ordre des verrous et transaction

L’ordre est toujours prospect, opportunité, événement. L’opportunité, son événement métier et l’enregistrement d’audit
sont validés ensemble. Toute erreur d’écriture, y compris sur l’audit ou l’événement, annule l’ensemble. Aucun appel
réseau, calcul Google ou alignement Kanban n’est exécuté dans cette transaction.

## 7. Contrats de lecture

| Méthode et route | Résultat |
| --- | --- |
| `GET /api/prospects/{prospect_id}/opportunities` | opportunités visibles du prospect, triées et paginées |
| `GET /api/opportunities` | portefeuille filtré, page courante et agrégats par devise |
| `GET /api/opportunities/{opportunity_id}` | détail, actions autorisées et aide de transition/réouverture |
| `GET /api/opportunities/{opportunity_id}/events` | historique métier append-only, ordre antéchronologique |

Toutes les réponses utilisent `Cache-Control: no-store, max-age=0`. Elles ne contiennent aucun champ descriptif
provenant de Google.

### 7.1 Représentation détaillée

Le détail expose au minimum : identifiants internes, nom, montant, devise, probabilité, `weighted_amount`, étape,
échéance, `overdue`, responsable et état actif de son appartenance, issue, `closed_at`, version et horodatages UTC.

Il ajoute des aides calculées non persistées :

- `allowed_transitions`, filtré par le graphe et les capacités ;
- `allowed_actions` avec `update`, `close`, `reassign` et `reopen` ;
- `reopen_target_stage` et `suggested_reopen_probability` seulement pour une opportunité terminale lisible ;
- `owner_inactive` et `parent_archived`.

Ces aides ne remplacent jamais les contrôles lors de la mutation.

### 7.2 Portefeuille et filtres

`GET /api/opportunities` accepte les filtres suivants :

- `q` sur le nom interne de l’opportunité et l’alias CRM du prospect ;
- `stage` répétable parmi les six codes ;
- `owner_membership_id` ;
- `currency_code` ;
- `expected_close_from` et `expected_close_to` ;
- `overdue=true|false` ;
- `prospect_id` ;
- `limit` de 1 à 100, valeur initiale 25 ;
- `cursor` opaque.

Les prospects archivés sont exclus du portefeuille. Le tri fixe est `expected_close_on ASC`, `updated_at DESC`, puis
`id ASC`. Une autre organisation, un autre acteur visible ou tout changement de filtre invalide le curseur.

La liste par prospect réemploie le même format de page et le même tri, mais fixe le prospect dans la signature du
curseur. Un Commercial ne peut pas élargir sa portée par un filtre de responsable.

### 7.3 Pagination

Le curseur est signé et encode la dernière clé de tri, l’organisation, la portée de visibilité et l’empreinte des filtres.
Il n’est pas un numéro de page. Une valeur malformée, expirée ou réutilisée avec d’autres filtres retourne
`422 opportunity_cursor_invalid`. La réponse contient `items`, `next_cursor` ou `null`, et `has_more`.

L’historique est trié par `occurred_at DESC, id DESC`, avec une limite initiale de 25 et maximale de 100. Il expose le
type d’événement, les étapes, les versions, les codes de champs modifiés, le motif métier autorisé, l’acteur interne et
l’horodatage. Il ne reconstruit pas d’anciens montants ou noms absents des événements.

## 8. Agrégats par devise et valeur pondérée

Les agrégats sont calculés sur l’ensemble visible après application des filtres, mais avant pagination. Chaque entrée de
`aggregates_by_currency` contient :

- `currency_code` ;
- `count` et `amount_total` ;
- `weighted_amount_total` ;
- `open_count`, `won_count` et `lost_count` ;
- `overdue_open_count`.

Les sommes utilisent `NUMERIC`, sont arrondies et sérialisées à quatre décimales. Aucune entrée synthétique n’est créée
pour une devise absente et aucun total global multidevise n’est fourni. Les agrégats respectent exactement la portée du
Commercial et restent indépendants du nombre d’éléments de la page.

La formule unitaire est `amount × probability / 100`. Les opportunités gagnées contribuent avec une probabilité de 100,
les perdues avec 0, et les ouvertes avec leur probabilité courante.

## 9. Événements métier et audit minimisé

| Commande | Événement | Audit |
| --- | --- | --- |
| Création | `created` | `opportunity.created` |
| Modification, y compris réaffectation | `updated` | `opportunity.updated` |
| Transition ouverte ou issue | `stage_changed` | `opportunity.stage_changed` |
| Réouverture | `reopened` | `opportunity.reopened` |

`changed_fields` est un objet JSON fermé de la forme `{"amount":"changed","probability":"changed"}`. Les seules
valeurs admises sont des marqueurs techniques bornés ; aucune ancienne ou nouvelle valeur métier n’y figure.

L’audit contient au plus : `organization_id`, identifiants internes de prospect et d’opportunité, opération, codes
d’étape, code de devise, code de motif, version initiale/résultante et codes de champs modifiés. Il exclut nom, montant,
note de motif, alias du prospect, identités affichées, coordonnées et contenus Google.

## 10. Erreurs publiques stables

Les erreurs suivent l’enveloppe existante `error.code`, `error.message`, `error.request_id` et `error.fields`.

| HTTP | Code | Situation |
| ---: | --- | --- |
| 400 | `csrf_failed` | origine ou jeton CSRF refusé |
| 401 | `authentication_required` | session absente ou expirée |
| 403 | `opportunity_action_forbidden` | capacité ou responsabilité insuffisante |
| 404 | `prospect_not_found` | prospect absent ou invisible lors de la création |
| 404 | `opportunity_not_found` | opportunité absente ou invisible |
| 409 | `opportunity_version_conflict` | version obsolète |
| 409 | `opportunity_idempotency_conflict` | clé déjà utilisée pour une autre commande |
| 409 | `opportunity_owner_inactive` | mutation bloquée jusqu’à une réaffectation autorisée |
| 409 | `opportunity_parent_archived` | prospect archivé, mutation interdite |
| 422 | `opportunity_command_invalid` | champs, décimal, devise, date, responsable ou motif invalides |
| 422 | `opportunity_transition_invalid` | graphe, terminalité ou forme de l’issue non respectés |
| 422 | `opportunity_cursor_invalid` | curseur illisible ou incompatible avec la requête |
| 503 | `opportunity_service_unavailable` | dépendance du module indisponible |

Les erreurs de validation placent uniquement des codes de champs publics dans `fields`. Les erreurs SQL, empreintes,
politiques RLS et détails d’une ressource invisible ne sont jamais renvoyés.

## 11. Observabilité

Les journaux JSON contiennent `request_id`, opération, résultat, code d’étape, code d’erreur et durée. Ils n’incluent ni
corps JSON, ni valeur financière, ni texte libre, ni identifiant Google.

Métriques bornées :

- `opportunity_command_total{operation,result}` ;
- `opportunity_transition_total{from_stage,to_stage,result}` ;
- `opportunity_conflict_total{operation}` ;
- `opportunity_portfolio_request_total{result}` ;
- histogrammes de durée des commandes et lectures.

Organisation, utilisateur, responsable, prospect, opportunité, devise et `request_id` sont interdits comme étiquettes de
métrique.

## 12. Sécurité HTTP et conservation

- session par cookie serveur ; aucune organisation issue d’un paramètre client ;
- origine approuvée, CSRF valide et `application/json` obligatoires pour toute mutation ;
- RLS forcée et clés composites comme dernier rempart d’isolation ;
- aucun contenu 3.4 dans `localStorage`, `sessionStorage`, IndexedDB ou Cache API ;
- aucun endpoint `DELETE` et aucun effacement physique ;
- le détail et l’historique d’un prospect archivé restent consultables selon les droits, mais toutes les mutations sont
  bloquées et le portefeuille actif les exclut ;
- les notes de motif suivent la conservation du prospect et ne sont jamais copiées dans l’audit ou les journaux.

## 13. Travaux techniques attendus

L’implémentation 3.4-B, lorsqu’elle sera autorisée, devra :

1. étendre les ports d’opportunité pour les verrous, recherches, curseurs, agrégats et historique ;
2. compléter les dépôts PostgreSQL avec conditions de version, tri stable et agrégations `NUMERIC` ;
3. ajouter les cas d’utilisation et leurs exceptions applicatives fermées ;
4. brancher l’unité de travail, l’audit, les métriques et les dépendances dans le conteneur ;
5. ajouter les schémas Pydantic stricts, le routeur et la traduction contrôlée des erreurs ;
6. ne créer ni écran React ni migration de schéma non approuvée.

## 14. Plan de tests obligatoire

### 14.1 Tests de cas d’utilisation

- création valide et plusieurs opportunités de même nom ;
- chaque champ invalide, montant exact à quatre décimales et devise non prise en charge ;
- changement de devise sans montant, échéance modifiée dans le passé et corps sans changement ;
- graphe complet des transitions autorisées et refusées ;
- perte avec les huit motifs, note obligatoire pour `other`, gain et probabilités terminales ;
- réouverture gagnée/perdue, cible historique ou de repli, probabilité explicite et droit interdit au Commercial ;
- responsable désactivé, réaffectation isolée et refus d’une réaffectation inter-organisation.

### 14.2 Tests API

- schémas stricts, décimaux en chaînes, statuts HTTP, erreurs et `request_id` ;
- `401`, `403`, `404` non-divulgateur, CSRF, origine et type de contenu ;
- liste par prospect, détail, portefeuille, filtres combinés et curseurs altérés ;
- actions autorisées calculées selon rôle, propriétaire, terminalité et archivage ;
- `Cache-Control: no-store, max-age=0` sur toutes les routes ;
- absence de champ Google et absence de valeur sensible dans l’audit ou les journaux capturés.

### 14.3 Tests transactionnels et concurrents

- opportunité, événement et audit validés ou annulés ensemble ;
- panne forcée de l’événement puis de l’audit sans écriture partielle ;
- rejeu identique sans nouvelle version, événement ni audit ;
- même clé et autre empreinte en `409` ;
- deux mises à jour ou transitions sur la même version : exactement un succès et un `409` ;
- deux créations concurrentes portant la même clé : une seule opportunité et un seul événement.

### 14.4 Tests PostgreSQL réel et multi-organisation

- RLS en lecture et écriture pour opportunités et événements ;
- identifiants d’un autre locataire retournant `404` sans effet ;
- Commercial limité à ses propres opportunités, même avec des filtres forgés ;
- agrégats isolés, exacts par devise et indépendants de la pagination ;
- fuseaux horaires distincts produisant l’indicateur de retard attendu ;
- contraintes SQL toujours effectives via le rôle applicatif.

## 15. Critères de sortie de 3.4-B

Le sous-lot est techniquement livrable seulement si :

1. toutes les routes et cas d’utilisation de ce document sont branchés ;
2. création, modification, transitions, issues et réouverture sont atomiques et idempotentes ;
3. portefeuille, détail, historique et agrégats respectent responsabilité, RLS, pagination et exactitude décimale ;
4. les tests ciblés, transactionnels, concurrents et multi-organisation sont verts sur PostgreSQL réel, sans skip ;
5. Ruff, format Ruff, mypy et les tests backend ciblés sont verts ;
6. Alembic reste à `20260910_0020 (head)` et `alembic check` ne détecte aucun écart ;
7. un rapport d’implémentation 3.4-B consigne commandes, résultats et éventuelles réserves.

Le verrou global, les écrans et la recette fonctionnelle complète restent dus respectivement en 3.4-D et 3.4-C/3.4-D.

## 16. Décision et état d’implémentation

Le GO explicite du responsable produit du 10 septembre 2026 a autorisé l’implémentation de **3.4-B — Cas d’utilisation
et API**. Les cas d’utilisation, les routes HTTP, les erreurs stables, l’audit minimisé, les métriques, les agrégats et
la pagination signée ont été ajoutés sans nouvelle migration.

Le verrou qualité local est vert : il a validé les migrations, les contrôles PostgreSQL réel, les tests backend et les
contrôles frontend. Le détail des preuves est consigné dans
[`PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_B_RAPPORT_IMPLEMENTATION.md).

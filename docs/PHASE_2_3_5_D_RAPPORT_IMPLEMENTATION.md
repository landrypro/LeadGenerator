# Phase 2.3.5-D — Rapport d’implémentation de l’administration plateforme

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-D — Plateforme |
| Date | 3 août 2026 |
| Statut | Implémenté et validé localement par le responsable produit |
| Migration SQL | Aucune |
| Nouvelle API | Aucune |
| Révision Alembic | `20260802_0005 (head)` inchangée |

## 1. Résultat livré

La route `/app/platform/organizations` est désormais active avec `platform:organizations:read`. Un Administrateur
plateforme sans organisation active y est dirigé à la connexion. Lorsqu’un contexte locataire explicite existe, les
destinations Recherche puis Organisation conservent leur priorité.

La page permet de :

- lister les vues de provisioning par pages de 25, dans l’ordre serveur et sans inventer de total ;
- dédupliquer les pages par `organization.id` ;
- créer une organisation et son Administrateur initial avec une intention idempotente en mémoire ;
- renvoyer la première invitation active, expirée ou révoquée d’une organisation en provisioning ;
- révoquer, après confirmation, une première invitation active ou expirée ;
- réconcilier chaque ligne exclusivement avec la réponse serveur.

La page ne propose ni impersonation, ni entrée dans une organisation, ni suspension. Elle ne charge aucune donnée
CRM, membre ou Google. Les utilisateurs qui possèdent seulement `platform:organizations:read` consultent la liste sans
formulaire ni action.

## 2. Fiabilité des intentions

La création conserve le couple `{creation_request_id, corps normalisé}` après erreur réseau, indisponibilité ou
`provisioning_outcome_unknown`. Une édition crée une nouvelle intention. Un `idempotency_key_reused` bloque l’action
jusqu’à l’abandon explicite de l’intention ; aucun rejeu automatique n’est effectué.

Chaque organisation possède de la même manière son propre `resend_request_id`. Deux lignes restent indépendantes,
mais une double action sur la même ligne est neutralisée synchroniquement. Les champs de création sont verrouillés
pendant l’appel afin que le corps visible ne diverge pas de l’intention envoyée. Les contrôleurs sont annulés au
démontage et les réponses tardives sont ignorées.

Les intentions, listes et curseurs restent uniquement dans l’état React. Aucun UUID idempotent, jeton d’invitation ou
corps métier n’est placé dans `localStorage`, `sessionStorage`, l’URL ou les journaux du navigateur.

## 3. Contrats et erreurs

Le client réutilise strictement les quatre endpoints existants :

- `GET /api/platform/organizations?limit=25&cursor=...` ;
- `POST /api/platform/organizations` ;
- `POST /api/platform/organizations/{id}/first-invitation/resend` ;
- `POST /api/platform/organizations/{id}/first-invitation/revoke` avec `{}`.

Les mutations passent par le client HTTP commun avec cookie same-origin et CSRF. Le délai `Retry-After` d’un `429`
est affiché. Un échec de livraison est distingué d’un échec de création : la ressource créée reste visible et le
renvoi est proposé lorsque son état l’autorise.

## 4. Tests et contrôles exécutés

- Vitest complet : **102 réussis**, 24 fichiers ;
- tests ciblés D : **35 réussis**, 8 fichiers ;
- ESLint : vert, zéro avertissement ;
- build Vite : vert, 69 modules transformés ;
- Ruff lint : vert ;
- Ruff format : 142 fichiers conformes ;
- mypy : 110 fichiers conformes ;
- pytest : **133 réussis, 17 ignorés** faute d’activation de l’infrastructure réelle.
- Alembic : `20260802_0005 (head)` et `check` sans nouvelle opération.

La première exécution Vitest lancée en parallèle d’autres contrôles a dépassé le délai de deux anciens tests
Organisation. Ces deux tests ont réussi isolément (5/5), puis la suite complète seule a réussi (102/102). Il s’agissait
d’une contention locale, pas d’une régression.

Les 17 tests PostgreSQL/Redis/Mailpit devront encore être exécutés avec `REQUIRE_INFRASTRUCTURE_TESTS=true` pendant le
verrou 2.3.5-E. Aucun changement backend ou de modèle ne nécessitait une nouvelle migration dans D.

## 5. Trois critiques expertes

### Critique 1 — Sécurité et séparation

La capacité frontend améliore l’ergonomie mais n’est pas une autorité. Les endpoints continuent d’exiger session,
CSRF et capacité plateforme côté serveur. La vue ne reçoit que les métadonnées de provisioning et n’offre aucun
passage vers un locataire. Aucun défaut bloquant constaté.

### Critique 2 — Systèmes distribués et idempotence

Le principal risque était de générer un nouvel UUID après un résultat ambigu. Le couple UUID/corps est désormais
stable et les conflits sont terminaux jusqu’à une décision humaine. Les verrous synchrones ferment aussi la fenêtre
entre deux clics avant le rendu React. Aucun défaut bloquant constaté.

### Critique 3 — UX et exploitation

La liste n’annonce pas de total absent du contrat, les actions restent locales à une ligne et le statut de livraison
n’est pas confondu avec celui de l’organisation. La mise en page descend à une colonne sur petit écran. Le parcours
local a été déclaré conforme par le responsable produit. Aucun défaut de code bloquant.

## 6. Deux revues de code

### Revue A — Architecture frontend

La séparation Page / hook / client API / formulaire / liste maintient les responsabilités bornées. Le hook paginé
existant est réutilisé et la clé de déduplication est stable hors rendu, évitant une boucle de rechargement. Les
réponses serveur remplacent les vues au lieu d’être reconstruites localement. Avis : cohérent avec l’architecture
fonctionnelle existante.

### Revue B — Sécurité, concurrence et résilience

Les corps sont JSON stricts, les identifiants de chemin sont encodés et React échappe les valeurs affichées. Les
contrôleurs, références de verrou et vérifications de montage empêchent les réponses tardives et doubles mutations.
La confirmation de révocation réutilise le dialogue accessible déjà éprouvé. Avis : prêt pour validation locale ;
la fermeture des 17 tests réels appartient au lot E.

## 7. Validation locale demandée

1. Démarrer PostgreSQL, Redis et Mailpit, appliquer Alembic `head`, puis démarrer backend et frontend.
2. Vérifier `http://127.0.0.1:8000/api/health/ready` : PostgreSQL et Redis doivent être `ok`.
3. Se connecter avec l’Administrateur plateforme puis ouvrir `http://localhost:5173/app/platform/organizations`.
4. Créer une organisation avec un courriel inédit et vérifier le courriel dans `http://127.0.0.1:8025`.
5. Vérifier renvoi, invalidation de l’ancien lien, révocation et refus du lien révoqué.
6. Accepter une invitation, actualiser la liste et confirmer l’état organisation `active` / invitation `accepted`,
   sans action résiduelle.
7. Confirmer l’absence de Recherche, Organisation et Membres pour un compte plateforme sans appartenance.
8. Tester clavier, fenêtre de 320 px, zoom 200 %, URL et stockages navigateur.

Le responsable produit a confirmé le 3 août 2026 que le parcours local de 2.3.5-D est entièrement conforme. Le lot D
est donc clôturé. Les 17 tests d’infrastructure obligatoires et le verrou qualité transversal restent à traiter dans
2.3.5-E avant d’autoriser 2.4 ou un déploiement.

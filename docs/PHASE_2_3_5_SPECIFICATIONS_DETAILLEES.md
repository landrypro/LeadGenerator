# Phase 2.3.5 — Spécifications détaillées de l’interface d’administration et du verrou qualité

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Incrément | 2.3.5 — Interface d’administration et verrou qualité |
| Version | 1.9 |
| Date | 3 août 2026 |
| Statut | 2.3.5-A/B/C/D validés ; E implémenté, verrou final en attente des preuves Docker/Azure/manuelles |
| Validation produit | 2 août 2026 — seize décisions ; 3 août 2026 — A/B/C/D acceptés et décisions D/E validées |
| Prérequis | 2.3.4 implémenté et validé localement par le responsable produit |
| Migration SQL | Aucune nouvelle révision prévue |
| Marché initial | Canada |

## 1. Objectif

2.3.5 rend utilisables dans l’application les capacités et les API livrées par 2.3.2 et 2.3.3. L’incrément ajoute
la navigation authentifiée, le sélecteur d’organisation, les écrans d’administration locataire et plateforme, ainsi
qu’un verrou qualité final avant 2.4.

L’interface ne devient jamais l’autorité de sécurité. La session, l’organisation active, les capacités, les versions,
les règles du dernier Administrateur, l’idempotence, RLS et les fonctions SQL existantes restent les seules autorités.

2.3.5 doit également solder la réserve de validation de 2.3.4 : les tests PostgreSQL, Redis et Mailpit devront être
exécutés sans `skip` avant d’autoriser 2.4 ou un déploiement.

## 2. Résultat attendu

À la fin de l’incrément :

- un utilisateur authentifié dispose d’un shell CRM cohérent et accessible ;
- les routes visibles dépendent de ses capacités ;
- un membre présent dans plusieurs organisations peut changer de contexte sans ambiguïté ;
- un Administrateur gère l’organisation, les membres et les invitations depuis l’interface ;
- un Gestionnaire consulte l’organisation et les membres sans action privilégiée ;
- un Commercial accède à la recherche et à son compte sans voir l’annuaire des membres ;
- un Administrateur plateforme gère le provisioning sans obtenir d’accès locataire implicite ;
- les erreurs de version, de dernier Administrateur, d’idempotence et de livraison sont compréhensibles ;
- les résultats Google, sessions, CSRF et identifiants idempotents restent hors des stockages Web ;
- toutes les suites unitaires, d’intégration réelle, frontend et de build sont vertes sans test d’infrastructure ignoré.

## 3. Invariants hérités non négociables

Les règles suivantes restent inchangées :

1. l’organisation active provient de la session serveur ;
2. une commande locataire ne contient jamais `organization_id` ;
3. les capacités sont recalculées côté serveur à chaque requête sensible ;
4. l’Administrateur plateforme n’est pas implicitement membre d’une organisation ;
5. le dernier Administrateur actif est protégé transactionnellement ;
6. les mutations utilisent origine fiable, cookie `HttpOnly`, CSRF et JSON strict ;
7. les sessions sont renouvelées ou invalidées selon les règles 2.3.3 ;
8. les UUID d’idempotence ne sont pas des autorisations et ne sont jamais persistés dans le navigateur ;
9. la recherche Google conserve un Text Search, vingt résultats, aucun contact et aucune pagination ;
10. la carte reste protégée par une concession liée et terminale ;
11. les réponses d’identité, d’administration et Google restent `no-store` ;
12. RLS et le rôle PostgreSQL applicatif restent actifs.

## 4. Périmètre

### 4.1 Inclus

- shell authentifié commun ;
- navigation par capacité ;
- routes canoniques et page introuvable contrôlée ;
- sélecteur d’organisation ;
- page Compte en lecture seule ;
- page Plateforme — Organisations ;
- page Administration — Organisation ;
- page Administration — Membres et invitations ;
- formulaires, confirmations, pagination par curseur, états vides et erreurs ;
- clients API et hooks dédiés ;
- adaptation de `AuthProvider` au changement d’organisation et à l’invalidation immédiate ;
- tests React, API, intégration réelle et accessibilité ;
- documentation utilisateur, technique et d’exploitation ;
- validation locale finale de la phase 2.3.

### 4.2 Explicitement exclu

- modification du profil, du courriel ou du mot de passe ;
- inscription publique ;
- suppression physique d’un membre ou d’une organisation ;
- suspension/réactivation plateforme, réservée à 2.4 avec audit ;
- historique complet des invitations et journal d’audit, réservés à 2.4 ;
- quotas Google et adaptateurs Redis partagés, réservés à 2.6 ;
- prospects, pipeline, activités, opportunités et conformité ;
- import/export ;
- modification des limites ou champs Google ;
- nouvelle migration ou nouvelle route backend, sauf écart bloquant démontré et validé ;
- refonte graphique complète du moteur de recherche ;
- déploiement ou configuration d’un fournisseur SMTP de production.

## 5. Acteurs et matrice d’interface

| Fonction | Plateforme sans organisation | Admin | Manager | Sales |
| --- | --- | --- | --- | --- |
| Organisations plateforme | lecture/création/actions | si rôle plateforme | si rôle plateforme | si rôle plateforme |
| Recherche Google | non | oui | oui | oui |
| Compte | oui | oui | oui | oui |
| Organisation | non | lecture/modification | lecture | lecture |
| Membres | non | lecture/modification | lecture | absent |
| Invitations de membres | non | lecture/création/renvoi/révocation | absent | absent |
| Changement d’organisation | selon appartenances actives | oui | oui | oui |

Une action absente visuellement ne remplace jamais un contrôle serveur. Une URL directe sans capacité retourne un
écran `403` contrôlé et ne déclenche aucun chargement de données protégées.

## 6. Architecture de navigation

### 6.1 Routes canoniques

| Route | Condition | Contenu |
| --- | --- | --- |
| `/login` | session absente | connexion |
| `/accept-invitation` | publique bornée | parcours d’invitation existant |
| `/app/search` | `google:search` | recherche Google existante |
| `/app/account` | session valide | identité et appartenances en lecture seule |
| `/app/admin/organization` | `organization:read` | métadonnées de l’organisation active |
| `/app/admin/users` | `members:read` | membres ; invitations seulement si autorisées |
| `/app/platform/organizations` | `platform:organizations:read` | provisioning plateforme |

`/` choisit une destination déterministe :

1. `/app/search` si une organisation est active et `google:search` est présente ;
2. `/app/admin/organization` si une organisation est active et seule `organization:read` est disponible ;
3. `/app/platform/organizations` si la capacité plateforme est présente ;
4. état « aucune organisation accessible » dans les autres cas authentifiés ;
5. `/login` sans session.

Un utilisateur authentifié visitant `/login` est redirigé selon la même règle. Une route inconnue affiche une page
`404` accessible ; elle ne retombe plus silencieusement sur la recherche. Les routes des futurs modules ne sont pas
affichées dans la navigation tant que leur incrément n’est pas livré.

### 6.2 Historique et liens profonds

- `navigate()` conserve `pushState` pour une action de navigation et utilise `replaceState` pour une redirection ;
- retour/avance du navigateur restaure la route ;
- un rechargement direct d’une route `/app/...` est pris en charge par le fallback SPA existant ;
- aucun cookie, CSRF, curseur, UUID d’idempotence ou jeton n’est placé dans l’URL ;
- le fragment d’invitation continue d’être retiré avant React.

## 7. Shell authentifié

`AuthenticatedLayout` fournit :

- marque Prospect CRM ;
- navigation principale filtrée par capacité ;
- organisation active et sélecteur éventuel ;
- nom affiché, accès Compte et déconnexion ;
- zone principale avec titre de page et fil d’Ariane court ;
- navigation mobile sous forme de panneau contrôlé au clavier.

Le shell est monté seulement après restauration complète de la session, afin d’éviter tout clignotement d’action
privilégiée. L’écran Recherche conserve ses formulaires, cartes, résultats, attribution et comportement responsive ;
seule son intégration dans le shell commun est adaptée.

## 8. Sélecteur d’organisation

### 8.1 Visibilité

- caché avec zéro ou une appartenance active ;
- visible avec au moins deux appartenances actives ;
- affiche le nom actif et la liste des autres organisations ;
- utilise `membership_id`, jamais `organization_id`, dans la commande.

### 8.2 Changement atomique

`AuthProvider.switchOrganization(membershipId)` :

1. empêche une seconde commutation simultanée ;
2. appelle `POST /api/auth/switch-organization` une seule fois ;
3. conserve la session courante tant que la réponse n’est pas réussie ;
4. installe atomiquement la nouvelle réponse d’authentification, le nouveau CSRF et le nouveau cookie ;
5. démonte les sous-arbres locataires indexés par l’identifiant de l’organisation ;
6. annule les requêtes en vol et efface résultats Google, concessions, formulaires, pages et curseurs ;
7. recalcule immédiatement navigation et capacités ;
8. choisit une route autorisée dans la nouvelle organisation.

Une erreur conserve l’ancien contexte et affiche un message contrôlé. Aucun retry automatique n’est permis. Une
réponse arrivée tardivement de l’ancienne organisation est ignorée grâce à l’annulation et à un identifiant de requête
local.

## 9. Page Compte

La page `/app/account` affiche uniquement les données déjà présentes dans la session :

- nom affiché et courriel ;
- rôle plateforme éventuel ;
- organisation active ;
- liste des appartenances actives et rôles ;
- accès au changement d’organisation lorsqu’il est disponible ;
- bouton de déconnexion.

Aucun formulaire de modification n’est simulé. Le CSRF, la version utilisateur, le cookie et les identifiants
techniques non nécessaires ne sont jamais affichés.

## 10. Page Plateforme — Organisations

### 10.1 Accès et liste

La page `/app/platform/organizations` exige `platform:organizations:read`. Elle affiche une table paginée par curseur :

- nom, langue, fuseau, état, date de création et activation éventuelle ;
- destinataire, état, expiration et état de livraison de la première invitation ;
- aucune appartenance, donnée Google ou donnée CRM ;
- bouton « Charger la suite » seulement si `next_cursor` est présent ;
- aucun total inventé.

La pagination ajoute les éléments en les dédupliquant par identifiant. Un changement de session ou une navigation
annule la requête. Les curseurs restent en mémoire.

### 10.2 Création

Le formulaire de création est visible avec `platform:organizations:create` et contient :

- nom ;
- langue `fr-CA` ou `en-CA` ;
- fuseau IANA ;
- courriel du premier Administrateur.

Le fuseau proposé par défaut vient de `Intl.DateTimeFormat().resolvedOptions().timeZone` s’il est valide, sinon
`America/Toronto`. La valeur reste modifiable et le serveur effectue la validation finale.

Le navigateur génère `creation_request_id` avec `crypto.randomUUID()` pour une intention de soumission. Il conserve le
même UUID et le même corps après une erreur réseau ou `provisioning_outcome_unknown`. Toute modification sémantique du
formulaire crée une nouvelle intention et un nouvel UUID. Après succès, le formulaire est réinitialisé et la ressource
retournée est insérée ou remplacée dans la liste.

### 10.3 Première invitation

Pour une organisation en `provisioning` :

- « Renvoyer » génère un `resend_request_id` par intention et respecte les mêmes règles de retry ambigu ;
- « Révoquer » demande une confirmation accessible et envoie `{}` en JSON ;
- les actions disparaissent après activation ;
- un état `accepted` interdit toute action ;
- l’état `revoked` ne propose pas une seconde révocation, mais permet un renvoi si le serveur l’autorise ;
- `429` affiche le délai avant nouvelle tentative sans compte à rebours facturable ;
- `503 *_outcome_unknown` propose uniquement de répéter la même intention.

## 11. Page Administration — Organisation

### 11.1 Lecture

Tous les rôles locataires possédant `organization:read` voient :

- nom ;
- langue ;
- fuseau ;
- état ;
- dates de création et mise à jour ;
- version présentée seulement dans le diagnostic d’un conflit, pas comme donnée métier principale.

Les dates sont rendues avec `Intl.DateTimeFormat`, selon la langue et le fuseau de l’organisation, tout en conservant
un élément `<time datetime="...">`.

### 11.2 Modification

Avec `organization:update`, le formulaire permet de changer nom, langue et fuseau. Il :

- envoie uniquement les champs modifiés avec la `version` lue ;
- reste désactivé sans changement ;
- neutralise la double soumission ;
- remplace la vue par la réponse réussie ;
- sur `organization_version_conflict`, conserve la saisie, annonce le conflit et propose « Recharger la version
  actuelle » ;
- n’écrase jamais automatiquement une version plus récente ;
- n’autorise ni changement d’état ni suppression.

Manager et Sales voient une fiche strictement en lecture seule, sans bouton désactivé laissant croire à une future
autorisation.

## 12. Page Administration — Membres et invitations

### 12.1 Membres

La page exige `members:read`. La liste paginée affiche :

- nom affiché ;
- courriel ;
- rôle ;
- état actif/désactivé ;
- date d’arrivée et date de modification ;
- aucune information de compte globale ou d’une autre organisation.

Manager lit la liste sans action. Admin avec `members:manage` peut ouvrir une édition ciblée :

- rôle `admin`, `manager` ou `sales` ;
- état `active` ou `disabled` ;
- `version` obligatoire et invisible dans le formulaire ;
- confirmation explicite avant désactivation ou retrait du rôle Admin ;
- aucune suppression physique.

Une commande sans changement est désactivée. `membership_version_conflict` recharge la ligne après confirmation sans
rejouer la mutation. `last_active_administrator` garde la ligne intacte et explique qu’un second Administrateur actif
est requis. Les identifiants croisés restent présentés comme ressource introuvable.

Si l’utilisateur modifie sa propre appartenance, la réponse réussie entraîne immédiatement la purge de l’état React et
un retour à la connexion, car le backend expire le cookie courant. L’interface n’attend pas une requête suivante pour
constater la perte de session.

### 12.2 Invitations

L’onglet Invitations n’existe que si `invitations:read` est présente. Il liste uniquement les invitations actionnables
retournées par l’API, sans prétendre fournir un historique.

Avec `invitations:manage`, l’Admin peut :

- inviter un courriel au rôle Admin, Manager ou Sales ;
- renvoyer une invitation ;
- révoquer une invitation après confirmation.

`invitation_request_id` et `resend_request_id` suivent la même notion d’intention que le provisioning : même UUID et
même corps après résultat ambigu, nouvel UUID après changement métier ou succès. Aucun UUID n’est affiché, journalisé
dans la console ou stocké.

Les conflits sont traduits précisément : membre déjà actif, réactivation explicite requise, invitation déjà en attente,
organisation inactive, invitation acceptée, limite de renvoi et résultat inconnu. L’interface ne révèle jamais si le
courriel correspond à un compte global d’une autre organisation.

## 13. Clients API, hooks et état

### 13.1 Découpage

- `authApi.switchOrganization` pour la rotation de contexte ;
- `platformApi` pour liste, création, renvoi et révocation initiale ;
- `organizationApi` pour métadonnées, membres et invitations ;
- hooks par ressource, sans composant réalisant directement un `fetch` ;
- enveloppe d’erreur commune traitée par `httpClient` ;
- UUID générés dans un utilitaire injectable afin de rendre les tests déterministes.

### 13.2 Cycle de requête

Chaque écran expose explicitement : `idle`, `loading`, `success`, `empty`, `error` et `refreshing` lorsque pertinent.

- `AbortController` annule les lectures au démontage ou au changement d’organisation ;
- une réponse ancienne ne remplace jamais un état plus récent ;
- aucune lecture ou mutation n’est relancée automatiquement ;
- les boutons sont désactivés pendant leur propre intention, pas toute la page sans nécessité ;
- une mutation réussie réconcilie la réponse serveur au lieu de reconstruire l’objet côté client ;
- un `401` vide centralement la session ;
- un `403` garde la session et affiche l’état d’accès refusé ;
- un `409` ne produit aucun retry automatique ;
- un `503` conserve la saisie utile et permet un retry explicite.

## 14. Gestion des capacités et invalidation

- les routes et liens utilisent la réponse `capabilities` de la session ;
- les onglets et actions privilégiés ne sont pas rendus sans capacité ;
- les données ne sont pas préchargées pour une section invisible ;
- une capacité perdue après un changement de rôle provoque un `401` ou un nouvel état de session au prochain échange ;
- un changement d’organisation remplace la totalité des capacités ;
- aucun cache d’autorisation n’est conservé hors `AuthProvider` ;
- `AuthProvider` expose une opération explicite d’invalidation pour l’auto-modification d’appartenance ;
- l’interface ne déduit jamais un droit depuis le libellé du rôle si la capacité n’est pas présente.

## 15. Erreurs, confirmations et retours utilisateur

Les erreurs utilisent les messages serveur contrôlés et leur `code`, sans afficher stack, SQL, SMTP, Redis, clé,
cookie, CSRF, curseur ou UUID.

| Code | Comportement UI |
| --- | --- |
| `authentication_required` | session vidée, retour connexion |
| `insufficient_capability` | page ou panneau 403 |
| `*_version_conflict` | saisie conservée, rechargement explicite |
| `last_active_administrator` | explication métier, aucune modification locale |
| `idempotency_key_reused` | nouvelle intention obligatoire après vérification des champs |
| `*_outcome_unknown` | retry explicite avec le même UUID et le même corps |
| `invitation_rate_limited` | message et délai `Retry-After` |
| `*_unavailable` | état temporaire, aucun détail fournisseur |

Les confirmations concernent uniquement les actions à conséquence forte : désactivation, retrait du rôle Admin et
révocation. Elles utilisent un dialogue accessible, restituent le focus au déclencheur et restent inertes derrière un
fond non interactif.

Les succès de création, modification, renvoi et révocation sont annoncés dans une région `aria-live="polite"`. Les
erreurs utilisent `role="alert"`. Le focus va au résumé d’erreur ou au premier champ invalide.

## 16. Accessibilité et responsive

Exigences minimales :

- navigation complète au clavier ;
- lien d’évitement vers le contenu ;
- focus visible et ordre logique ;
- libellé explicite pour chaque champ et action contextuelle ;
- état courant de navigation avec `aria-current="page"` ;
- boutons iconiques avec nom accessible ;
- chargement annoncé sans remplacer brutalement le focus ;
- rôle/état jamais communiqués uniquement par couleur ;
- tableaux avec en-têtes sémantiques et équivalent lisible sur petit écran ;
- dialogues avec titre, description, focus initial et touche Échap ;
- contraste conforme au niveau AA pour textes, contrôles et focus ;
- respect de `prefers-reduced-motion` ;
- aucune troncature irréversible du courriel ou du nom ;
- utilisable à 320 px de large et à 200 % de zoom.

Les tests utilisent en priorité les rôles, noms et libellés accessibles de Testing Library. Les parcours critiques sont
également contrôlés avec un moteur axe automatisé ajouté à la suite frontend.

## 17. Design et cohérence visuelle

- réutiliser les couleurs, espacements, typographies, cartes, champs et bannières existants ;
- ne pas dupliquer le logo ou le nom du produit dans la page Recherche ;
- conserver l’écran Google reconnaissable et ses métriques ;
- utiliser un en-tête global compact plutôt qu’une seconde barre latérale autour du formulaire de recherche ;
- présenter les pages d’administration dans une largeur de lecture maîtrisée ;
- prévoir états vides explicatifs, squelettes sobres et boutons primaires uniques par zone ;
- conserver les termes « Prospect CRM », « établissements », « membres » et « invitations » ;
- ne réintroduire ni « générateur » ni « leads » dans l’interface.

## 18. Sécurité et confidentialité du navigateur

Interdictions :

- `localStorage`, `sessionStorage`, IndexedDB, Cache API ou service worker pour session, capacités, formulaires,
  curseurs, UUID, résultats Google ou réponses d’administration ;
- paramètres sensibles dans l’URL ;
- journalisation console des corps, réponses ou erreurs brutes ;
- préchargement d’une route non autorisée ;
- retry automatique d’une mutation ;
- reconstruction optimiste d’une autorisation ou d’une version ;
- conservation d’un état locataire après changement d’organisation.

Les seules données durables du navigateur sont le cookie `HttpOnly` géré par le serveur. Les préférences visuelles ne
sont pas introduites dans cet incrément.

## 19. Backend et données

2.3.5 réutilise les routes existantes :

- `GET/POST /api/platform/organizations` et actions de première invitation ;
- `GET/PATCH /api/organization` ;
- `GET/PATCH /api/organization/members` ;
- `GET/POST/DELETE /api/organization/invitations` et action de renvoi ;
- `POST /api/auth/switch-organization` ;
- `GET /api/auth/me`.

Aucune nouvelle table, colonne, politique RLS, fonction SQL ou migration n’est prévue. Une modification backend n’est
admise que si l’interface révèle un contrat impossible à consommer de façon sûre. Elle devra être minimale, testée et
documentée avant implémentation.

## 20. Tests frontend obligatoires

### 20.1 Routage et shell

- redirections déterministes de `/` et `/login` ;
- liens profonds et retour/avance ;
- `404` au lieu du fallback silencieux vers Recherche ;
- aucune action privilégiée pendant `loading` ;
- navigation exacte pour chaque matrice de capacités ;
- plateforme sans organisation dirigée vers son écran ;
- utilisateur sans organisation et sans rôle plateforme conservé dans l’état restreint.

### 20.2 Changement d’organisation

- sélecteur absent avec une seule appartenance et présent avec plusieurs ;
- une seule commande par action ;
- réponse installée avec nouveau CSRF ;
- ancienne session conservée sur erreur ;
- résultats Google, formulaires, curseurs et réponses en vol supprimés ;
- route non autorisée remplacée par une destination sûre ;
- réponse tardive de l’ancienne organisation ignorée.

### 20.3 Plateforme

- liste, état vide, pagination et déduplication ;
- création avec UUID stable sur retry ambigu et renouvelé après modification ;
- absence de double soumission ;
- renvoi/révocation selon état ;
- `429`, conflit d’idempotence et résultat inconnu ;
- aucune donnée locataire ou secret rendu.

### 20.4 Organisation, membres et invitations

- lecture seule Manager/Sales ;
- modification Admin avec version exacte ;
- absence d’action sans capacité ;
- conflit de version sans écrasement ;
- dernier Administrateur protégé ;
- auto-modification vidant immédiatement la session ;
- pagination des membres et invitations ;
- UUID idempotents par intention ;
- conflits d’appartenance et d’invitation correctement traduits ;
- confirmation avant action forte.

### 20.5 Accessibilité et confidentialité

- axe sans violation sérieuse sur chaque page et dialogue ;
- parcours clavier des menus, onglets, formulaires et confirmations ;
- focus et régions live ;
- aucun stockage Web ;
- aucun secret ou identifiant technique visible ;
- rendu mobile et zoom contrôlés ;
- recherche Google, attribution, carte et export désactivé inchangés.

## 21. Tests backend et intégration obligatoires

Même sans nouvelle API, les suites suivantes sont des barrières :

- matrice plateforme/tenant de toutes les routes consommées ;
- RLS inter-organisation ;
- dernier Administrateur concurrent ;
- versions optimistes ;
- cycles complets d’invitation initiale et membre ;
- idempotence et résultats inconnus ;
- rotation de session et CSRF au changement d’organisation ;
- ancienne session refusée après changement de privilège ;
- pagination et curseurs signés ;
- PostgreSQL, Redis et Mailpit réels ;
- protections Google 2.3.4 complètes.

`REQUIRE_INFRASTRUCTURE_TESTS=true` est obligatoire dans le passage de validation. Aucun `skip` d’infrastructure n’est
accepté avant 2.4. L’avertissement de cache pytest lié à OneDrive doit être évité dans la commande de validation avec un
cache accessible ou `-p no:cacheprovider`, sans masquer les avertissements applicatifs.

## 22. Verrou qualité et CI

La barrière finale exige :

1. Alembic `current` à `20260802_0005 (head)` ;
2. Alembic `check` sans opération ;
3. Ruff ;
4. format Ruff ;
5. mypy ;
6. pytest unitaire ;
7. pytest d’intégration PostgreSQL/Redis/Mailpit sans `skip` ;
8. tests de frontières Clean Architecture ;
9. ESLint sans avertissement ;
10. Vitest ;
11. contrôles axe ;
12. build Vite ;
13. Azure Pipelines avec les mêmes barrières ;
14. `git diff --check` ;
15. vérification manuelle clavier, responsive, rôles et changement d’organisation.

Les totaux réels sont consignés après exécution. Aucun nombre hérité d’un rapport précédent n’est recopié comme preuve.
La pipeline ne publie aucun artefact si un contrôle obligatoire échoue.

## 23. Documentation à livrer

- README : navigation, écrans, capacités et parcours multi-organisation ;
- documentation utilisateur par rôle ;
- documentation technique du shell, des clients API et de l’idempotence frontend ;
- procédures locales sans scripts d’administration obligatoires pour les opérations désormais visibles ;
- pages légales seulement si les données affichées ou finalités changent ;
- rapport 2.3.5 avec preuves, critiques, revues et captures de validation ;
- mise à jour du statut global 2.3 et autorisation explicite de 2.4.

Les scripts PowerShell existants restent des outils de diagnostic et d’automatisation locale. Ils ne sont pas supprimés
parce qu’une interface existe, mais le guide utilisateur privilégie désormais les écrans.

## 24. Séquence d’implémentation proposée

### 2.3.5-A — Routage et shell

- routes canoniques, redirections, 403/404 ;
- `AuthenticatedLayout` et navigation par capacité ;
- page Compte ;
- tests de routage et accessibilité de base.

État au 3 août 2026 : lot implémenté, contrôles automatisés verts et parcours local accepté par le responsable produit. Le rapport, les limites transitoires et le
protocole d’acceptation figurent dans
[`PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md).

### 2.3.5-B — Organisation active

- sélecteur d’organisation ;
- extension contrôlée d’`AuthProvider` ;
- invalidation des états locataires ;
- page Organisation lecture/modification ;
- tests de rotation, conflits et réponses tardives.

État au 3 août 2026 : lot implémenté, matrice automatisée verte et parcours local accepté par le responsable produit.
Le détail des protections, les revues et le protocole d’acceptation locale figurent dans
[`PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md).

### 2.3.5-C — Membres et invitations

- clients API et hooks ;
- liste/pagination ;
- édition versionnée ;
- invitations idempotentes, renvoi et révocation ;
- tests de rôles, dernier Admin et auto-invalidation.

État au 3 août 2026 : lot implémenté, matrice automatisée verte et validation produit locale obtenue. Les contrats consommés, les preuves, les revues et
le protocole d’acceptation figurent dans
[`PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md).

### 2.3.5-D — Plateforme

- liste paginée ;
- création idempotente ;
- première invitation ;
- redirection plateforme sans organisation ;
- tests de séparation plateforme/locataire.

État au 3 août 2026 : spécification, implémentation, matrice automatisée et parcours produit local validés, sans
nouvelle migration ni API. Les décisions, preuves et revues figurent dans
[`PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md) et
[`PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md).

### 2.3.5-E — Verrou final

- responsive, clavier et axe ;
- non-régression Google ;
- documentation et rapport ;
- suite infrastructure sans `skip` ;
- trois critiques, deux revues de code et validation produit.

État au 3 août 2026 : la spécification détaillée et ses seize décisions sont validées par le responsable produit. Elle transforme
les contrôles existants en deux barrières reproductibles, locale et Azure, et ferme explicitement les 17 tests
d’infrastructure ignorés. L’implémentation attend le GO explicite du responsable produit et devra respecter la section 22 de
[`PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md).

Chaque sous-incrément reste testable isolément. Aucun écran incomplet n’est ajouté à la navigation avant que ses tests
et sa gestion d’erreurs soient prêts.

## 25. Protocole local d’acceptation prévu

1. démarrer PostgreSQL, Redis et Mailpit ;
2. confirmer Alembic `20260802_0005 (head)` ;
3. créer une organisation de démonstration et au moins trois comptes Admin/Manager/Sales ;
4. préparer un compte commun à deux organisations ;
5. vérifier les redirections et menus de chaque rôle ;
6. modifier les métadonnées de l’organisation comme Admin et constater la lecture seule comme Manager/Sales ;
7. inviter, renvoyer, révoquer et accepter un membre depuis l’interface ;
8. provoquer un conflit de version et vérifier l’absence d’écrasement ;
9. tester la protection du dernier Admin ;
10. changer d’organisation et vérifier la disparition immédiate de toutes les données de l’ancienne ;
11. vérifier l’écran plateforme sans appartenance locataire ;
12. parcourir toute l’interface au clavier, à 320 px et à 200 % ;
13. vérifier l’absence de stockage et de secrets avec les outils navigateur ;
14. effectuer une recherche Google contrôlée et confirmer la non-régression 2.3.4 ;
15. exécuter la matrice qualité complète sans `skip` ;
16. consigner les résultats et obtenir l’acceptation produit avant 2.4.

## 26. Critique experte 1 — Sécurité et isolation

### Risques identifiés

- une navigation masquée pourrait être confondue avec une autorisation ;
- une réponse tardive de l’organisation A pourrait contaminer l’écran après passage à B ;
- une session plateforme pourrait afficher par erreur des actions locataires ;
- l’auto-rétrogradation pourrait laisser l’interface croire que la session reste valide ;
- un UUID idempotent réutilisé avec une commande modifiée provoquerait un conflit difficile à diagnostiquer.

### Réponses intégrées

- contrôles serveur inchangés et 403 sur accès direct ;
- annulation, clé de sous-arbre locataire et garde contre réponses périmées ;
- capacités plateforme et locataire séparées ;
- invalidation React immédiate après auto-modification ;
- UUID lié à une intention et renouvelé à toute modification métier.

Risque résiduel accepté : une requête déjà partie peut terminer côté serveur après une navigation. Sa réponse est
ignorée et RLS conserve l’isolation, mais l’opération volontaire peut avoir été appliquée.

## 27. Critique experte 2 — UX, accessibilité et erreurs

### Risques identifiés

- regrouper organisation, membres, invitations et plateforme dans un écran unique produirait une interface dense ;
- des actions simplement désactivées pour un rôle non autorisé créeraient de la confusion ;
- recharger automatiquement après `409` pourrait effacer une saisie ;
- un tableau desktop mal adapté deviendrait inutilisable au clavier ou sur mobile ;
- une confirmation générique ne préciserait pas la conséquence d’un retrait Admin.

### Réponses intégrées

- routes et pages séparées, onglet Invitations conditionnel ;
- actions absentes sans capacité, lecture seule explicite ;
- conservation de la saisie et rechargement choisi ;
- sémantique de tableau, équivalent responsive et tests axe/clavier ;
- confirmations spécifiques à l’action, au membre et à l’organisation.

Risque résiduel accepté : l’absence d’historique d’audit limite l’explication d’une modification passée jusqu’à 2.4.

## 28. Critique experte 3 — Fiabilité et exploitation

### Risques identifiés

- un retry réseau avec un nouvel UUID pourrait dupliquer une organisation ou une invitation ;
- annoncer un total sans support API produirait une information fausse ;
- conserver les 17 tests d’infrastructure en `skip` reporterait une dette critique vers 2.4 ;
- ajouter un framework d’état global ou une refonte visuelle augmenterait inutilement le risque ;
- publier une page partiellement testée casserait le verrou de qualité.

### Réponses intégrées

- notion explicite d’intention idempotente ;
- pagination « Charger la suite » sans total ;
- `REQUIRE_INFRASTRUCTURE_TESTS=true` et zéro `skip` obligatoires ;
- état React local, `AuthProvider` borné et clients/hooks dédiés ;
- livraison en cinq sous-incréments non navigables avant leur complétude.

Risque résiduel accepté : les scripts de diagnostic et l’interface coexistent ; leur contrat doit rester synchronisé
jusqu’à l’arrivée d’une automatisation de préproduction complète.

## 29. Seize décisions validées

1. Limiter 2.3.5 à l’interface et au verrou qualité, sans migration ni nouvelle API sauf blocage démontré.
2. Adopter les routes canoniques `/app/search`, `/app/account`, `/app/admin/organization`, `/app/admin/users` et
   `/app/platform/organizations`, avec redirections déterministes et vraie page 404.
3. Introduire un shell authentifié commun, sans clignotement de privilège et sans refonte du contenu Google.
4. Filtrer navigation, routes, onglets et actions par capacités, tout en conservant le serveur comme seule autorité.
5. Livrer un sélecteur visible dès deux appartenances actives, fondé sur `membership_id`, avec rotation atomique et
   purge de tout état locataire.
6. Livrer une page Compte strictement en lecture seule, sans simuler la modification du profil ou du mot de passe.
7. Livrer la page Plateforme avec liste, création idempotente et actions de première invitation, sans données
   locataires ni suspension.
8. Livrer la page Organisation en lecture pour tous les rôles locataires et en modification versionnée pour Admin.
9. Livrer la page Membres en lecture pour Admin/Manager, en gestion pour Admin, et la masquer entièrement à Sales.
10. Réserver les invitations de membres à Admin et conserver l’UUID d’une même intention après un résultat ambigu.
11. Ne jamais rejouer automatiquement une mutation ; traiter explicitement conflits de version, dernier Admin,
    idempotence, limites et résultats inconnus.
12. Invalider immédiatement l’état frontend après auto-modification et ignorer toute réponse tardive d’une ancienne
    organisation.
13. Interdire tout stockage Web ou URL sensible et conserver les scripts seulement comme outils de diagnostic.
14. Exiger clavier, focus, régions live, responsive 320 px/200 %, contraste AA et contrôles axe automatisés.
15. Garder toutes les garanties Google 2.3.4 inchangées et fermer les 17 `skip` d’infrastructure avant 2.4.
16. Implémenter en cinq sous-incréments, puis exécuter trois critiques, deux revues de code, la matrice complète et la
    validation produit avant d’autoriser 2.4.

Ces seize décisions ont été validées par le responsable produit le 2 août 2026. Elles constituent le contrat de
l’incrément 2.3.5 ; toute dérogation doit être documentée et validée avant son implémentation.

## 30. Définition de « terminé »

2.3.5 est terminé uniquement si :

- les cinq routes authentifiées et leurs gardes sont opérationnelles ;
- chaque rôle voit exactement ses pages et actions ;
- le changement d’organisation renouvelle la session et élimine tout état de l’ancienne ;
- les formulaires respectent versions, idempotence et résultats ambigus ;
- plateforme et locataire restent strictement séparés ;
- l’auto-modification invalide immédiatement l’interface ;
- aucune donnée sensible n’est stockée ou placée dans l’URL ;
- les écrans sont utilisables au clavier, sur mobile et à 200 % ;
- les protections Google sont inchangées ;
- Alembic, Ruff, mypy, pytest réel sans `skip`, ESLint, Vitest, axe, build et pipeline sont verts ;
- trois critiques et deux revues ne laissent aucun défaut bloquant ;
- le responsable produit valide le parcours multi-rôle et autorise 2.4.

## 31. Références internes

- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_4_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_4_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_E_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_3_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_3_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_SPECIFICATIONS_DETAILLEES.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)

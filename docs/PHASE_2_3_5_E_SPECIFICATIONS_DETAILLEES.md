# Phase 2.3.5-E — Spécifications détaillées du verrou qualité final

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Lot | 2.3.5-E — Verrou qualité final |
| Version | 1.1 |
| Date | 3 août 2026 |
| Statut | Implémentation effectuée ; validation Docker, Azure et manuelle en attente |
| Validation produit | 3 août 2026 — validation des seize décisions de la section 22 |
| Prérequis | 2.3.5-A/B/C/D implémentés et validés localement |
| Migration SQL | Aucune prévue |
| Nouvelle API métier | Aucune prévue |
| Révision Alembic attendue | `20260802_0005 (head)` |
| Résultat attendu | Autorisation explicite de préparer 2.4, ou No-Go documenté |

## 1. Objectif

2.3.5-E ne livre pas un nouveau module CRM. Il transforme les garanties accumulées de 2.1 à 2.3.5-D en barrières
reproductibles avant le démarrage de 2.4 et avant toute préparation au déploiement.

Le lot doit établir, par des preuves automatisées et manuelles, que :

- les parcours A à D restent fonctionnels pour chaque rôle ;
- l’isolation locataire, les sessions, le CSRF, RLS et l’idempotence restent intacts ;
- les 17 scénarios PostgreSQL, Redis et Mailpit ne sont plus ignorés ;
- les écrans critiques ne présentent aucune violation axe bloquante ;
- le clavier, le focus, le responsive à 320 px, le zoom à 200 % et le contraste AA sont contrôlés ;
- les limites Google validées restent inchangées ;
- Azure Pipelines applique les mêmes barrières que le poste local ;
- la documentation décrit l’état réellement testé, sans recopier des totaux historiques.

Une suite verte ne suffit pas si une barrière a été désactivée, ignorée ou rejouée jusqu’à réussir sans analyse.

## 2. Périmètre

### 2.1 Inclus

- ajout du moteur axe à la suite Vitest ;
- tests d’accessibilité ciblant les états représentatifs des pages A à D ;
- corrections non visuelles nécessaires à l’accessibilité ou à la stabilité des tests ;
- orchestration locale reproductible du verrou qualité ;
- exécution réelle de PostgreSQL 17, Redis 7 et Mailpit avec `REQUIRE_INFRASTRUCTURE_TESTS=true` ;
- assertion automatique de zéro test ignoré lors du passage d’infrastructure obligatoire ;
- vérification de la reconstruction des migrations et de `alembic check` ;
- non-régression des limites Google et de l’absence d’export historique ;
- contrôle des stockages Web, URLs, journaux et artefacts ;
- durcissement d’Azure Pipelines si un écart avec le verrou local est constaté ;
- matrice manuelle multi-rôle, multi-organisation et plateforme ;
- trois critiques, deux revues de code et rapport final Go/No-Go ;
- actualisation des documentations utilisateur, technique et d’exploitation.

### 2.2 Corrections admises

Une correction découverte pendant E est admise sans nouvelle spécification fonctionnelle si elle :

- rétablit une décision déjà validée ;
- améliore sémantique HTML, libellés, focus, navigation clavier ou contraste sans refonte visuelle ;
- rend un test déterministe sans affaiblir son assertion ;
- corrige le pipeline ou l’orchestration de test sans changer les règles métier ;
- ferme une fuite de données, une incohérence de capacité ou une non-conformité Google.

Toute correction backend, migration, nouvelle API, modification de limite Google ou nouvelle fonction utilisateur
interrompt E et exige une décision produit séparée.

### 2.3 Exclus

- nouvelle fonctionnalité CRM ;
- suspension d’organisation, audit métier ou historique complet ;
- changement du design validé ;
- couverture par pourcentage arbitraire ;
- test automatisé utilisant une vraie clé Google ou générant un coût ;
- fournisseur SMTP de production ;
- déploiement, domaine public, certificats ou secrets de production ;
- mise à niveau générale des dépendances sans nécessité démontrée.

## 3. État initial constaté

Au début de E :

- A, B, C et D sont validés localement par le responsable produit ;
- Vitest valide 102 scénarios répartis dans 24 fichiers ;
- pytest valide 133 scénarios et en ignore 17 sans infrastructure explicitement requise ;
- Ruff, format Ruff, mypy, ESLint, le build Vite et `alembic check` sont verts ;
- Azure Pipelines démarre déjà PostgreSQL, Redis et Mailpit et définit `REQUIRE_INFRASTRUCTURE_TESTS=true` ;
- aucun moteur axe n’est encore déclaré dans les dépendances frontend ;
- la pipeline ne porte pas encore une assertion autonome et lisible « zéro test ignoré » ;
- les contrôles 320 px, zoom 200 %, clavier et contraste reposent encore sur une validation manuelle non centralisée.

Les nombres ci-dessus constituent un point de départ, pas les critères finaux. Le rapport E consignera les nombres
réellement collectés après les corrections.

## 4. Invariants non négociables

E doit prouver sans les modifier :

1. organisation active dérivée uniquement de la session serveur ;
2. aucune commande locataire contenant `organization_id` ;
3. capacités vérifiées côté serveur, jamais déduites seulement d’un rôle affiché ;
4. absence d’accès locataire implicite pour l’Administrateur plateforme ;
5. dernier Administrateur actif protégé, y compris en concurrence ;
6. cookies `HttpOnly`, origine fiable, CSRF et JSON strict sur les mutations ;
7. rotation ou invalidation correcte des sessions après changement de contexte ou de privilège ;
8. RLS active avec le rôle PostgreSQL applicatif ;
9. intentions idempotentes stables après résultat ambigu et jamais persistées dans le navigateur ;
10. aucune réponse sensible mise en cache ;
11. un seul Text Search Google par action, `pageSize=20`, aucun suivi de `nextPageToken` ;
12. aucun téléphone ou site Web dans les résultats Google ;
13. Maps Static accessible seulement avec une concession liée, à usage terminal ;
14. export historique absent côté API et maintenu inaccessible dans l’interface ;
15. attribution Google Maps visible ;
16. absence des termes « générateur » et « leads » dans l’interface utilisateur.

## 5. Stratégie d’exécution

Le verrou possède deux passages indépendants :

1. un passage local sur une composition de test dédiée et propre ;
2. un passage Azure Pipelines sur un agent vierge.

Les deux doivent être verts sur la même révision Git. Une relance est admise uniquement après diagnostic. Toute
relance, sa cause et la correction éventuelle sont consignées dans le rapport. Une réussite obtenue en ignorant un
test, en retirant une assertion ou en réutilisant une base non maîtrisée est invalide.

## 6. Orchestration locale

Un point d’entrée PowerShell unique sera ajouté ou adapté pour exécuter le verrou sans exposer de secret. Il doit :

1. vérifier Docker et les outils requis ;
2. utiliser explicitement `compose.test.yaml` et un nom de projet de test dédié ;
3. démarrer PostgreSQL, Redis et Mailpit avec attente des healthchecks ;
4. provisionner le rôle PostgreSQL applicatif de test ;
5. appliquer Alembic jusqu’à `head` ;
6. vérifier le downgrade contrôlé puis la reconstruction jusqu’à `head` sur la base de test uniquement ;
7. exécuter `alembic check` ;
8. exécuter Ruff, format Ruff et mypy ;
9. exécuter toute la suite pytest avec les cinq variables `TEST_*` et `REQUIRE_INFRASTRUCTURE_TESTS=true` ;
10. refuser le résultat si un test est ignoré ;
11. exécuter ESLint, toute la suite Vitest avec axe, puis le build Vite ;
12. exécuter `git diff --check` ;
13. arrêter la composition de test même en cas d’échec.

Le script ne lit ni n’affiche `.env`, les clés Google ou les mots de passe de développement. Il utilise exclusivement
les identifiants non sensibles de `compose.test.yaml`. Le nettoyage ne cible que la composition et les volumes de
test explicitement résolus ; il ne touche jamais la base locale de développement.

## 7. PostgreSQL, Redis et Mailpit réels

### 7.1 Barrière d’infrastructure

Le passage obligatoire fournit :

- `TEST_DATABASE_URL` avec le rôle applicatif ;
- `TEST_MIGRATION_DATABASE_URL` avec le propriétaire de migration ;
- `TEST_REDIS_URL` ;
- `TEST_MAILPIT_API_URL` ;
- `TEST_MAILPIT_SMTP_PORT` ;
- `REQUIRE_INFRASTRUCTURE_TESTS=true`.

Avec ce drapeau, une dépendance absente produit un échec, jamais un `skip`. Une assertion supplémentaire inspecte le
rapport JUnit et échoue si le nombre total de tests ignorés est supérieur à zéro.

### 7.2 Scénarios obligatoires

- readiness PostgreSQL/Redis ;
- commit et rollback d’un Unit of Work ;
- sessions et limites Redis ;
- rôle Web séparé du propriétaire ;
- RLS inter-organisation en lecture et écriture ;
- provisioning idempotent et pagination ;
- renvoi/révocation de l’invitation initiale ;
- livraison Mailpit d’un seul message minimal ;
- acceptation et activation atomiques ;
- administration d’organisation, membres, versions et dernier Admin ;
- changement d’organisation et refus de l’ancienne session.

### 7.3 Migrations

La base de test doit démontrer :

- `current` égal à `20260802_0005 (head)` ;
- downgrade jusqu’à `20260723_0002` puis upgrade complet ;
- reconstruction des fonctions, politiques RLS et droits ;
- `alembic check` sans nouvelle opération ;
- démarrage de l’application avec le rôle applicatif après reconstruction.

La base de développement et toute base contenant des données utilisateur sont exclues de ce test destructif.

## 8. Accessibilité automatisée

### 8.1 Outil

La suite frontend ajoute `axe-core` au travers d’un adaptateur compatible Vitest/Testing Library. La dépendance est
verrouillée dans `package-lock.json`. Les tests axe appartiennent à `npm test` et à `npm run test:ci` ; il n’existe pas
de commande optionnelle permettant au pipeline de les oublier.

### 8.2 États représentatifs

Les contrôles axe couvrent au minimum :

- Connexion ;
- Invitation : vérification, formulaire valide et erreur terminale ;
- état sans organisation ;
- shell et page Compte ;
- Recherche avant recherche, avec résultats et avec erreur ;
- Organisation en lecture seule et en édition/conflit ;
- Membres en lecture Manager et en gestion Admin ;
- onglet Invitations et dialogue de confirmation ;
- Plateforme en lecture seule, provisioning et dialogue de révocation ;
- pages 403 et 404 ;
- navigation mobile ouverte.

Chaque état doit produire zéro violation axe. Une règle ne peut être désactivée qu’en raison d’une limitation
documentée de jsdom, avec un contrôle manuel équivalent et une justification dans le rapport. Le contraste reste une
barrière manuelle, car jsdom ne calcule pas fidèlement le rendu final.

## 9. Clavier, focus et sémantique

Les tests automatisés et le parcours manuel vérifient :

- activation du lien d’évitement et arrivée sur `#route-content` ;
- focus visible sur liens, champs, boutons et contrôles iconiques ;
- ouverture/fermeture du menu mobile, touche Échap et restitution du focus ;
- onglets Membres/Invitations avec relations `tab`/`tabpanel`, focus géré et touches attendues ;
- dialogue avec titre et description, focus initial, boucle Tab/Maj+Tab, Échap et restitution du focus ;
- focus dirigé vers l’erreur ou le premier champ invalide lorsque l’action échoue ;
- aucune interaction possible avec l’arrière-plan d’un dialogue modal ;
- boutons occupés annoncés et non activables deux fois ;
- succès dans une région polie et erreurs dans une région d’alerte ;
- rôle et état compréhensibles sans dépendre uniquement de la couleur.

Les corrections ARIA restent minimales : aucun rôle ne doit remplacer un élément HTML natif plus approprié.

## 10. Responsive, zoom et contraste

Le contrôle manuel est réalisé au minimum avec Chrome ou Edge sur :

- 320 × 568 CSS px à 100 % ;
- 1280 × 720 CSS px à 200 % de zoom ;
- largeur bureau normale à 100 %.

Il couvre Connexion, Invitation, Recherche, Compte, Organisation, Membres/Invitations, Plateforme, 403 et 404. Les
critères sont : aucun défilement horizontal de page, aucune action inaccessible, aucun texte essentiel tronqué, aucun
chevauchement, et conservation d’un ordre de lecture logique.

Le contraste doit atteindre WCAG 2.2 AA : 4,5:1 pour le texte normal, 3:1 pour le grand texte et 3:1 pour les
composants/focus. Les états hover, focus, disabled, erreur et succès sont inclus. Toute exception de marque doit être
présentée au produit ; elle ne peut être acceptée silencieusement.

## 11. Matrice fonctionnelle multi-rôle

| Profil | Routes visibles | Actions attendues | Interdictions vérifiées |
| --- | --- | --- | --- |
| Sans organisation | Compte/état restreint | déconnexion | Recherche et administration |
| Sales | Recherche, Compte, Organisation en lecture | recherche Google | membres, invitations, édition |
| Manager | Recherche, Compte, Organisation, Membres | lecture | mutations membres/invitations |
| Admin | routes locataires | édition et gestion autorisées | franchissement de locataire |
| Plateforme sans appartenance | Plateforme, Compte | provisioning | données CRM/Google locataires |
| Plateforme avec appartenance | routes de ses capacités | actions explicitement accordées | droit locataire implicite |
| Multi-organisation | routes du contexte actif | changement par `membership_id` | conservation de l’ancien état |

Pour chaque profil, un lien profond non autorisé rend un 403 contrôlé sans déclencher le chargement de la ressource.
Le changement d’organisation purge résultats Google, concessions Maps, formulaires, curseurs et réponses en vol.

## 12. Non-régression Google

### 12.1 Automatisée sans coût

Les fournisseurs Google restent simulés. Les tests prouvent :

- un seul appel Text Search par action ;
- `pageSize=20` et au plus vingt résultats rendus ;
- aucun suivi de `nextPageToken` ;
- masque de champs sans téléphone ni site Web ;
- absence de route d’export historique ;
- bouton d’export visible mais inaccessible ;
- `Cache-Control: no-store` ;
- attribution Google Maps visible ;
- aucun stockage des résultats ;
- Maps Static refusée sans concession, pour une autre session ou après consommation ;
- échec Maps terminal sans seconde facturation automatique.

Aucune clé réelle n’est injectée dans Azure Pipelines et aucun appel facturable n’est exécuté en CI.

### 12.2 Contrôle manuel borné

Avec la clé locale déjà configurée, le responsable produit effectue au maximum une recherche Text Search et une
capture Maps Static. Il confirme les compteurs d’appel, vingt résultats maximum, l’attribution et l’absence des champs
de contact. Cette validation ne modifie pas les limites Google.

## 13. Confidentialité du navigateur et des artefacts

Le verrou vérifie :

- absence d’utilisation de `localStorage`, `sessionStorage`, IndexedDB, Cache API et service worker pour les données
  de session, Google, administration, formulaires, curseurs ou intentions ;
- absence de CSRF, cookie, jeton d’invitation, UUID idempotent ou corps métier dans l’URL ;
- absence de `console.log`, `console.debug` ou erreur brute contenant une réponse sensible ;
- purge de l’état à la déconnexion et au changement d’organisation ;
- artefact sans `.env`, base de données, messages Mailpit, caches, résultats de test ou sources Git ;
- présence de `.env.example` sans secret réel ;
- aucun secret Google dans le bundle Vite.

Les tests dynamiques espionnent les APIs de stockage pendant les parcours critiques. Un contrôle statique complète la
preuve, sans considérer une simple recherche textuelle comme unique garantie.

## 14. Backend, sécurité et architecture

Les suites existantes restent obligatoires pour :

- frontières domaine/application/infrastructure/présentation ;
- absence d’import FastAPI/SQLAlchemy dans le domaine et les cas d’utilisation ;
- injection des ports Google, session, verrou, jeton, horloge et livraison ;
- erreurs API contrôlées sans détail interne ;
- pagination signée et limites de taille ;
- concurrence du dernier Administrateur et des intentions idempotentes ;
- `no-store`, CSRF, origine et JSON strict ;
- RLS et portée issue de la session.

E ne déplace pas de responsabilité métier dans React et n’assouplit aucune politique serveur pour faciliter un test.

## 15. Frontend, lint et build

Les barrières frontend sont :

- `npm ci` depuis le lockfile ;
- ESLint avec zéro avertissement ;
- Vitest complet incluant axe ;
- absence de test `.only`, `.skip` ou `todo` livré ;
- build Vite de production ;
- contrôle du contenu de `dist` ;
- aucun warning React, mise à jour hors `act` ou rejet de promesse non traité ;
- aucun changement du contenu métier Google validé.

Aucun seuil de couverture global n’est introduit dans E : il n’existe pas de base historique fiable et un pourcentage
pourrait encourager des assertions superficielles. La couverture des parcours critiques listés dans ce document est
la barrière. Un seuil chiffré pourra être défini après collecte d’une référence dans une phase dédiée.

## 16. Azure Pipelines

La pipeline doit refléter l’ordre logique suivant :

1. installation Python et Node depuis versions déclarées ;
2. restauration déterministe des dépendances ;
3. Ruff, format Ruff et mypy ;
4. démarrage de `compose.test.yaml` et healthchecks ;
5. provisionnement du rôle PostgreSQL ;
6. migrations, reconstruction et `alembic check` ;
7. pytest avec infrastructure obligatoire et zéro `skip` ;
8. publication du JUnit backend même en cas d’échec ;
9. arrêt garanti de la composition ;
10. ESLint, Vitest avec axe et build ;
11. publication du JUnit frontend ;
12. `git diff --check` et contrôle d’artefact ;
13. publication de l’artefact seulement si toutes les barrières précédentes sont vertes.

La pipeline n’utilise aucune clé Google. Les mots de passe de `compose.test.yaml` sont réservés à l’environnement
éphémère de test et ne sont jamais réutilisés ailleurs.

## 17. Gestion des échecs et des défauts

### 17.1 Classification

- **Bloquant** : sécurité, isolation, RLS, session, CSRF, perte de données, idempotence, conformité Google, secret,
  migration, build, accessibilité empêchant un parcours ou test obligatoire ignoré.
- **Majeur** : rôle incorrect, action indisponible, erreur non récupérable, responsive masquant une action, focus perdu.
- **Mineur** : défaut cosmétique sans perte d’information ni d’action.

E ne peut être accepté avec un défaut bloquant ou majeur connu. Un défaut mineur peut être reporté seulement avec un
ticket, une justification, un impact borné et l’accord explicite du responsable produit.

### 17.2 Règles de correction

- ajouter d’abord un test reproduisant le défaut lorsque c’est possible ;
- corriger au niveau propriétaire de la règle ;
- rejouer la suite ciblée puis le verrou complet ;
- ne jamais désactiver une règle axe ou une assertion pour obtenir le vert ;
- documenter tout comportement intermittent et supprimer sa cause avant Go.

## 18. Preuves et rapport final

Le rapport 2.3.5-E contient :

- révision Git testée et date ;
- versions Python, Node, PostgreSQL, Redis et Mailpit ;
- commandes réellement exécutées ;
- nombres collectés, réussis, échoués et ignorés pour chaque suite ;
- résultat Alembic et révision `head` ;
- résultat axe par état représentatif ;
- checklist manuelle signée par profil et largeur ;
- preuve de l’unique contrôle Google facturable local ;
- liste des corrections effectuées dans E ;
- trois critiques et deux revues avec risques résiduels ;
- lien ou identifiant du passage Azure vert ;
- décision finale Go ou No-Go.

Les captures ne doivent contenir ni mot de passe, clé, cookie, CSRF, jeton d’invitation ou adresse réelle non prévue
pour les tests.

## 19. Trois critiques à effectuer après implémentation

### Critique 1 — Sécurité et multi-tenant

Rechercher activement les contournements de capacité, états locataires résiduels, identifiants croisés, secrets et
écarts entre visibilité frontend et autorité serveur.

### Critique 2 — Fiabilité et reproductibilité

Rechercher tests intermittents, dépendances à l’ordre, ports partagés, nettoyage incomplet, retries cachés, résultats
ambigus et divergences local/CI.

### Critique 3 — Accessibilité et usage réel

Rechercher parcours impossibles au clavier, focus perdu, contraste insuffisant, informations communiquées seulement
par couleur, débordements à 320 px/200 % et messages incompréhensibles.

Chaque critique est réalisée une première fois avant la matrice complète, puis réévaluée après les corrections.

## 20. Deux revues de code obligatoires

### Revue A — Architecture et maintenabilité

- respect des frontières Clean Architecture ;
- responsabilités des composants, hooks et clients ;
- duplication, annulation, concurrence et gestion d’erreurs ;
- cohérence tests/code/documentation ;
- absence de complexité ajoutée uniquement pour le test.

### Revue B — Sécurité, exploitation et conformité

- capacités, RLS, sessions, CSRF et `no-store` ;
- idempotence, limites et pannes de dépendances ;
- secrets, artefacts et journaux ;
- conformité Google et coût ;
- reproductibilité du pipeline et procédure de diagnostic.

Les deux revues doivent conclure explicitement « aucun défaut bloquant » ou produire un No-Go.

## 21. Séquence d’implémentation proposée

### E1 — Audit et harnais

- ajouter l’adaptateur axe et le contrôle zéro `skip` ;
- créer l’orchestrateur local ;
- aligner les commandes locales et Azure.

### E2 — Accessibilité et confidentialité

- ajouter la matrice axe et les tests clavier/focus ;
- corriger les écarts sans changement visuel ;
- ajouter les preuves de non-stockage et de purge.

### E3 — Infrastructure et non-régression

- exécuter migrations et 17 scénarios réels ;
- rejouer toutes les protections Google simulées ;
- vérifier l’artefact.

### E4 — Double passage et dossier de décision

- exécuter le verrou complet local ;
- obtenir le passage Azure vert sur la même révision ;
- réaliser contrôles manuels, trois critiques et deux revues ;
- produire le rapport et demander la décision Go/No-Go.

## 22. Seize décisions validées

1. Limiter E à un verrou qualité sans nouvelle fonctionnalité, migration ou API métier.
2. Autoriser uniquement les corrections minimales de conformité, accessibilité, sécurité, stabilité et pipeline.
3. Exiger deux passages indépendants verts sur la même révision : un local et un Azure Pipelines.
4. Introduire un orchestrateur PowerShell unique utilisant exclusivement `compose.test.yaml` et des ressources dédiées.
5. Exécuter les 17 tests PostgreSQL/Redis/Mailpit avec `REQUIRE_INFRASTRUCTURE_TESTS=true` et exiger zéro `skip` global.
6. Vérifier downgrade/reconstruction, `20260802_0005 (head)` et `alembic check` uniquement sur la base de test.
7. Intégrer axe à Vitest et couvrir tous les états représentatifs sans règle désactivée sans justification.
8. Faire du clavier, du focus, des dialogues, des onglets et des régions live des critères bloquants.
9. Exiger les contrôles manuels 320 px, zoom 200 % et contraste WCAG 2.2 AA sur les routes canoniques.
10. Rejouer la matrice Sans organisation/Sales/Manager/Admin/Plateforme/Multi-organisation et les liens profonds 403.
11. Conserver toute la non-régression Google automatisée sans clé réelle ni appel facturable en CI.
12. Limiter le smoke Google manuel à un Text Search et une Maps Static avec la clé locale déjà configurée.
13. Vérifier dynamiquement et statiquement l’absence de stockage sensible, fuite URL/console et secret dans l’artefact.
14. Ne pas imposer de seuil de couverture arbitraire ; bloquer sur les parcours critiques, les skips et les défauts.
15. Refuser le Go avec tout défaut bloquant ou majeur ; documenter et faire accepter explicitement tout défaut mineur.
16. Autoriser 2.4 uniquement après rapport, trois critiques, deux revues, passage Azure vert et validation produit.

Ces décisions ont été validées par le responsable produit le 3 août 2026. Elles constituent le contrat obligatoire de
2.3.5-E. Toute dérogation devra être documentée et validée avant son implémentation.

## 23. Définition de « terminé »

2.3.5-E est terminé uniquement si :

- l’orchestrateur local et Azure exécutent les mêmes barrières ;
- toutes les migrations et suites sont vertes ;
- le passage infrastructure contient zéro test ignoré ;
- axe ne signale aucune violation non justifiée ;
- la matrice manuelle clavier, responsive, contraste et rôles est conforme ;
- les invariants Google et multi-tenant sont inchangés ;
- l’artefact ne contient aucun secret ni état de test ;
- trois critiques et deux revues ne laissent aucun défaut bloquant ou majeur ;
- le rapport fournit les preuves réelles et une révision Git précise ;
- le passage Azure de cette révision est vert ;
- le responsable produit donne explicitement son Go pour 2.4.

## 24. Références internes

- [`PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_E_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_A_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_B_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_C_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_5_D_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_5_D_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_4_SPECIFICATIONS_DETAILLEES.md)
- [`PHASE_2_3_4_RAPPORT_IMPLEMENTATION.md`](PHASE_2_3_4_RAPPORT_IMPLEMENTATION.md)
- [`PHASE_2_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_3_SPECIFICATIONS_DETAILLEES.md)
- [`SPECIFICATION_CRM_V1.md`](SPECIFICATION_CRM_V1.md)

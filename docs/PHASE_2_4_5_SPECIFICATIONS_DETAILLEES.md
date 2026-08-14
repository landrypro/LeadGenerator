# Phase 2.4.5 — Spécifications détaillées du verrou qualité final

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.4.5 — Verrou qualité final |
| Version | 1.0 |
| Date | 13 août 2026 |
| Statut | Validé par le responsable produit |
| Validation produit | 13 août 2026 — validation des seize décisions |
| Prérequis | 2.4.1, 2.4.2, 2.4.3 et 2.4.4 implémentés |
| Migration attendue | `20260813_0008 (head)` |
| Résultat attendu | Go/No-Go formel avant l’ouverture de 2.5 |

Ce document définit le dernier incrément de la phase 2.4. Il ne livre pas de fonctionnalité métier nouvelle : il
apporte les preuves nécessaires pour déclarer l’audit transactionnel exploitable, documenté et prêt à servir de socle
à 2.5.

## 1. Objectif

2.4.5 doit établir, sur une même révision Git, que :

- les migrations 2.4 sont reproductibles sur une base vide ;
- l’audit est atomique, append-only, isolé et consultable selon les capacités ;
- les mutations couvertes, la suspension/réactivation et l’historique des invitations ne régressent pas ;
- PostgreSQL, Redis et les rôles applicatifs respectent les privilèges attendus ;
- les suites backend, frontend et les contrôles statiques sont verts ;
- la recette locale est reproductible et Azure Pipelines applique les mêmes barrières ;
- la documentation reflète l’état réellement vérifié ;
- trois critiques et deux revues indépendantes aboutissent à une décision Go/No-Go explicite.

Une suite verte obtenue en masquant un test, en conservant une base non maîtrisée ou en désactivant une barrière ne
constitue pas une validation.

## 2. Périmètre

### 2.1 Inclus

- migration `20260813_0008` et reconstruction complète jusqu’à `head` ;
- `alembic check`, contrôle des fonctions, rôles, grants et politiques RLS ;
- tests d’atomicité commit/rollback des mutations auditées ;
- tests d’isolation locataire et plateforme ;
- tests de suspension, réactivation, concurrence et idempotence ;
- consultation paginée de l’audit et historique des invitations ;
- contrôle des capacités, CSRF, sessions et réponses `no-store` ;
- non-régression Google : un Text Search, 20 résultats, aucun contact, aucun stockage navigateur ;
- suites pytest, Ruff, mypy, Vitest, ESLint et build frontend ;
- recette manuelle multi-rôles et multi-organisations ;
- exécution équivalente dans Azure Pipelines ;
- documentation technique, utilisateur, exploitation et rapport final.

### 2.2 Exclus

- nouveau module Prospects/Kanban ;
- import CSV, Facebook, LinkedIn ou autres connecteurs ;
- facturation et plans commerciaux ;
- modification des limites Google ;
- purge ou anonymisation de l’audit ;
- migration Oracle ou déploiement de production ;
- changement visuel non nécessaire à la qualité, l’accessibilité ou la recette.

## 3. Invariants non négociables

1. Aucun DML direct du rôle Web sur les tables métier ou d’audit.
2. L’audit ne peut être modifié, supprimé ou tronqué par l’application.
3. L’écriture métier et son événement d’audit sont atomiques.
4. La portée plateforme ne donne aucun accès implicite aux données locataires.
5. La RLS bloque toute lecture ou écriture inter-organisation.
6. Une suspension bloque immédiatement l’accès locataire et tout appel Google facturable.
7. Une réactivation ne réactive aucun membre, invitation ou droit terminal.
8. Un rejeu idempotent ne crée ni nouvelle mutation ni nouvel événement d’audit.
9. Les curseurs d’audit et filtres restent côté serveur et ne sont pas persistés dans le navigateur.
10. Les réponses sensibles portent `Cache-Control: no-store`.
11. Google conserve les règles validées : un Text Search, `pageSize=20`, pas de `nextPageToken`, aucun téléphone/site Web.
12. L’attribution Google Maps reste visible et les clés ne sont jamais exposées au client.
13. Aucun export historique n’est disponible.
14. Les capacités sont vérifiées côté serveur, indépendamment du rôle affiché par l’interface.
15. Les tests d’infrastructure obligatoires ne sont jamais ignorés.
16. Toute dérogation est documentée et approuvée avant la décision finale.

## 4. Barrières de validation

### 4.1 Migration et base

Sur une base de test dédiée :

1. appliquer `alembic upgrade head` ;
2. vérifier `alembic current` égal à `20260813_0008 (head)` ;
3. exécuter `alembic check` ;
4. vérifier les rôles propriétaire, migration, Web et RLS ;
5. inspecter les privilèges effectifs (`information_schema` et `pg_policies`) ;
6. exécuter un downgrade contrôlé puis reconstruire jusqu’à `head` ;
7. démarrer l’application avec le rôle Web après reconstruction.

Le downgrade est interdit sur toute base contenant des données utilisateur.

### 4.2 Backend et sécurité

Le passage doit couvrir :

- authentification, CSRF, rotation de session et changement d’organisation ;
- capacités plateforme, administrateur, manager et sales ;
- commit et rollback d’une mutation auditée ;
- refus d’un champ ou d’une métadonnée interdite ;
- pagination `(occurred_at, id)` et limites 50/100 ;
- suspension/réactivation avec version obsolète, transition invalide et rejeu ;
- absence d’appel Google après suspension ;
- isolation RLS sur deux organisations distinctes.

### 4.3 Frontend et accessibilité

Les états suivants sont testés avec Vitest/Testing Library et contrôles axe lorsque disponibles : connexion, invitation,
shell, organisation, membres, historique des invitations, plateforme, suspension, réactivation, erreurs 403/404 et état
mobile. La recette manuelle vérifie clavier, focus, Échap, zoom 200 %, largeur 320 px, contraste et attribution Google.

## 5. Exécution locale reproductible

Un point d’entrée documenté doit :

1. vérifier Docker, Python, Node et les variables nécessaires sans afficher les secrets ;
2. démarrer PostgreSQL, Redis et Mailpit de test avec healthchecks ;
3. appliquer et vérifier les migrations ;
4. lancer Ruff, mypy, pytest avec infrastructure obligatoire ;
5. refuser tout rapport contenant un test ignoré ;
6. lancer ESLint, Vitest et le build ;
7. produire les rapports JUnit et les artefacts utiles ;
8. arrêter uniquement la composition de test utilisée.

Une panne d’environnement doit être distinguée d’un échec produit et consignée séparément.

## 6. Azure Pipelines

Azure doit exécuter les mêmes contrôles sur un agent vierge, avec PostgreSQL, Redis et Mailpit réels ou services
équivalents déclarés. Les variables de secrets sont fournies par le coffre de pipeline ; aucune clé Google réelle n’est
utilisée par les tests. Le pipeline échoue si :

- une migration dérive ;
- un contrôle statique échoue ;
- un test obligatoire est ignoré ;
- un artefact JUnit ou frontend attendu manque ;
- le build frontend échoue.

Le rapport conserve la révision Git, les versions d’outils, les commandes et les éventuelles relances justifiées.

## 7. Documentation attendue

À actualiser :

- spécifications générales et phase 2.4 ;
- guide technique (architecture, migrations, rôles, RLS, audit) ;
- guide utilisateur (organisations, suspension, invitations, audit) ;
- guide d’exploitation (variables, sauvegarde, restauration, healthchecks, rollback) ;
- cahier de recette QA et matrice des preuves ;
- rapport 2.4.5 avec résultats réellement observés.

La documentation doit distinguer les contrôles exécutés localement, ceux exécutés dans Azure et ceux restant à faire.

## 8. Trois critiques obligatoires

1. **Architecture** : cohérence ports/adaptateurs, transaction partagée, absence de dépendance inverse et couverture des
   nouveaux chemins de mutation.
2. **Sécurité et données** : privilèges effectifs, RLS, fuite de données, idempotence, secrets, cache et audit.
3. **Exploitation et produit** : observabilité, reprise après erreur, lisibilité des états, documentation et risque de
   basculer vers 2.5 avec une preuve incomplète.

Chaque critique produit des constats classés bloquant, majeur, mineur ou observation, avec décision de traitement.

## 9. Deux revues de code

- **Revue backend/base** : migrations, SQL, transactions, RLS, capacités et tests négatifs.
- **Revue frontend/CI** : routes, états d’erreur, accessibilité, absence de stockage Web, pipeline et artefacts.

Une revue ne peut être déclarée valide si elle ne cite pas les fichiers examinés, les risques recherchés et les preuves
associées.

## 10. Seize décisions proposées à validation

1. 2.4.5 ne modifie pas les règles métier validées de 2.4.
2. La migration `20260813_0008` doit être appliquée et reconstruite sur base vide.
3. `alembic check` doit être vert avant toute recette fonctionnelle.
4. Les privilèges effectifs et politiques RLS sont vérifiés en base, pas seulement dans le code.
5. Les tests d’infrastructure utilisent PostgreSQL, Redis et Mailpit réels ou explicitement équivalents.
6. Un test d’infrastructure ignoré rend le verrou invalide.
7. Les suites backend et frontend complètes sont exécutées sur la même révision Git.
8. Azure applique les mêmes barrières que le passage local.
9. Les tests Google utilisent des doubles et ne génèrent aucun coût.
10. La recette manuelle couvre plateforme, administrateur, manager, sales et organisation suspendue.
11. Les trois critiques et deux revues sont obligatoires et archivées.
12. Les corrections admises restent limitées à la conformité, la qualité et la non-régression.
13. Toute nouvelle fonctionnalité ou migration supplémentaire sort du périmètre et exige une décision séparée.
14. Les documentations technique, utilisateur et exploitation sont livrées avec le rapport.
15. Le Go/No-Go est décidé après analyse des preuves, jamais sur le seul nombre de tests verts.
16. Aucun travail 2.5 ne commence avant la clôture formelle de 2.4.5.

## 11. Définition de terminé

2.4.5 est terminé uniquement si :

- les seize décisions sont respectées ou leurs dérogations approuvées ;
- la migration, la reconstruction et `alembic check` sont verts ;
- les privilèges et RLS sont prouvés par des contrôles réels ;
- pytest, Ruff, mypy, Vitest, ESLint et le build sont verts ;
- aucun test obligatoire n’est ignoré ;
- la recette manuelle est signée ;
- les trois critiques et deux revues ne contiennent aucun défaut bloquant ;
- les documentations sont à jour ;
- Azure est vert ou un No-Go est documenté avec plan d’action ;
- le responsable produit prononce explicitement le Go pour 2.5.

## 12. Décision de sortie

La sortie produit prend l’une des deux formes suivantes :

- **Go 2.5** : toutes les barrières sont satisfaites et les écarts résiduels sont acceptés et tracés ;
- **No-Go** : au moins une barrière obligatoire échoue, avec défaut, preuve manquante, responsable et prochaine action.

Le rapport final référence les journaux, rapports JUnit, version Git, migration courante et captures manuelles sans
contenir de secret.

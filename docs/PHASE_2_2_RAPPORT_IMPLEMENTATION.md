# Phase 2.2 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Incrément | 2.2 — Identité, mots de passe et sessions |
| Date | 23 juillet 2026 |
| Statut | Implémenté, double revue terminée, validation produit en attente |
| Changement fonctionnel | Écran de connexion et session utilisateur ; recherche Google inchangée |

## 1. Résultat livré

- domaine d’identité indépendant des frameworks : utilisateurs, organisations, appartenances, rôles, états et capacités ;
- normalisation NFKC et IDNA des courriels, sans normalisation ni troncature des mots de passe ;
- tables PostgreSQL `users`, `organizations`, `memberships` et `user_invitations`, contraintes et migration Alembic ;
- bootstrap contrôlé, idempotent et concurrent du premier administrateur de plateforme ;
- mots de passe Argon2id de 12 à 128 caractères ;
- sessions Redis opaques indexées par le condensat d’un jeton aléatoire de 256 bits ;
- expirations d’inactivité et absolue, révocation par utilisateur et invalidation sur changement de version d’identité ;
- limitation des échecs de connexion par couple adresse/courriel et par adresse, avec dimensions pseudonymisées ;
- routes `POST /api/auth/login`, `GET /api/auth/me` et `POST /api/auth/logout` ;
- cookie `HttpOnly`, `SameSite=Lax`, `Secure` et préfixe `__Host-` obligatoires en production ;
- protection CSRF et contrôle strict de l’origine des mutations authentifiées ;
- écran React accessible de connexion, restauration de session et déconnexion ;
- état d’authentification et jeton CSRF conservés uniquement en mémoire ;
- documentation utilisateur, technique et légale actualisée.

La création libre de comptes est absente. Les organisations et membres sont amorcés par la commande d’exploitation ou seront administrés par les fonctions de l’incrément 2.3.

## 2. Critique experte 1 — Sécurité et architecture

### Constats initiaux

1. Deux exécutions concurrentes du bootstrap pouvaient toutes deux observer l’absence d’administrateur.
2. L’auteur d’une appartenance initiale pouvait être nul alors que la traçabilité doit rester explicite.
3. L’organisation active par défaut dépendait d’un nom modifiable.
4. Une charge de session Redis corrompue pouvait provoquer une indisponibilité répétée.

### Corrections appliquées

- verrou transactionnel PostgreSQL par advisory lock autour du bootstrap initial ;
- champ `created_by` obligatoire pour les appartenances ;
- sélection déterministe de l’organisation active par date de création puis identifiant ;
- suppression automatique d’une session Redis illisible, traitée ensuite comme expirée ;
- tests concurrentiels et tests de corruption ajoutés.

### Conclusion de la revue 1

Les invariants d’identité restent dans le domaine et les cas d’utilisation. PostgreSQL, Redis, Argon2id et FastAPI demeurent derrière des ports ou dans les adaptateurs. Le bootstrap ne permet plus de créer deux administrateurs initiaux en concurrence.

## 3. Critique experte 2 — Exploitation et maintenabilité

### Constats initiaux

1. Argon2id, volontairement coûteux, était exécuté directement dans la boucle asynchrone.
2. La création d’une session et de son index utilisateur reposait sur plusieurs commandes Redis séparées.
3. Une erreur Pydantic pouvait renvoyer dans le détail HTTP la valeur brute d’un mot de passe invalide.
4. La variable d’environnement du mot de passe de bootstrap restait accessible plus longtemps que nécessaire.

### Corrections appliquées

- hachage et vérification Argon2id exécutés dans un thread de travail via un port asynchrone ;
- création atomique de la session et de son index au moyen d’un script Lua Redis ;
- gestion dédiée des erreurs de validation des routes d’authentification, sans écho des données soumises ;
- suppression immédiate de la variable du mot de passe après sa lecture par la commande ;
- tests des erreurs, de l’atomicité fonctionnelle et des chemins de session étendus.

### Conclusion de la revue 2

Le coût cryptographique ne bloque plus les autres requêtes, une session ne peut plus être créée sans son index de révocation et les réponses de validation n’exposent pas le secret fourni.

## 4. Contrôles réalisés

| Contrôle | Résultat local |
| --- | --- |
| Migration Alembic | Downgrade jusqu’au socle puis upgrade jusqu’à `head` réussis sur PostgreSQL réel |
| `alembic check` | Aucune opération de migration manquante |
| pytest avec infrastructure obligatoire | 72 réussis, aucun test ignoré |
| mypy strict | Vert, 82 fichiers source |
| Ruff | Vert |
| Ruff format | Vert, 100 fichiers |
| ESLint | Vert, aucune alerte admise |
| Vitest | 6 fichiers, 15 tests réussis |
| Build Vite | Vert |

`git diff --check` est également vert. Les avertissements Git locaux concernent uniquement la conversion future LF/CRLF et ne signalent aucune erreur de contenu.

## 5. Frontière avec l’incrément 2.3

Les éléments suivants sont volontairement différés et ne constituent pas un défaut de 2.2 :

- administration des organisations, membres et rôles ;
- émission et acceptation des invitations à usage unique ;
- changement d’organisation depuis l’interface ;
- politiques PostgreSQL Row-Level Security et séparation des rôles de migration et d’application ;
- protection des routes Google par l’identité authentifiée ;
- retrait du formulaire temporaire d’identité du demandeur dans la recherche.

Cette frontière permet de tester l’authentification avant d’introduire l’autorisation multi-organisation. La recherche Google conserve donc son comportement fonctionnel de phase 1 pendant 2.2.

## 6. Risques résiduels et conditions de déploiement

- le reverse proxy devra fournir une adresse client fiable avant d’utiliser la limitation par adresse en production ;
- les durées juridiques de conservation des comptes et invitations doivent encore être validées ;
- une invitation expirée devra être révoquée transactionnellement avant d’en émettre une nouvelle pour le même couple organisation/courriel ;
- la première exécution Azure Pipelines doit confirmer la reproductibilité de tous les contrôles ;
- aucun déploiement public ne doit précéder la protection authentifiée des routes Google prévue en 2.3.

## 7. Verdict technique

Le verrou final local est entièrement vert : l’incrément 2.2 peut être présenté à la validation produit. Après cette validation, le démarrage de 2.3 est recommandé avec les routes d’organisation et l’isolation RLS avant l’ouverture des appels Google aux comptes authentifiés.

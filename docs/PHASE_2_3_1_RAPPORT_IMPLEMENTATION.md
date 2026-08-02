# Phase 2.3.1 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Incrément | 2.3.1 — Rôle applicatif, contexte et Row-Level Security |
| Date | 23 juillet 2026 |
| Statut | Implémenté, double revue terminée et validation produit locale obtenue |
| Changement visuel | Aucun |

## 1. Résultat livré

- rôle Web fixe `prospect_app`, distinct du propriétaire des migrations ;
- rôle Web connecté mais non superutilisateur, sans création de base ou de rôle, sans `BYPASSRLS` et sans propriété des tables ;
- rôle technique `prospect_rls_definer` sans connexion, propriétaire d’une seule fonction de lecture privilégiée ;
- provisionneur Docker idempotent qui fonctionne aussi sur un volume PostgreSQL déjà initialisé ;
- `TenantContext` interne contenant `actor_id`, `organization_id` et `request_id` ;
- unité de travail locataire qui ouvre une transaction puis utilise `set_config(..., true)` ;
- politiques RLS à refus par défaut sur `organizations`, `memberships` et `user_invitations` ;
- `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY` sur les trois tables ;
- clauses `USING` et `WITH CHECK` empêchant lecture, mise à jour et écriture croisées ;
- droits DML minimaux et absence de droit `DELETE` pour le rôle Web ;
- lecture des appartenances pendant l’authentification par une fonction SQL étroite, sans droit public ;
- PostgreSQL 17.10 et Redis 7.4.9 pour les environnements Compose local, test et CI ;
- cycle Alembic upgrade, downgrade contrôlé, ré-upgrade et détection de dérive dans Azure Pipelines ;
- aucun fichier du frontend modifié.
- commande interactive de récupération du mot de passe plateforme, avec verrou optimiste et invalidation des sessions ;

## 2. Chemin d’exécution

Le serveur construit un `TenantContext` à partir de la session authentifiée. L’unité de travail ouvre ensuite une
transaction et pose les trois paramètres PostgreSQL avec une portée locale. Les dépôts appelés dans cette unité de
travail ne reçoivent jamais un `organization_id` librement soumis par le navigateur.

À la fin de la transaction, commit comme rollback rétablit l’état précédent de la connexion. Les tests imposent un
pool d’une connexion, vérifient le même `pg_backend_pid()` avant et après sa remise au pool et prouvent que les trois
paramètres ne subsistent pas.

L’authentification constitue l’unique exception actuelle sans organisation active. Elle relit les appartenances de
l’acteur courant par `app_private.identity_memberships()`. Cette fonction :

- est `SECURITY DEFINER` avec un `search_path` figé ;
- appartient à un rôle `NOLOGIN` ;
- n’accepte aucun identifiant en argument et utilise seulement `app.actor_id` local à la transaction ;
- expose uniquement l’identifiant, le nom et l’état de l’organisation ainsi que le rôle et l’état de l’appartenance ;
- est révoquée à `PUBLIC` et explicitement accordée à `prospect_app` ;
- ne donne aucun contournement RLS général au rôle Web.

## 3. Migration et privilèges

La révision `20260723_0003` refuse de démarrer si :

- le rôle applicatif ou le rôle technique manque ;
- `prospect_app` est superutilisateur, `BYPASSRLS`, créateur de rôle, créateur de base, `INHERIT` ou `NOLOGIN` ;
- `prospect_app` appartient directement ou indirectement au propriétaire ou à un rôle privilégié ;
- `prospect_app` possède une table locataire ou appartient à son propriétaire.

Les rôles sont créés avant Alembic par le service Compose `database-role-provisioner`. Placé sous un profil d’outil, il
est exécuté explicitement avec `docker compose run --rm database-role-provisioner`, remet les attributs et le mot de
passe local en conformité, puis se termine avec le code zéro. Il ne supprime ni base, ni table, ni volume, ni donnée.
Cette séparation permet à `docker compose up -d --wait` de surveiller uniquement les services persistants et de
retourner un code fiable.

En production, ces deux rôles doivent être provisionnés par l’infrastructure approuvée avant Alembic. Le serveur Web
reçoit seulement `DATABASE_URL`; l’opérateur de migration reçoit séparément `MIGRATION_DATABASE_URL`.

## 4. Critique experte 1 — Sécurité et architecture

### Constats

1. Une RLS stricte aurait rendu invisibles les appartenances nécessaires au login avant la sélection d’une organisation.
2. Le propriétaire d’une table contourne normalement RLS ; séparer seulement les URL sans `FORCE` aurait créé une fausse protection.
3. Une valeur absente ou malformée dans `app.organization_id` pouvait produire soit une erreur, soit un comportement non déterministe.
4. Un rôle `SECURITY DEFINER` trop large aurait simplement déplacé le contournement RLS.
5. Une appartenance indirecte de `prospect_app` à un rôle privilégié aurait annulé ses attributs apparemment sûrs.

### Corrections incorporées

- fonction d’identité sans argument et limitée aux colonnes nécessaires ;
- rôle propriétaire séparé, politiques ciblées sur `prospect_app`, et combinaison `ENABLE` plus `FORCE` ;
- fonctions de contexte qui transforment l’absence, la chaîne vide ou un UUID invalide en `NULL`, donc en refus ;
- rôle technique `NOLOGIN`, `search_path` sûr, droits publics révoqués et seulement deux tables lisibles ;
- contrôle de toute appartenance directe ou indirecte à un rôle superutilisateur ou `BYPASSRLS` avant migration ;
- absence de privilège de suppression physique pour le serveur Web.

### Verdict de la première critique

La barrière protège les erreurs de programmation et les requêtes applicatives croisées sans faire du rôle plateforme
un passe-droit. Le rôle technique privilégié demeure une surface sensible, mais son absence de connexion, sa fonction
unique et ses ACL minimales réduisent son rayon d’impact. Toute nouvelle fonction `SECURITY DEFINER` devra recevoir la
même revue explicite ; aucun droit générique ne doit être ajouté à ce rôle.

## 5. Critique experte 2 — Exploitation et maintenabilité

### Constats

1. Un script placé seulement dans `docker-entrypoint-initdb.d` ne s’exécuterait pas sur le volume local existant.
2. `SET` à portée session pourrait contaminer l’utilisateur suivant après retour d’une connexion au pool.
3. Le passage de 17.5 à 17.10 reste mineur, mais un volume utile ne doit jamais être mis à niveau sans sauvegarde vérifiée.
4. Un downgrade RLS incomplet laisserait des ACL ou fonctions privilégiées orphelines.
5. Le mot de passe local apparaît dans le provisionneur et dans `DATABASE_URL`; une divergence entre les deux provoquerait une panne d’authentification PostgreSQL.
6. Le nom fixe `prospect_app` simplifie des migrations déterministes mais impose un contrat de déploiement.

### Corrections incorporées

- service one-shot idempotent rejoué explicitement sur volume neuf ou existant ;
- `set_config` avec le troisième argument `true`, transaction explicite et tests commit, rollback et réutilisation réelle ;
- versions correctives figées et avertissement de sauvegarde avant la première mise à niveau locale ;
- downgrade qui retire politiques, `FORCE`, `ENABLE`, ACL et schéma privé, puis ré-upgrade testé en CI ;
- une variable `POSTGRES_APP_PASSWORD` documentée et une URL Web distincte dans `.env.example` ;
- rôle SQL fixe documenté comme prérequis d’infrastructure, sans interpolation de nom dans la migration.

### Verdict de la seconde critique

Le chemin local est reproductible et ne dépend pas d’une réinitialisation du volume. Les risques résiduels sont
opérationnels : sauvegarder avant l’upgrade du volume, injecter le même secret aux deux emplacements et créer les rôles
par l’IaC en production. Ils n’autorisent aucun assouplissement vers le propriétaire ou `BYPASSRLS` si une configuration
échoue.

## 6. Contrôles réalisés

| Contrôle | Résultat local |
| --- | --- |
| Images de test | PostgreSQL 17.10 et Redis 7.4.9 sains |
| Provisionnement | service terminé avec code 0 sur base éphémère |
| Alembic | upgrade, downgrade vers `20260723_0002`, ré-upgrade réussis |
| `alembic check` | aucune dérive détectée |
| Tests RLS et infrastructure ciblés | 9 réussis |
| pytest complet avec infrastructure obligatoire | 83 réussis, aucun ignoré |
| mypy strict | vert, 87 fichiers source |
| Ruff et format | verts |
| ESLint | vert, aucune alerte admise |
| Vitest | 6 fichiers et 15 tests réussis |
| Build Vite | vert, 45 modules transformés |
| Validation produit manuelle | connexion, restauration, clé API, Text Search unique, 20 résultats et carte validés |

## 7. Comment tester localement

### 7.1 Tester le rendu actuel avec votre volume de développement

Depuis la racine du projet, sauvegardez d’abord le volume ou la base si elle contient des données utiles. Exécutez
ensuite :

```powershell
$env:POSTGRES_APP_PASSWORD = "prospect-app-development-only"
docker compose up -d --wait
docker compose run --rm database-role-provisioner
docker compose ps -a

$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:5432/prospect"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check

$env:DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-development-only@127.0.0.1:5432/prospect"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000 --env-file .env
```

La commande de provisionnement doit se terminer sans erreur ; le conteneur temporaire est ensuite supprimé.
PostgreSQL et Redis doivent apparaître `healthy` dans `docker compose ps`.
Dans un deuxième terminal :

```powershell
cd client
npm run dev
```

Ouvrez `http://localhost:5173`, connectez-vous avec le compte bootstrap existant et vérifiez :

1. `http://127.0.0.1:8000/api/health/ready` retourne `status: ready` ;
2. la connexion et la déconnexion fonctionnent ;
3. l’écran de recherche est visuellement inchangé ;
4. le rechargement de la page restaure la session attendue.

Il n’existe pas encore d’écran d’organisation dans 2.3.1 : cette livraison est un verrou de base de données.

### 7.2 Exécuter la preuve automatisée isolée

Ces commandes utilisent les ports 55432 et 56379 et une base temporaire indépendante :

```powershell
docker compose -f compose.test.yaml up -d --wait
docker compose -f compose.test.yaml run --rm database-role-provisioner

$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect_test:prospect-test-only@127.0.0.1:55432/prospect_test"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head

$env:TEST_DATABASE_URL = "postgresql+asyncpg://prospect_app:prospect-app-test-only@127.0.0.1:55432/prospect_test"
$env:TEST_MIGRATION_DATABASE_URL = $env:MIGRATION_DATABASE_URL
$env:TEST_REDIS_URL = "redis://127.0.0.1:56379/0"
$env:REQUIRE_INFRASTRUCTURE_TESTS = "true"
.\.venv\Scripts\python.exe -m pytest -q

docker compose -f compose.test.yaml down --volumes
```

Le résultat attendu est 83 tests réussis, sans test ignoré. La dernière commande supprime uniquement les conteneurs et
le stockage temporaire du projet Compose `prospect-crm-test`.

## 8. Frontière avec 2.3.2

2.3.1 ne crée aucune organisation par API, n’émet aucune invitation et n’ajoute aucune route ou page. Le prochain
sous-incrément peut s’appuyer sur le contexte et les politiques livrés pour construire le provisioning et les
invitations sans rouvrir l’isolation en base.

Le verdict technique et produit est favorable. Le compte existant, l’état `ready`, la clé Google, la recherche limitée
à un appel et vingt résultats ainsi que la carte ont été validés localement le 23 juillet 2026. Le démarrage de 2.3.2
est autorisé.

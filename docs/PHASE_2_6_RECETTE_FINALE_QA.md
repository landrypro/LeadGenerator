# Recette finale QA — Phase 2.6 Redis, quotas et observabilité

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Portée | 2.6.1, 2.6.2 et 2.6.3 |
| Environnement prévu | Staging (recette locale volontairement différée) |
| Précondition | PostgreSQL, Redis et Mailpit de test disponibles ; clé Google QA restreinte ou faux fournisseur de test |
| Objectif | Vérifier les protections partagées, les expirations et le verrou qualité sans exposer de secret |

> Ne copiez jamais une clé Google, un cookie de session, un bearer métriques ou un jeton de carte dans le rapport QA.
> Utilisez des comptes et noms de démonstration.

## 1. Préparer l’environnement

1. Depuis PowerShell, ouvrez le dossier du projet.
2. Démarrez les dépendances, ou utilisez le moteur WSL si Docker Desktop Windows est indisponible :

   ```powershell
   docker compose up -d --wait
   docker compose run --rm database-role-provisioner
   ```

3. Vérifiez `http://127.0.0.1:8000/api/health/ready` : PostgreSQL et Redis doivent être `ok`.
4. Appliquez Alembic avec `MIGRATION_DATABASE_URL`, puis vérifiez que `current` affiche `20260815_0013 (head)`.
5. Démarrez deux processus API sur des ports distincts, partageant le même `.env`, PostgreSQL et Redis :

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8001 --env-file .env
   ```

Résultat attendu : les deux APIs sont prêtes. Aucun secret n’apparaît dans la console ou le navigateur.

## 2. Verrou partagé et recherche Google

1. Préparez la même recherche Google sur deux onglets connectés avec le même compte et la même organisation active.
2. Soumettez les deux recherches aussi simultanément que possible.
3. Relevez uniquement les statuts publics.

Résultat attendu : une seule demande est acceptée ; l’autre retourne le message de recherche déjà en cours (`409`).
Une seule requête Text Search est observée dans le faux fournisseur ou la journalisation Google autorisée. La tentative
refusée ne réduit pas le quota.

## 3. Jetons partagés entre deux instances

1. Réalisez une recherche via l’API A (port 8000).
2. Basculez le proxy de développement ou l’URL API vers l’API B (port 8001) sans modifier la session.
3. Ajoutez un établissement sélectionné au CRM ; renseignez un nom interne CRM distinct du nom Google.
4. Demandez l’affichage de la carte depuis l’API B, puis répétez une fois l’opération.

Résultat attendu : l’ajout CRM depuis B fonctionne avec le jeton émis par A. La carte fonctionne une seule fois ; une
seconde tentative est refusée sans appel Maps supplémentaire. Le prospect conserve le `place_id` et le nom interne CRM,
sans détail Google descriptif.

## 4. Quotas QA et refus fermé

> Réservez cette étape à un environnement QA isolé. Réduisez temporairement les limites dans ses variables
> `GOOGLE_SEARCH_USER_DAILY_LIMIT` et `GOOGLE_SEARCH_ORGANIZATION_DAILY_LIMIT`, puis redémarrez les deux APIs.

1. Choisissez des limites QA courtes : utilisateur `2`, organisation `3`, avertissement `50`.
2. Réalisez deux recherches avec le premier membre, puis une troisième.
3. Connectez un second membre dans la même organisation et réalisez une recherche, puis une autre.

Résultat attendu : la troisième recherche du premier membre retourne `429 google_quota_exceeded` avec un
`Retry-After` positif et sans appel Google. La recherche du second membre consomme la dernière unité d’organisation ;
la suivante retourne aussi `429`. Rétablissez ensuite les limites 20/100 ou recréez un Redis QA vide, sans toucher aux
données de développement.

## 5. Expirations Redis

1. En environnement de test seulement, configurez des TTL courts compatibles avec les validations puis redémarrez.
2. Émettez une recherche, attendez l’expiration du jeton de sélection et tentez l’ajout CRM.
3. Émettez une nouvelle recherche, récupérez la carte une fois, puis attendez le TTL restant.

Résultat attendu : le jeton expiré est refusé proprement, sans reconstituer les résultats en mémoire. Les verrous et
jetons expirent automatiquement. Aucun état temporaire ne devient un stockage CRM.

## 6. Métriques privées et journaux

1. En QA/staging, configurez `LOG_FORMAT=json`, `METRICS_ENABLED=true` et un bearer métriques dans le coffre de
   secrets ; redémarrez les APIs.
2. Depuis le collecteur autorisé seulement, appelez `GET /internal/metrics` avec `Authorization: Bearer …`.
3. Tentez ensuite la même route sans bearer depuis un navigateur ou un terminal non autorisé.
4. Inspectez un échantillon de logs JSON après une recherche acceptée et une recherche refusée.

Résultat attendu : le collecteur reçoit les compteurs de verrou/quota/jetons et les durées Redis/Google avec des
labels bornés. L’accès non autorisé retourne `404`. Les logs contiennent `timestamp`, `level`, `event`, `request_id`
et `instance_id`, jamais clé, bearer, courriel, recherche, résultat, `place_id`, adresse ou coordonnées.

## 7. Verrou automatisé et Azure

1. Fermez Vite avant le verrou local, afin de libérer les modules Node verrouillés.
2. Lancez :

   ```powershell
   .\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04" -TestPostgresPort 55433 -TestRedisPort 56380 -TestMailpitSmtpPort 51027 -TestMailpitApiPort 58027
   ```

   Adaptez la distribution si nécessaire. Si les ports de test sont occupés, utilisez les paramètres de ports du
   script, sans supprimer les volumes de développement.
3. Vérifiez `test-results/quality-summary.md`, `pytest-quality.xml`, `vitest.xml` et `alembic-current.txt`.
4. Déclenchez Azure Pipelines sur le même commit et vérifiez l’artefact `MarketteoQualityEvidence`.

Résultat attendu : tous les contrôles sont verts, les deux JUnit ne comportent aucun test ignoré et Alembic est à la
révision attendue. Notez le lien Azure, le commit et le verdict dans le rapport de recette.

## 8. Verdict QA

| Contrôle | Verdict | Preuve / commentaire |
| --- | --- | --- |
| Deux instances, un seul verrou |  |  |
| Jetons carte et sélection inter-instance |  |  |
| Quotas atomiques et `429` |  |  |
| Expirations Redis |  |  |
| Métriques privées et logs sans fuite |  |  |
| Conformité Google phase 1 |  |  |
| Verrou local sans skip |  |  |
| Azure Pipelines vert |  |  |

Un verdict non conforme, une clé dans une preuve, un test ignoré ou une exécution Azure absente est un **No-Go** de
préproduction.

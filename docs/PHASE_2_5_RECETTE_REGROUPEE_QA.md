# Phase 2.5 — Recette regroupée QA 2.5.3 à 2.5.5

## Identification

| Champ | Valeur |
|---|---|
| Date | 15/08/2026 |
| Testeur | Guy Landry  |
| Version / commit | __________ |
| Organisation A / B | __________ / __________ |
| Verdict | GO / NO-GO |

Utiliser uniquement des données fictives. Ne jamais inscrire de mot de passe, clé Google, jeton d’invitation ou donnée
personnelle réelle dans cette feuille.

## Préparation technique

1. Depuis WSL Ubuntu-24.04, démarrer PostgreSQL, Redis et Mailpit avec `docker compose up -d --wait`.
2. Depuis PowerShell, configurer les URL PostgreSQL/Redis, appliquer `alembic upgrade head`, puis vérifier que `current`
   retourne `20260814_0012 (head)`.
3. Vérifier `/api/health/ready` : PostgreSQL et Redis doivent être `ok`.
4. Démarrer backend avec `--env-file .env`, puis frontend avec `npm run dev`.

## Parcours fonctionnel

| ID | Étapes | Résultat attendu | Statut |
|---|---|---|---|
| CRM-01 | Créer un prospect manuellement puis ouvrir sa fiche. | Fiche routable, provenance manuelle, aucune donnée Google copiée. | OK |
| CRM-02 | Ajouter depuis Google, puis répéter le même ajout. | Seul `place_id` persiste ; doublon signalé sans deuxième prospect. | OK |
| CRM-03 | Modifier alias, secteur, ville, priorité et étiquettes. | Version incrémentée ; conflit 409 si une ancienne version est réutilisée. | OK |
| CRM-04 | Ajouter un contact puis des canaux établissement/contact. | Canaux séparés, permission initiale « non déterminée ». | OK |
| CRM-05 | Autoriser un canal avec provenance, puis enregistrer une opposition. | Base/provenance requise ; l’opposition est prioritaire. | OK |
| ISO-01 | Créer le même jeu dans deux organisations puis changer d’organisation. | Aucun prospect, contact, fournisseur ou audit de l’autre organisation n’est visible. | OK |
| SRC-01 | Créer un fournisseur brouillon et tenter une acquisition. | Brouillon signalé non utilisable ; acquisition non conforme mise en quarantaine. | OK |
| SRC-02 | Compléter droits, territoires, finalités et catégories, puis activer. | Fournisseur actif et acquisition compatible approuvée. | OK |
| SRC-03 | Expirer/suspendre le fournisseur et déclarer une nouvelle acquisition. | Nouvelle acquisition quarantinée ; motif contrôlé visible. | OK |
| RET-01 | Créer puis activer une politique. | Une seule politique active par type ; événement d’audit présent. | OK |
| RET-02 | Ajouter un hold sur une ressource, consulter la revue, puis le lever. | Hold actif bloque l’archivage puis la levée est auditée. | OK |
| IMP-01 | Déclarer un import CSV depuis une acquisition approuvée. | Aucun fichier demandé ; statut et motifs affichés. | OK |
| IMP-02 | Annuler puis archiver logiquement une déclaration. | Donnée encore consultable, aucune purge physique. | OK |
| SEC-01 | Rejouer les parcours avec manager et commercial. | Actions absentes ou 403 conformément aux capacités. | OK(reserve)    |
| AUD-01 | Consulter le journal. | Événements présents, sans courriel, téléphone, secret, note sensible ou contenu brut. |  OK(reserve) |
| GOO-01 | Exécuter une recherche Google. | Un Text Search, 20 résultats max, aucun contact, aucune pagination suivie. |  OK(reserve) |
| NAV-01 | Recharger chaque URL, tester clavier, Échap, zoom 200 % et largeur 320 px. | Routes stables, focus visible, dialogues accessibles, aucun blocage horizontal critique. |  OK(reserve) |

## Verrou automatisé

Exécuter depuis PowerShell :

```powershell
.\scripts\Test-QualityGateLocal.ps1 -DockerMode wsl -WslDistribution "Ubuntu-24.04"
```

Joindre `test-results/quality-summary.md`, `pytest-quality.xml`, `vitest.xml` et `alembic-current.txt`, puis joindre le
lien du passage Azure Pipelines sur le même commit.

## Signature

| Rôle | Nom | Décision | Date |
|---|---|---|---|
| QA | Landry | GO (avec reserve) | 25/08/2026 |
| Responsable produit | Guy K | GO  | 25/08/2026 |

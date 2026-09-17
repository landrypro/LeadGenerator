# Phase 3.4-D — Recette et verrou

| Métadonnée | Valeur |
| --- | --- |
| Phase | 3.4 — Opportunités |
| Sous-lot | 3.4-D — Recette et verrou |
| Révision attendue | `20260910_0020 (head)` |
| Prérequis | 3.4-A, B et C implémentés ; verrou local 3.4-C vert |
| Statut | Préparé ; exécution de la recette et clôture soumises à validation produit |

## 1. Objectif

3.4-D ne crée aucune règle métier. Il démontre que le domaine, la persistance, l’API et l’interface des opportunités
fonctionnent ensemble sur PostgreSQL réel, sans régression de 3.1 à 3.3. La sortie exige des preuves reproductibles,
aucun `skip` et un verrou qualité global vert.

## 2. Livrables obligatoires

1. reconstruction Alembic réelle jusqu’à `20260910_0020` et contrôle d’absence de dérive ;
2. recette [`RECETTE_FONCTIONNELLE_3_4_OPPORTUNITES.md`](RECETTE_FONCTIONNELLE_3_4_OPPORTUNITES.md) renseignée ;
3. manuel utilisateur mis à jour pour les opportunités et leur indépendance du pipeline ;
4. rapport [`PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md`](PHASE_3_4_D_RAPPORT_IMPLEMENTATION.md) complété avec les preuves ;
5. régression ciblée 3.1 CSV, 3.2 Kanban et 3.3 activités/tâches ;
6. verrou global produisant `pytest-quality.xml`, `vitest.xml`, `alembic-current.txt` et `quality-summary.md`.

## 3. Reconstruction PostgreSQL réelle

Le verrou doit démarrer une composition isolée, appliquer `upgrade head`, revenir à `20260723_0002`, puis reconstruire
jusqu’à la tête. Sont interdits : `stamp`, modification manuelle d’`alembic_version` et réemploi d’une base déjà
préparée comme seule preuve. `current` doit retourner exactement `20260910_0020 (head)` et `alembic check` ne doit
détecter aucune opération.

## 4. Matrice de recette

La recette couvre : décimaux exacts et devises séparées ; échéances et retards ; étapes ouvertes, gain, perte et
réouverture ; concurrence optimiste et idempotence ; Administrateur, Gestionnaire, Commercial propriétaire et
Commercial non propriétaire ; isolation entre deux organisations ; événements de chronologie, synthèses et alignement
pipeline explicite. Les résultats Google ne doivent jamais préremplir les opportunités.

## 5. Régression 3.1 à 3.3

- **3.1** : aperçu CSV temporaire, mapping et confirmation restent fonctionnels ;
- **3.2** : neuf colonnes, transitions contrôlées, perte/réouverture et chargement additionnel restent conformes ;
- **3.3** : note, activité déclarative, chronologie unifiée, tâche, prochaine action, rappel, accusé et report restent
  conformes ;
- les contrôles reportés `AUD-01`, `SEC-01`, `TASK-02`, `TASK-05`, `TASK-06`, `PERM-01`, `ISO-01` et `SEC-3.3`
  demeurent suivis pour la recette finale 3.6 s’ils ne sont pas soldés ici.

## 6. Verrou global et verdict

Commande de référence :

```powershell
.\scripts\Test-QualityGateLocal.ps1 `
  -DockerMode wsl `
  -WslDistribution "Ubuntu-24.04" `
  -TestPostgresPort 55433 `
  -TestRedisPort 56380 `
  -TestMailpitSmtpPort 51027 `
  -TestMailpitApiPort 58027 `
  -QualityTempRoot "D:\MarketteoQualityTemp"
```

Le verdict est vert uniquement si migrations, Ruff, format Ruff, mypy, pytest réel, zéro skip backend, audit npm,
ESLint, Vitest/axe, zéro skip frontend, build Vite, sources navigateur, artefact et diff Git réussissent. Un avertissement
LF/CRLF n’est pas un échec ; un test ignoré, une migration dérivante ou une dépendance réelle inaccessible bloque la
clôture.

## 7. Critères de sortie

- chaque scénario porte `OK`, `ÉCHEC` ou `REPORTÉ` avec motif et preuve ;
- aucun scénario reporté n’est compté comme validé ;
- aucune anomalie critique ou majeure ne reste ouverte ;
- le rapport d’implémentation contient les compteurs exacts et les chemins des artefacts ;
- le responsable produit donne son GO de clôture après lecture du verdict.

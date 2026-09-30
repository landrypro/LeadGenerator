# Recette fonctionnelle — Phase 4.6

## Cadre

| Élément | Valeur |
|---|---|
| Produit | Marketteo CRM |
| Identifiant de campagne | `P4.6-20260925-R1` |
| État | Recette locale : E2E-01 à E2E-12 validés ; verrou qualité final VERT le 30 septembre 2026. Le GO de clôture locale est reçu ; le pipeline Azure doit publier ses preuves sur le commit de clôture. |
| Référence de qualité | verrou local vert du 30 septembre 2026, tête Alembic `20260929_0030`, 345 pytest, 216 Vitest et 44 parcours Axe |
| Registre d'exécution | [RECETTE_PHASE4.6_REGISTRE.csv](RECETTE_PHASE4.6_REGISTRE.csv) |
| Spécification source | [PHASE_4_6_SPECIFICATIONS_DETAILLEES.md](PHASE_4_6_SPECIFICATIONS_DETAILLEES.md) |

Cette recette couvre les parcours réalisables en environnement local avec des données synthétiques. Aucun mot de passe, jeton, donnée réelle de prospect ou appel au service Meta n'est nécessaire.

## Préconditions

1. Démarrer PostgreSQL, Redis et Mailpit selon la procédure locale, puis l'API et le client web.
2. Vérifier `GET http://localhost:8000/api/health/live` et `GET http://localhost:8000/api/health/ready` avec un statut HTTP 200.
3. Créer deux organisations de test, `ORG-A` et `ORG-B`, et les comptes synthétiques décrits dans le registre CSV.
4. Utiliser uniquement les fournisseurs simulés, les jeux CSV de test et les données créées pendant la recette.
5. Relever l'identifiant de révision et l'heure de démarrage de la campagne dans le registre.

## Jeu de données

| Référence | Contenu prévu | Usage |
|---|---|---|
| `ORG-A` | Organisation française, fuseau `America/Toronto` | Parcours principaux et contrôles d'isolation |
| `ORG-B` | Organisation anglaise, fuseau `UTC` | Vérification d'étanchéité inter organisation |
| `A-MANAGER` / `A-SALES-1` | Comptes synthétiques avec rôles distincts | Autorisations, pipeline, activités et tâches |
| `CSV-01` | `P4_6_IMPORT_VALID.csv` (2 lignes valides) et `P4_6_IMPORT_QUARANTAINE.csv` (courriel invalide, nom absent) | Import, déduplication, rapport de quarantaine et reprise |
| `EXPORT-01` | Jeu `prospects` issu de E2E-02/E2E-03, portée `organization` ou `self` selon capacité | Export asynchrone privé, idempotence, téléchargement et étanchéité ORG-B |
| `META-SIM-01` | Événement Meta simulé, identifiant déterministe | Connecteur pilote, webhook et idempotence |
| `USAGE-01` | Appels Google simulés et quota de test | Rapport d'usage et comportement au quota |
| `PURGE-01` | Données marquées pour purge de fin de recette | Nettoyage contrôlé |

Le détail exploitable des données, préconditions, attentes et résultats est tenu dans le registre CSV. Les mots de passe sont créés localement au moment de la recette et ne sont pas consignés.

## Parcours exécutables

| Référence | Parcours | Preuve attendue | État initial |
|---|---|---|---|
| `E2E-01` | Connexion puis bascule entre `ORG-A` et `ORG-B` | Capture de l'organisation active et réponse API bornée à son tenant | PASS — validé le 26 septembre 2026 |
| `E2E-02` | Création d'un prospect, activité, tâche et opportunité | Identifiants créés, timeline et pipeline cohérents | PASS — validé le 27 septembre 2026 |
| `E2E-03` | Import du jeu `CSV-01` | Compteurs de succès, rejeu idempotent et erreur de ligne invalide | PASS — validé le 30 septembre 2026 |
| `E2E-04` | Demande d'export et traitement par worker | Fichier privé, compteurs rapprochés, téléchargement refusé depuis ORG-B | PASS — validé le 27 septembre 2026 |
| `E2E-05` | Interruption contrôlée d'un worker puis reprise | État de reprise et absence de doublon | PASS — validé le 28 septembre 2026 |
| `E2E-06` | Google simulé, quota et relevé d'usage | Ligne d'usage agrégée et tenant correct | PASS — validé le 28 septembre 2026 par parcours de services Docker |
| `E2E-07` | Quota atteint puis indisponibilité réelle et réversible | Erreur métier compréhensible, aucune fuite entre tenants | PASS — `429` quota, deux `503` fermés et reprise validés le 30 septembre 2026 |
| `E2E-08` | Connecteur Meta simulé : fournisseur, liaison et webhook | Prospect associé à `ORG-A`, état de liaison visible | PASS — validé le 29 septembre 2026 |
| `E2E-09` | Rejeu du webhook puis révocation simulée | Idempotence et arrêt de la liaison | PASS — validé le 29 septembre 2026 |
| `E2E-10` | Rôles et isolation multi organisation | Accès autorisé ou refusé conformément au rôle | PASS — validé le 29 septembre 2026 |
| `E2E-11-AUTO` | Accessibilité automatisée sur les routes Phase 4 | Rapport Axe : 44 parcours conformes | PASS — verrou du 25 septembre 2026 |
| `E2E-11-MANUAL` | Clavier, zoom 200 %, libellés bilingues, états vides et erreurs | Capture ou note de vérification par page | PASS — validé le 30 septembre 2026 |
| `E2E-12` | Purge des données synthétiques de recette | Compteurs avant et après purge, confirmation d'absence | PASS — validé le 29 septembre 2026 |

## Procédure d'exécution

1. Dupliquer les références de données du registre dans l'environnement local et renseigner l'exécutant.
2. Jouer les parcours dans l'ordre ci-dessus. Pour chaque parcours, consigner le résultat observé, les identifiants non sensibles, le lien vers la preuve et l'état `PASS`, `FAIL`, `BLOCKED` ou `NOT_RUN` dans le CSV.
3. En cas d'anomalie, conserver l'horodatage, le rôle, l'organisation active, la réponse masquée et les étapes de reproduction. Ne pas joindre de cookie, mot de passe, jeton ou contenu de prospect réel.
4. Jouer `E2E-12` après l'ensemble des vérifications afin de retirer les données synthétiques créées.
5. Si le code, les migrations ou les dépendances de test changent, relancer le verrou qualité complet avant de conclure la recette.

## Scripts de recette préparés

Chaque script affiche un marqueur `E2E-xx_SCRIPT=PASS` et place sa preuve dans `test-results`. Ce marqueur valide la
partie automatisée décrite ci-dessous. Le registre reste à `NOT RUN` tant que le parcours fonctionnel et les preuves
attendues par le scénario ne sont pas rapprochés.

| Ordre | Commande PowerShell | Contenu du script |
|---|---|---|
| 1 | `./scripts/Test-E2E03CsvReplay.ps1` | Contrôle les deux fixtures CSV, le mapping, l'idempotence, la quarantaine et la rétention. Il ne rejoue pas l'import dans l'interface : conserver le rapport `CSV-VALID-REPLAY` affichant deux doublons pour clôturer E2E-03. |
| 2 | `./scripts/Test-E2E07QuotaResilience.ps1` | Vérifie la réservation de quota, le refus avant appel fournisseur et la fermeture de l'API en cas d'indisponibilité. Les dépendances externes ne sont jamais appelées. |
| 3 | `./scripts/Set-E2E08MetaSimulation.ps1 -WslDistribution Ubuntu-24.04`, puis `./scripts/Invoke-E2E08SimulatedWebhook.ps1 -FormId <formulaire>` et `./scripts/Test-E2E08MetaPilot.ps1` | Injecte des valeurs synthétiques locales dans l'API et le worker, active un simulateur local de lead et envoie un webhook signé sans appeler Meta. Le test contrôle ensuite le format du webhook, la signature, la liste blanche de champs, l'authentification et le CSRF. |
| 4 | `./scripts/Test-E2E09MetaWebhookReplay.ps1 -WslDistribution Ubuntu-24.04` | Lance le verrou qualité dans une base PostgreSQL temporaire avec rôles `app` et `worker`, puis vérifie signature Meta, admission HTTP et rejeu durable des jobs. Il prépare la preuve technique ; effectuer encore le rejeu fonctionnel dix fois et la révocation du binding avant de conclure E2E-09. |
| 5 | `./scripts/Test-E2E10TenantIsolation.ps1 -WslDistribution Ubuntu-24.04` | Lance la même infrastructure isolée puis contrôle RLS réel : contexte absent, accès entre organisations, mutations refusées et nettoyage du contexte de connexion. |
| 6 | `./scripts/Test-E2E12PurgePreflight.ps1 -WslDistribution Ubuntu-24.04` | Vérifie les contrats de rétention et compte les candidats synthétiques `P4-ALPHA*` et `QA-P46-*` présents dans le runtime. Le script ne supprime aucune donnée ; l'exécution d'une purge demeure une action finale distincte. |
| 7 | `./scripts/Invoke-E2E12ArchiveCandidates.ps1 -Mode Preview` | Liste les candidats avec leur organisation, version et compteurs de cascade, sans ouvrir de session API ni modifier de donnée. Le mode `Execute -ConfirmPurge` exige une confirmation textuelle, archive chaque candidat par l'API, puis impose un compteur final à zéro. |

Les scripts E2E-09 et E2E-10 utilisent les ports `56432`, `56380`, `51027` et `58027` pour ne pas gêner le runtime local.

## Résultats des exécutions du 25 au 29 septembre 2026

| Contrôle | Résultat | Preuve |
|---|---|---|
| Disponibilité API | PASS — `live` et `ready` répondent HTTP 200 ; PostgreSQL et Redis sont prêts. | Sondes locales consignées dans le registre |
| Parcours navigateur Axe | PASS — 44 parcours, 22 routes en `fr-CA` et 22 en `en-CA`, zéro violation. | `test-results/phase-4-6/browser-axe-recette.json` |
| Tests de domaine et contrats Phase 4 | PASS — 49 tests, zéro échec, zéro skip. | `test-results/phase-4-6/pytest-recette-unit.xml` |
| Tests de workflow API | PASS — 18 tests, zéro échec, zéro skip. | `test-results/phase-4-6/pytest-recette-api.xml` |
| Verrou complet avec dépendances réelles | PASS — 345 pytest, 216 Vitest, 44 parcours Axe, audit npm sans vulnérabilité et build Vite verts, sans skip. | `test-results/pytest-quality.xml`, `test-results/vitest.xml` et `test-results/phase-4-6/browser-axe.json` |
| Navigation interactive Codex | BLOCKED_TOOL — le composant d'automatisation native du navigateur n'a pas pu s'initialiser après deux tentatives, dont une après réinitialisation. | Erreur d'initialisation de l'outil navigateur |

Les résultats automatisés couvrent les contrats et les invariants des parcours. Ils ne prouvent pas les actions visuelles avec une session utilisateur ouverte ni les scénarios de reprise impliquant deux workers réels. Ces points restent `NOT RUN` ou `BLOCKED` dans le registre, avec la prochaine action indiquée.

| Référence | Résultat de cette exécution | Suite requise |
|---|---|---|
| `E2E-01` | PASS — vues Dashboard française et anglaise contrôlées, organisation active visible dans chaque vue, état vide cohérent. | Aucune pour ce parcours. |
| `E2E-02` | PASS — prospect `P4-ALPHA-2`, activité, tâche `TASK-001`, pipeline `Qualification` et opportunité `OPP-E2E` clôturée `Gagnée` à 100 %. | Aucune pour ce parcours. |
| `E2E-03` | PASS — premier lot : 2 créations ; rejeu confirmé : 0 création et 2 doublons exacts ; lot de quarantaine : 2 lignes rejetées. Prospects et historique rapprochés. | Aucune. Conserver les preuves assainies et les identifiants des lots. |
| `E2E-04` | PASS — exports `bb8d92dc-2803-46fe-b891-43586d6db56a` et `282eea94-0d7f-4401-a5ee-ffc81c7b29e9` téléchargés, colonnes allowlistées et isolation ORG-B validée. | Aucune pour ce parcours. |
| `E2E-05` | PASS — reprise worker validée avec une seconde tentative et un seul artefact. | Aucune pour ce parcours. |
| `E2E-06` | PASS — simulateur Google et agrégats de quota validés dans les deux portées par parcours de services Docker. | Aucune pour ce parcours. |
| `E2E-07` | PASS — 28 tests ciblés passés ; en navigateur, limite synthétique atteinte en HTTP `429 google_quota_exceeded` (portée `user`), verrou réel du registre durable ayant produit HTTP `503 usage_tracking_unavailable`, puis pause Redis ayant produit HTTP `503 authentication_unavailable` et un message explicite dans l'interface. Redis et PostgreSQL sont redevenus sains, `/api/health` indique le mode Google `live`, et Usage affiche de nouveau le quota courant (organisation : 12/100). | Aucune pour ce parcours. Le verrou qualité final du 30 septembre est vert. |
| `E2E-08` | PASS — fournisseur, acquisition, contrat, binding approuvé, webhook signé et traitement worker validés. Une ingestion, un job, un prospect, un contact et une provenance ont été rapprochés ; deux canaux et deux permissions `allowed` ont été créés. | Aucune pour E2E-08. Conserver les données synthétiques jusqu'à E2E-12. |
| `E2E-09` | PASS — contrat Meta signé, rejeu durable des jobs PostgreSQL, reconstructions Alembic et révocation contrôlés dans l'infrastructure isolée. | Aucune pour E2E-09. Conserver les preuves jusqu'à E2E-12. |
| `E2E-10` | PASS — 4 tests RLS PostgreSQL passés : contexte absent, lecture croisée, mutation inter organisation, réutilisation de connexion et rôles SQL. | Aucune pour E2E-10. Conserver les preuves jusqu'à E2E-12. |
| `E2E-11-AUTO` | PASS — Axe sur 44 parcours. | Aucune. |
| `E2E-11-MANUAL` | PASS — les quatre passages manuels sont validés : pages FR/EN, clavier et focus, petit écran et zoom à 200 %, état vide et erreur réversible. | [Fiche E2E-11](RECETTE_PHASE4.6_INTERACTIVE.md#fiche-de-test-détaillée--e2e-11-manual) et captures assainies de la recette du 30 septembre 2026. |
| `E2E-12` | PASS — prévol de 11 tests, 2 candidats synthétiques archivés via l'API, puis compteur final à 0. Les deux réponses indiquent 0 contact et 0 canal à archiver. | Aucune pour E2E-12. Conserver le rapport JUnit, les identifiants fictifs et les journaux du worker. |

## Fiche de test détaillée — E2E-12

### Prévol exécuté

Le prévol couvre les règles de rétention, l'archivage en cascade et les contrôles de droits. Il ne supprime aucune
donnée. La commande jouée depuis PowerShell est :

```powershell
.\scripts\Test-E2E12PurgePreflight.ps1 -WslDistribution Ubuntu-24.04
```

La suite ciblée a produit `11 passed` en `9.78 s`, avec le rapport
`test-results/phase-4-6/scripted/e2e-12.xml` (`tests=11`, `failures=0`, `errors=0`, `skipped=0`).

La version initiale du script a ensuite échoué lors du comptage SQL des candidats, car PowerShell interprétait
`count(*)` dans la commande WSL. Cette étape ne lance aucune suppression. Le script corrigé a confirmé
`E2E12_PURGE=READY candidates=2`.

### Exécution de purge du 29 septembre 2026

L'archivage a été lancé après affichage et confirmation des deux candidats. Les résultats observés sont :

| Candidat synthétique | Version avant → après | Contacts archivés | Canaux archivés |
|---|---:|---:|---:|
| `0cad33e8-95ee-44ff-a790-8c01c35b76f9` (`P4-ALPHA`) | 8 → 9 | 0 | 0 |
| `c5aa96eb-0886-4457-aa6d-ed054ed9f0fb` (`P4-ALPHA-2`) | 2 → 3 | 0 | 0 |

La sortie finale est `E2E12_PURGE=PASS candidates_before=2 candidates_after=0`. L'archivage est logique et produit
un événement d'audit ; aucune suppression SQL directe n'a été exécutée.

### Verdict

**E2E-12 — PASS.** Les 11 contrôles de rétention sont verts. Les deux candidats synthétiques ont été archivés via
l'API après confirmation explicite, avec un compteur final de `0`. Aucun contact ni canal actif ne leur était rattaché.

### Étapes de purge finale

1. **Geler la recette.** Ne plus créer de prospect, d'import, d'export ou de webhook synthétique. Conserver l'API,
   PostgreSQL et le worker démarrés.
2. **Lister les candidats sans modifier la base.** Utiliser la requête de prévol avec les colonnes `id`,
   `internal_alias`, `organization_id`, `version` et les compteurs de contacts/canaux actifs. Les deux lignes doivent
   porter un alias `P4-ALPHA*` ou `QA-P46-*` et appartenir à l'organisation attendue. Exporter uniquement ces
   identifiants fictifs dans la preuve. La commande préparée est
   `./scripts/Invoke-E2E12ArchiveCandidates.ps1 -Mode Preview`.
3. **Valider la liste.** Vérifier manuellement les deux alias et les versions retournées. En cas de troisième ligne,
   d'organisation inattendue ou de version différente, arrêter la procédure et relancer le prévol.
4. **Archiver via l'API authentifiée.** Exécuter
   `./scripts/Invoke-E2E12ArchiveCandidates.ps1 -Mode Execute -ExpectedCandidateCount 2 -ConfirmPurge`.
   Le script demande le compte local ayant `prospects:archive`, contrôle le CSRF, bascule vers l'organisation du
   candidat si nécessaire et archive une ligne à la fois avec le motif `no_longer_relevant`. Cette commande est
   logique, journalisée et archive en cascade les contacts et canaux ; ne pas exécuter d'`UPDATE` ou de `DELETE`
   direct sur les tables métier. L'API est jointe sur le port `8000` et l'origine autorisée par défaut est le client
   Vite sur `http://localhost:5173`. Si votre client utilise une autre origine déclarée dans
   `CORS_ALLOWED_ORIGINS`, ajouter `-Origin http://<hôte>:<port>` à la commande.

5. **Contrôler la cascade.** Pour chaque réponse, relever seulement `prospect_id`, la nouvelle `version`,
   `contacts_archived` et `channels_archived`. Une réponse HTTP `200` est attendue pour chaque candidat.
6. **Rapprocher après archivage.** Rejouer `Test-E2E12PurgePreflight.ps1` : le compteur doit être `candidates=0`.
   Vérifier aussi qu'aucun contact ni canal actif ne reste rattaché aux deux prospects et que deux événements d'audit
   `prospect.archived` sont visibles pour l'organisation.
7. **Laisser le worker appliquer les purges échues.** Redémarrer le worker si nécessaire avec
   `docker compose --profile runtime restart worker`, puis relever les journaux `usage_retention_purged` et les
   nettoyages d'artefacts. Ces fonctions ne suppriment que les jobs, artefacts, événements d'usage et références
   d'ingestion arrivés à échéance ; les métadonnées d'audit restent conservées.
8. **Clôturer la preuve.** Conserver le rapport JUnit, le compteur initial `2`, le compteur final `0`, les deux
   réponses d'archivage masquées et les journaux du worker. Le registre E2E-12 est `PASS` lorsque tous les contrôles
   attendus sont rapprochés.

## Critères d'acceptation

- Tous les parcours P0 et P1 réalisables sont à `PASS`, sans anomalie P0 ouverte.
- Les données de `ORG-A` ne sont jamais visibles, exportables ni modifiables depuis `ORG-B`.
- Les échecs de quota, d'import, de worker et de webhook sont traçables, compréhensibles et ne produisent pas de doublon.
- La recette manuelle d'accessibilité est documentée pour les zones visuelles qui ne peuvent pas être conclues par Axe seul.
- La purge de fin de campagne ne laisse aucune donnée synthétique de recette.

## Hors périmètre exécutable localement

`META-EXT-01`, la validation avec un vrai compte Meta Lead Ads, reste bloqué jusqu'à l'autorisation externe et à la revue préalable prévues par la Phase 4.5. Il est enregistré dans le CSV comme `BLOCKED_EXTERNAL`; il ne doit pas être interprété comme un échec de la recette locale.

## Fiche de test détaillée — E2E-08

### Objectif et périmètre

Vérifier le pilote Meta Lead Ads en environnement local avec des secrets et des données synthétiques : fournisseur actif,
acquisition approuvée, contrat et binding approuvés par un réviseur distinct, admission d'un webhook signé, traitement
asynchrone par le worker et création des enregistrements CRM autorisés. Aucun appel à l'API Meta réelle n'est effectué.

| Élément | Valeur de recette |
|---|---|
| Organisation | `ORG-A` — environnement local de recette |
| Fournisseur | `MetaSimulé` |
| Référence d'acquisition | `MetaSimulé01` |
| Formulaire simulé | `E2E08-FORM-002 2` |
| Lead simulé | `E2E08-LEAD-006` |
| Champs autorisés | Nom complet, courriel, téléphone |
| Données retournées par le simulateur | `Lead Meta Simulé`, courriel synthétique, téléphone synthétique |
| Appel Meta externe | 0 — simulateur local activé |

### Déroulé et résultats

| Étape | Contrôle | Résultat observé |
|---|---|---|
| 1 | Activation de la simulation locale avec `Set-E2E08MetaSimulation.ps1` | `E2E08_META_SIMULATION=READY enabled=true simulator=true secrets=synthetic` |
| 2 | Création et approbation du fournisseur, de l'acquisition et du contrat | Fournisseur actif, acquisition approuvée et liaison Meta disponible dans **Connexions** |
| 3 | Approbation du binding et création du brouillon | Binding approuvé, puis état `approved` après revue ; aucun secret Meta réel affiché |
| 4 | Envoi du webhook signé | `E2E08_WEBHOOK=PASS status=200` |
| 5 | Admission et idempotence de l'ingestion | Une ingestion créée, statut final `succeeded`, une tentative |
| 6 | Traitement worker | Un job créé, statut final `succeeded`, une tentative, résultat `imported` |
| 7 | Création CRM et provenance | Un prospect, un contact et une provenance créés ; nom du prospect et du contact : `Lead Meta Simulé` |
| 8 | Canaux et permissions | Deux canaux créés et deux permissions associées, toutes deux à l'état `allowed` |
| 9 | Contrats automatisés | `Test-E2E08MetaPilot.ps1` : 4 tests passés ; rapport `test-results/phase-4-6/scripted/e2e-08.xml` |

### Rapprochement technique

| Objet | Identifiant ou valeur rapprochée |
|---|---|
| Ingestion | `ae541201-cc64-4cc2-94ba-c933b887ee43` |
| Job | `f46756d9-27ea-4277-a605-adc36d0e3f97` |
| Prospect | `e32f4004-835f-4a0e-8705-263b1db4cfa4` |
| Contact | `f486d17a-c484-4391-9526-2b647c6f572e` |
| Provenance | `d1dcd341-3b0f-4f59-993a-559cdc27070d` |
| Résultat d'ingestion | `imported` |
| Tentatives ingestion/job | `1 / 1` |
| Canaux / permissions | `2 / 2`, permissions `allowed` |

### Anomalie rencontrée et correction

Le premier traitement worker échouait sur la contrainte unique des permissions de contact : le déclencheur PostgreSQL
créait déjà une permission `unknown`, puis le pilote tentait d'en insérer une seconde. La migration `20260929_0030`
ajoute une transition sécurisée de la permission créée par le déclencheur. Après reconstruction des conteneurs et
application de la migration, le traitement direct sous le rôle `prospect_worker` puis le webhook complet ont réussi au
premier essai.

### Verdict

**E2E-08 — PASS.** Le parcours local est validé : admission signée, traitement asynchrone, création CRM et permissions
conformes. La validation avec un compte Meta réel reste hors périmètre et ne fait pas partie de ce verdict.

## Fiche de test détaillée — E2E-09

### Objectif et périmètre

Vérifier que le webhook Meta signé est admis dans une file PostgreSQL durable, qu'un rejeu ne crée pas de doublon,
que les jobs reprennent correctement après reconstruction de la base et que la révocation du binding ferme les
admissions ultérieures. Le scénario s'exécute dans une composition isolée avec les rôles PostgreSQL `prospect_app` et
`prospect_worker`, Redis et Mailpit.

| Élément | Valeur de recette |
|---|---|
| Scénario | `E2E-09 — Contrat Meta signé et rejeu durable des jobs dans PostgreSQL isolé` |
| Distribution | `Ubuntu-24.04` via WSL |
| Services | PostgreSQL, Redis et Mailpit isolés, tous sains |
| Révision finale | `20260929_0030 (head)` |
| Tests du script | `6 passed` |
| Rapport | `test-results/pytest-quality.xml` |

### Contrôles exécutés

| Contrôle | Résultat observé |
|---|---|
| Provisionnement des rôles | Rôles applicatif et worker créés, droits et rôles accordés |
| Migration initiale | Reconstruction complète depuis la base vide jusqu'à `20260929_0030` |
| Downgrade/re-upgrade | Downgrade contrôlé puis remontée jusqu'à `20260929_0030` sans erreur |
| Cohérence Alembic | `No new upgrade operations detected` |
| Contrat webhook | Signature et admission Meta contrôlées dans l'infrastructure isolée |
| File durable | Rejeu des jobs PostgreSQL contrôlé avec le worker et les transitions terminales |
| Révocation | Binding désactivé/révoqué puis nouvelle admission refusée conformément au scénario |
| Verrou qualité | `Verrou qualité local : VERT` |
| Frontend et navigateur | 213 tests frontend passés, 44 parcours navigateur contrôlés, axe PASS |

### Preuve automatisée

La commande exécutée est :

```powershell
.\scripts\Test-E2E09MetaWebhookReplay.ps1 -WslDistribution Ubuntu-24.04
```

Sortie de synthèse :

```text
E2E-09_SCRIPT=PASS tests=6 rapport=C:\Users\Admin\OneDrive\Family Room\Documents\LeadGenerator\test-results\pytest-quality.xml
```

### Verdict

**E2E-09 — PASS.** Le rejeu durable, l'absence de doublon, les transitions du worker et la fermeture après révocation
sont validés dans l'infrastructure PostgreSQL isolée. Aucun appel Meta réel n'est utilisé.

## Fiche de test détaillée — E2E-10

### Objectif et périmètre

Vérifier l'isolation multi organisation au niveau PostgreSQL avec RLS, les droits des rôles applicatifs et worker,
l'absence de contexte locataire, les lectures croisées interdites, les mutations inter organisation refusées et la
réinitialisation correcte du contexte lors de la réutilisation d'une connexion.

| Élément | Valeur de recette |
|---|---|
| Scénario | `E2E-10 — Rôles PostgreSQL et isolation multi-organisation dans une base temporaire` |
| Suite ciblée | `tests.integration.test_tenant_rls` |
| Infrastructure | PostgreSQL, Redis et Mailpit isolés dans WSL `Ubuntu-24.04` |
| Tests du script | `4 passed` |
| Révision finale | `20260929_0030 (head)` |
| Rapport | `test-results/pytest-quality.xml` |

### Contrôles exécutés

| Contrôle | Résultat observé |
|---|---|
| Contexte locataire absent | Accès refusé ou vide conformément aux règles RLS |
| Lecture inter organisation | Les données d'une autre organisation ne sont pas visibles |
| Mutation inter organisation | Les écritures ciblant un autre tenant sont refusées |
| Réutilisation de connexion | Le contexte du tenant précédent n'est pas conservé sur une nouvelle opération |
| Rôles SQL | Les rôles applicatif et worker disposent uniquement des droits prévus |
| Verrou qualité | `Verrou qualité local : VERT` |

### Preuve automatisée

La commande exécutée est :

```powershell
.\scripts\Test-E2E10TenantIsolation.ps1 -WslDistribution Ubuntu-24.04
```

Sortie de synthèse :

```text
E2E-10_SCRIPT=PASS tests=4 rapport=C:\Users\Admin\OneDrive\Family Room\Documents\LeadGenerator\test-results\pytest-quality.xml
```

### Verdict

**E2E-10 — PASS.** L'isolation RLS, les refus inter organisation, les droits des rôles PostgreSQL et la remise à zéro
du contexte de connexion sont validés dans une base temporaire. Aucun accès entre tenants n'a été observé.

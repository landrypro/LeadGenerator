# Protocole et registre des preuves — Étape 4 Automatisation

> **Version :** `PV-AUT-4.1`  
> **Statut :** scénarios et oracles spécifiés ; preuves isolées S4-0 et S4-1 produites ; S4-2, S4-3, S4-4, S4-5 et S4-6 clôturées pour définition ; S4-7 active sous réserves ; Porte 4 `GO avec réserves` pour `P4-Lite` ; activation non validée.  
> **Backlog lié :** [BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md).  
> **Principe :** une preuve prévue n’est jamais présentée comme une preuve obtenue.

## 1. Niveaux de preuve

| Niveau | Sens | Utilisable à la Porte 4 |
|---|---|---|
| `D0 — Décision` | Règle et portée approuvées dans RF-AUT-2.1 | Oui comme contrat, pas comme preuve d’exécution. |
| `D1 — Spécification` | Scénario, données, oracle et artefact définis | Oui pour juger la préparation. |
| `D2 — Exécutable` | Test ou procédure disponible sur environnement isolé | Oui pour autoriser une tranche ciblée. |
| `D3 — Exécutée` | Résultat daté, versionné et reproductible | Oui comme preuve technique. |
| `D4 — Observée` | Résultat confirmé en staging ou pilote contrôlé | Requis avant production ou élargissement. |

Tous les scénarios du présent document sont au niveau **D1**, sauf les preuves historiques du socle citées dans T1 et
la preuve D3 locale, synthétique et explicitement bornée d’IMP-A6 documentée ci-dessous. Aucun résultat D4,
staging ou activation Automation n’est revendiqué.

### Exception contrôlée — artefacts statiques S4-0

La réalisation de S4-0 a produit une preuve **D2 artefact statique** distincte, sans exécution serveur :

| Preuve | Artefact | Résultat | Limite |
|---|---|---|---|
| `S4-0-D2-STATIC` | [`fixtures/s4-0/manifest.json`](./fixtures/s4-0/manifest.json) + [`validate_manifest.py`](./fixtures/s4-0/validate_manifest.py) | PASS — 2 organisations, 3 prospects synthétiques, flags désactivés, principal borné, RLS/rollback déclarés, métriques sans PII | Ne prouve ni RLS réel, ni migration réelle, ni worker, ni effet CRM |

Cette exception ne requalifie pas les scénarios runtime `PV-*` en D2. Les preuves serveur, d’intégration et d’observation
restent à produire avant la Porte 4.

### Exception contrôlée — noyau runtime isolé S4-1

La réalisation du domaine déterministe a produit une preuve exécutable locale, sans base, worker ou fournisseur externe :

| Preuve | Artefact | Résultat | Limite |
|---|---|---|---|
| `S4-1-DOMAIN-RT` | [`backend/app/domain/automation.py`](../../backend/app/domain/automation.py) + [`tests/test_automation_deterministic.py`](../../tests/test_automation_deterministic.py) | PASS — 8 tests couvrant versions, priorité du Feu, `to_verify`, Prévol, expiration et invalidation | Ne prouve ni API, ni RLS, ni persistance, ni worker, ni effet CRM |

Cette preuve est utilisable pour valider le noyau pur, mais ne requalifie pas les contrats d’intégration `PV-RULE-*` en
preuves serveur complètes.

### Définition contrôlée — tranche S4-2

La définition clôturée de [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md), contre-validée dans
[CONTRE-VALIDATION-S4-2](./CONTRE_VALIDATION_S4_2.md), fournit des
scénarios et oracles de niveau **D1** pour l’admission canonique, la tâche interne, l’idempotence, la double garde, le
Passeport et les exceptions. Aucun test serveur n’est revendiqué et aucun prospect ou tâche réel n’a été créé.

### Définition contrôlée — tranche S4-3

La définition clôturée de [S4-3 — Assistant IA encadré](./S4_3_ASSISTANT_IA_ENCADRE.md), documentée dans
[CONTRE-VALIDATION-S4-3](./CONTRE_VALIDATION_S4_3.md), fournit des scénarios et oracles de niveau **D1** pour le schéma
d’intention, l’absence d’outil, la minimisation des données, le repli, les quotas et la série adversariale
`AI-ADV-01..10`. Les prescriptions CV-S4-3-01 à CV-S4-3-07 sont appliquées au niveau contractuel. Aucun fournisseur,
prompt persistant, appel de modèle, outil CRM ni route IA ne sont revendiqués.

### Définition contrôlée — tranche S4-4

La [définition S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md), documentée
dans [CONTRE-VALIDATION-S4-4](./CONTRE_VALIDATION_S4_4.md), pose les oracles D1 PV-FUN-04, PV-APP-01..03,
PV-CONC-01..02, PV-AUD-02 et PV-OPS-02. Les prescriptions CV-S4-4-01 à CV-S4-4-07 sont appliquées au niveau
contractuel. Aucune approbation, persistance de brouillon, route, worker ou communication externe n’est revendiquée.

### Définition clôturée — tranche S4-5

La [définition S4-5 — Playbooks complémentaires et exceptions](./S4_5_PLAYBOOKS_COMPLEMENTAIRES_EXCEPTIONS.md) pose
les oracles D1 PV-FUN-05..06, PV-EXC-01..04, PV-RULE-05, PV-SEC-05 et PV-OBS-05. Les prescriptions
CV-S4-5-01..07 sont appliquées au niveau contractuel ; le verdict est consigné dans
[CONTRE-VALIDATION-S4-5](./CONTRE_VALIDATION_S4_5.md). Les preuves D2/D3 restent à produire ; aucun Playbook
complémentaire, traitement d'exception, worker, route ou effet CRM réel n'est revendiqué.

### Définition clôturée — tranche S4-6

La définition [S4-6 — Preuves, résilience et préparation de la Porte 4](./S4_6_PREUVES_RESILIENCE_PORTE_4.md) fixe
les fixtures, les niveaux D1-D4, les oracles de charge, sécurité, IA, observabilité, panne et rollback. Les
prescriptions CV-S4-6-01..07 sont appliquées au niveau contractuel ; le verdict figure dans
[CONTRE-VALIDATION-S4-6](./CONTRE_VALIDATION_S4_6.md). Elle reste au niveau D1 ; aucune preuve D2/D3 ni exécution
Automation n'est revendiquée.

### Préparation confirmée — IMP-A6

Le [dossier IMP-A6](./IMP_A6_PREPARATION.md) confirme le cadre d'exécution des preuves D3 : Docker/WSL local,
fixtures synthétiques, pannes injectées uniquement en test, rollback ordonné sur base jetable et rapports minimisés
sous `test-results/automation-imp-a6/`. Ce cadre produit une preuve D3 seulement après son exécution complète ; il ne
revendique jamais de D4, de staging ou d'activation Automation.

L'implémentation du 4 octobre 2026 ajoute la migration `20261004_0035`, le manifeste `fixtures/imp-a6/manifest.json`,
la procédure `IMP_A6_ROLLBACK.md`, les tests de résilience/audit/Assistant et la production contrôlée de
`test-results/automation-imp-a6/evidence.json`. Le verrou qualité complet est vert : 381 tests backend, 218 tests
frontend et 44 parcours navigateur/axe passés, sans test ignoré. L'artefact D3 est daté, minimisé, synthétique et
reproductible ; il couvre la migration `20261004_0035`, le rollback/reconstruction et les scénarios IMP-A6. Sa
portée n'autorise ni D4, ni staging, ni activation. La revue Produit/QA/Sécurité est consignée dans la décision
`GO avec réserves` de Porte 4.

## 2. Règles de conservation des preuves

Chaque artefact doit indiquer : version du code, schéma, Playbook, règles, configuration, environnement, données
synthétiques, horodatage, résultat et réserve. Les phrases libres, secrets, courriels, téléphones, brouillons et données
personnelles sont interdits dans les rapports.

Convention proposée :

`test-results/automation/<version>/<preuve-id>/`.

La convention est préparatoire : aucun répertoire ni artefact d’exécution n’est créé pendant cette étape documentaire.

## 3. Jeux de données synthétiques

| Fixture | Contenu | Scénarios servis |
|---|---|---|
| `ORG-ALPHA` | Administrateur, gestionnaire, deux commerciaux actifs, un membre inactif | Capacités, attribution, révocation. |
| `ORG-BETA` | Même identifiant externe qu’Alpha, utilisateurs distincts | Isolation multi-tenant. |
| `PROSPECT-NOUVEAU` | Provenance manuelle, courriel inconnu, aucun responsable | Nouveau prospect, Feu Jaune. |
| `PROSPECT-VERT` | Permission documentée, responsable actif, données complètes | Prévol Vert sans envoi. |
| `PROSPECT-OPPOSITION` | Opposition explicite au canal | Feu Rouge non dérogeable. |
| `DOUBLON-EXACT` | Même clé externe et même organisation | Idempotence et rattachement. |
| `DOUBLON-AMBIGU` | Deux fiches plausibles sans clé forte | Quarantaine. |
| `PROPOSITION-SILENCIEUSE` | Étape ouverte, dernière activité > délai | Playbook Proposition en attente. |
| `OCCASION-INACTIVE` | Opportunité ouverte sans activité ni échéance | Playbook Occasion oubliée. |
| `NOTE-INJECTION` | Note CRM demandant de contourner permissions et Feu | IA adversariale. |

## 4. Matrice fonctionnelle

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-FUN-01` | Nouveau prospect admissible | Une seule tâche préparée, responsable actif, aucun envoi | État CRM + audit corrélé | D1 |
| `PV-FUN-02` | Ouvrir le Passeport | Origine, permission, responsable et prochaine action proviennent du CRM canonique | Capture structurée + requêtes | D1 |
| `PV-FUN-03` | Doublon exact puis ambigu | Exact rattaché ; ambigu quarantainé ; aucune fusion silencieuse | Rapport de cas + compteurs | D1 |
| `PV-FUN-04` | Brouillon externe | Brouillon visible, zéro appel de connecteur | Audit + compteur fournisseur nul | D1 |
| `PV-FUN-05` | Proposition silencieuse | Suivi proposé, pipeline inchangé | Diff CRM avant/après | D1 |
| `PV-FUN-06` | Occasion oubliée | Revue humaine, aucune fermeture automatique | Diff opportunité + audit | D1 |

## 5. Règles, Feu et Prévol

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-RULE-01` | Construire le contexte d’évaluation | Tenant, acteur, canal, objet, version et snapshot présents | Contexte sérialisé sans PII | D1 |
| `PV-RULE-02` | Vert, Jaune, Rouge et inconnu | Rouge prioritaire ; inconnu jamais Vert | Table de décision exécutée | D1 |
| `PV-RULE-03` | Comparer Prévol/exécution | Même règle et même version, différences expliquées | Rapport de fidélité | D1 |
| `PV-RULE-04` | Modifier une donnée après Prévol | Prévol déclaré obsolète, nouvelle évaluation exigée | Événement d’invalidation | D1 |

## 6. Sécurité, tenant et capacités

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-SEC-01` | Chaque rôle appelle chaque commande | Matrice T3 appliquée, refus fermé | Rapport par rôle/capability | D1 |
| `PV-SEC-02` | Faux `system_origin` ou portée excessive | Admission refusée et auditée | Test négatif + audit | D1 |
| `PV-SEC-03` | Droit révoqué après Prévol | Aucun effet CRM ; exception explicite | État CRM inchangé | D1 |
| `PV-SEC-04` | Accès Alpha vers Beta | Zéro donnée, zéro différence d’existence | Tests RLS/API | D1 |
| `PV-SEC-05` | Rouge approuvé par un manager | Refus serveur non dérogeable | Réponse normalisée + audit | D1 |

## 7. Idempotence, concurrence et résilience

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-IDEM-01` | Même clé, même commande | Même exécution retournée, aucun doublon | Identifiants et compteurs | D1 |
| `PV-IDEM-02` | Timeout après effet potentiel | Aucun retry aveugle, statut `to_verify` | Trace de panne injectée | D1 |
| `PV-IDEM-03` | Même clé, charge différente | Conflit d’idempotence | Réponse et audit | D1 |
| `PV-CONC-01` | Deux approbations concurrentes | Une transition gagnante, autre obsolète | Versions et événements | D1 |
| `PV-CONC-02` | Suspension pendant un lot | Aucun nouvel effet après génération d’arrêt | Chronologie corrélée | D1 |
| `PV-EXC-04` | Réconciliation d’un état incertain | Résolution unique, auditée et rejouable | Rapport de réconciliation | D1 |

## 8. IA, données et UX

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-AI-01` | Sortie conforme au schéma | Intention typée, aucun champ d’effet | Validation JSON/schema | D1 |
| `PV-AI-02` | Demande d’écriture directe | Aucun outil ni commande CRM disponible | Test d’interface du port IA | D1 |
| `PV-AI-03` | Phrase contenant une donnée sensible | Donnée minimisée, non journalisée | Inspection logs/audit | D1 |
| `PV-AI-04` | Timeout, quota ou réponse hors schéma | Repli guidé, aucun effet | Parcours de repli | D1 |
| `PV-AI-05` | Dépassement de budget organisation | Appel refusé avant fournisseur | Compteur et refus | D1 |
| `PV-AI-06` | Série `AI-ADV-01..10` | Toutes les injections rejetées ou clarifiées | Rapport adversarial | D1 |
| `PV-UX-01` | Expliquer le Feu | Motif et prochaine action compréhensibles | Scénario d’acceptation | D1 |
| `PV-UX-02` | Phrase → plan → Prévol | Périmètre et absence d’effet visibles avant préparation | Parcours instrumenté | D1 |

## 9. Approbations, audit et exploitation

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-APP-01` | Approuver un brouillon | Lien complet contenu/destinataire/canal/version | Enregistrement minimal | D1 |
| `PV-APP-02` | Modifier après approbation | Approbation invalidée | Événement d’invalidation | D1 |
| `PV-APP-03` | Brouillon expiré | Action impossible | Réponse + audit | D1 |
| `PV-AUD-01` | Traquer une exécution | Décision reconstruisible sans phrase libre | Chronologie d’audit | D1 |
| `PV-AUD-02` | Refus ou approbation | Identité, portée, version et raison minimale | Audit sans contenu sensible | D1 |
| `PV-OPS-01` | Désactiver un flag | Parcours caché/refusé côté serveur | Configuration + test API | D1 |
| `PV-OPS-02` | Suspension générationnelle | Aucun effet après arrêt | Chronologie worker | D1 |
| `PV-OPS-03` | Rollback et réconciliation | Retour à un état sûr et explicable | Procédure répétée | D1 |

## 10. Données, observabilité et capacité

| ID | Scénario | Oracle | Artefact attendu | Niveau |
|---|---|---|---|---|
| `PV-DATA-01` | Migration puis rollback | Schéma cohérent, aucune perte d’objet CRM | Rapports Alembic/SQL | D1 |
| `PV-DATA-02` | Activer puis modifier une version | Version active immuable, nouvelle version distincte | État des versions | D1 |
| `PV-DATA-03` | Charger les fixtures | Deux tenants isolés et cas limites reproductibles | Manifest de fixtures | D1 |
| `PV-OBS-01` | Inspecter métriques/logs | Cardinalité bornée, aucune PII | Export de labels | D1 |
| `PV-OBS-02` | Déclencher blocage et exception | Dashboard et alerte reflètent l’état | Capture métrique/alerte | D1 |
| `PV-CAP-01` | Exécuter `T4-CAP-01..05` | Seuils mesurés, saturation refusée sans perte | Rapport de charge | D1 |
| `PV-QA-01` | Couverture P0/P1 | Chaque item a positif, négatif, tenant et rejeu pertinents | Matrice de couverture | D1 |
| `PV-GOV-01` | Assembler Porte 4 | Preuves et réserves indexées par tranche | Dossier de décision | D1 |

## 11. Seuils d’acceptation proposés

| Dimension | Seuil Porte 4 proposé |
|---|---|
| Isolement | 0 accès ou effet inter-organisation. |
| Effet externe autonome | 0 envoi et 0 connecteur d’envoi actif. |
| Doublon | 0 tâche, prospect, brouillon ou approbation dupliqué sur rejeu. |
| Rouge | 0 dérogation, y compris administrateur. |
| État incertain | 100 % vers `to_verify` ou réconciliation idempotente. |
| Prévol | 100 % des décisions portent la même version de règle que l’exécution planifiée. |
| IA | 0 chemin d’écriture ; 100 % des sorties validées par schéma. |
| Données sensibles | 0 phrase libre ou secret dans logs, métriques et audit. |
| Capacité | `S95 ≤ 3 s` et `Smax ≤ 9 s` restent des cibles à confirmer, pas des résultats acquis. |

## 12. Matrice de traçabilité fonctionnelle

| Contrat V2.1 | Backlog | Preuves |
|---|---|---|
| Point d’entrée IA unique | `AUT-4301..06` | `PV-AI-*`, `PV-UX-02` |
| Feu relationnel | `AUT-4102..06` | `PV-RULE-*`, `PV-UX-01` |
| Prévol fidèle | `AUT-4104`, `AUT-4106` | `PV-RULE-03..04` |
| Nouveau prospect | `AUT-4201..06` | `PV-FUN-01..03`, `PV-IDEM-*` |
| Proposition en attente | `AUT-4501` | `PV-FUN-05` |
| Occasion oubliée | `AUT-4502` | `PV-FUN-06` |
| Brouillon et approbation | `AUT-4401..06` | `PV-APP-*`, `PV-FUN-04` |
| Exceptions | `AUT-4503..06` | `PV-EXC-*`, `PV-SEC-03` |
| Aucun envoi externe | Toutes tranches | `PV-FUN-04`, seuil 0 envoi |
| Traçabilité et arrêt | `AUT-4002`, `AUT-4006..07`, `AUT-4605..06` | `PV-AUD-*`, `PV-OPS-*`, `PV-OBS-*` |

## 13. Statut des preuves

| Catégorie | Spécifiées D1 | Exécutables D2 | Exécutées D3 | Observées D4 |
|---|---:|---:|---:|---:|
| Fonctionnel et règles | Oui | 0 | 0 | 0 |
| Sécurité et tenant | Oui | 0 | 0 | 0 |
| Idempotence et résilience | Oui | 0 | 0 | 0 |
| IA et UX | Oui | 0 | 0 | 0 |
| Audit, données et opérations | Oui | 0 | 0 | 0 |
| Capacité | Oui | 0 | 0 | 0 |

La Porte 4 devra décider quelles preuves D2/D3 sont nécessaires avant d’autoriser chaque tranche de construction. Le
présent registre rend cette décision vérifiable, mais ne remplace pas les résultats futurs.

## 14. Registre S4-7 — preuves à produire pour la réouverture

La phase [S4-7 — Levée des réserves et réouverture de la Porte 4](./S4_7_LEVEE_RESERVES_PORTE_4.md), complétée par les
[propositions de réouverture](./PROPOSITIONS_PORTE_4_REOUVERTURE.md), suit les réserves du `GO avec réserves` sans
requalifier les preuves D1 existantes. Les identifiants attendus sont :

| Preuve | Objectif | Niveau cible | État initial |
|---|---|---|---|
| `PV-S47-GOV-01` | Owners, capacité, estimations et dépendances | D2 | À produire |
| `PV-S47-ENV-01` | Environnement isolé réinitialisable | D2 | À produire |
| `PV-S47-RUN-01` | Feu, Prévol, garde et idempotence | D3 | À produire |
| `PV-S47-RUN-02` | Exceptions et états `to_verify` | D3 | À produire |
| `PV-S47-RES-01` | Suspension, reprise et rollback | D3 | À produire |
| `PV-S47-AI-01` | OpenAI, fake, quotas et rétention | D2 | Fake et limites locales IMP-A5 confirmés ; quotas/rétention OpenAI à confirmer |
| `PV-S47-OBS-01` | Audit, télémétrie et registre des risques | D2 | À produire |
| `PV-S47-GATE-01` | Dossier et verdict de réouverture Porte 4 | D1/D2 | À assembler |

Tant que ces preuves ne sont pas produites, l'activation et l'élargissement de `P4-Lite` restent interdits. Une réserve
critique non traitée suspend la tranche concernée, même si le `GO avec réserves` autorise la préparation.

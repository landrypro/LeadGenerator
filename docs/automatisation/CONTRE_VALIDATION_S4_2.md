# Contre-validation S4-2 — Nouveau prospect et tâche interne

> **Verdict : `GO sous prescriptions` — définition S4-2 clôturée**  
> **Décision à la date de la contre-validation :** construction intégrée, effets CRM, worker, API et migration non autorisés. Cette conclusion D1 est remplacée, pour le seul périmètre `P4-Lite`, par le `GO avec réserves` consigné dans le [dossier Porte 4](./PORTE_4_PRET_A_CONSTRUIRE.md).  
> **Date :** 1er octobre 2026

## 1. Objet de la contre-validation

Cette revue vérifie que la définition de S4-2 est cohérente avec :

- la référence fonctionnelle `RF-AUT-2.1` ;
- le noyau S4-1 et son Prévol ;
- les objets canoniques du CRM des Phases 1 à 4 ;
- les décisions T1 à T4 de l’Étape 3 ;
- le backlog et le protocole de preuves de l’Étape 4.

Elle vérifie la qualité de la définition, pas l’exécution dans le produit. Aucun prospect, aucune tâche, aucun événement
réel et aucune migration n’ont été créés par cette revue.

## 2. Artefacts contrôlés

- [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ;
- [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ;
- [Référence fonctionnelle `RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) ;
- [Backlog `BL-AUT-4.1`](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [Registre des preuves `PV-AUT-4.1`](./PREUVES_VALIDATION_ETAPE_4.md) ;
- [Contrôle final Étapes 1 à 4 / Phases 1 à 4](./CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md) ;
- [Spécification CRM V1](../SPECIFICATION_CRM_V1.md).

## 3. Résumé du verdict

La définition est suffisamment précise pour servir de contrat de préparation. Elle respecte le périmètre Lite : un seul
Playbook, une prochaine action interne, aucune communication autonome et aucun registre métier parallèle.

Les prescriptions sont maintenant appliquées au niveau contractuel et documentaire. Le `GO` reste limité à la définition
parce que les preuves d’exécution restent au niveau D1 et doivent être produites après la Porte 4.

## 4. Matrice de contre-validation

| Contrôle | Résultat | Conclusion |
|---|---|---|
| Déclencheur après création canonique | **Conforme** | L’admission intervient après la réussite de l’écriture CRM ; rejet, doublon et quarantaine ne redéclenchent pas le Playbook. |
| Indépendance vis-à-vis des sources | **Conforme sous preuve** | Manuel, Google, CSV, Meta conditionnel et Web/API partagent le même contrat ; LinkedIn reste différé. |
| Réutilisation du CRM | **Conforme** | Prospect, tâche, membre, audit et Passeport restent canoniques ; aucun second CRM n’est introduit. |
| Tâche interne sans contact | **Conforme — contrat séparé appliqué** | La tâche ne dépend pas d’une permission courriel/téléphone ; `InternalTaskEligibility` est séparé du Feu relationnel. |
| Feu par canal | **Conforme** | Le Feu de contact reste affiché séparément et ne devient pas une autorisation générale. |
| Responsable actif | **Conforme** | Inactif ou absent mène à une exception ; aucune attribution aléatoire. |
| Idempotence | **Conforme au niveau définition** | Clé fonctionnelle, empreinte, conflit et rejeu sont spécifiés ; preuve serveur encore à produire. |
| Résultat incertain | **Conforme** | Timeout après effet potentiel mène à `to_verify` et à une recherche par clé avant tout rejeu. |
| Garde avant effet | **Conforme au niveau contrat** | Tenant, capacité, version, suspension et snapshot sont revérifiés ; exécution serveur non prouvée. |
| Doublon exact / ambigu | **Conforme** | Rattachement exact ou quarantaine ; aucune fusion silencieuse. |
| Passeport | **Conforme** | Origine, responsable, prochaine action, Prévol et historique sont lisibles depuis les données canoniques. |
| Audit et télémétrie | **Conforme sous preuve** | Corrélation et minimisation sont définies ; rapport d’exécution à produire. |
| IA et sources sociales | **Conforme** | Aucune IA réelle ni connecteur social obligatoire n’est requis pour S4-2. |
| Compatibilité Phases 1 à 4 | **Conforme** | Les patrons d’idempotence, de capacité, de tenant et de tâche existants sont réutilisés. |

## 5. Prescriptions appliquées au niveau contractuel

Les prescriptions `CV-S4-2-01` à `CV-S4-2-07` sont fermées dans la définition, les contrats, les séquences et les
oracles. Elles ne sont pas encore des preuves runtime : leur exécution D2/D3 reste une condition d’intégration.

### `CV-S4-2-01` — Contrat d’éligibilité interne distinct

La définition distingue explicitement :

- l’éligibilité d’une tâche interne ;
- le Feu relationnel d’un contact externe.

Une permission courriel `unknown` ou absente ne doit pas bloquer une tâche interne autorisée. Elle doit uniquement empêcher
ou mettre en vérification une action de contact. Le code d’intégration ne doit pas détourner une couleur relationnelle pour
représenter un droit CRM interne.

**Preuve runtime restante :** `PV-FUN-01` et `PV-QA-07` avec permission externe inconnue et tâche interne acceptée.

### `CV-S4-2-02` — Atomicité de l’admission

L’admission `ProspectCanonicalAdmitted` est définie avec l’admission Automation et un job PostgreSQL idempotent, écrits
dans la même transaction que l’écriture canonique réussie. Aucun outbox générique n’est introduit ; le job ne devient
réclamable qu’après le commit et reste corrélé à l’admission.

**Preuve runtime restante :** aucun événement pour un rejet, un doublon ou une quarantaine ; reprise sans perte après redémarrage.

### `CV-S4-2-03` — Garde finale serveur

La garde juste avant la création de tâche doit relire côté serveur :

- l’organisation et l’appartenance ;
- la capacité CRM et la capacité Automation ;
- l’état actif du membre responsable ;
- les flags et la suspension ;
- la version du Playbook et du ruleset ;
- le Prévol et son empreinte CRM ;
- la clé d’idempotence et l’empreinte de commande.

Une révocation ou une divergence gagne toujours sur le Prévol précédent.

**Preuve runtime restante :** `PV-SEC-03` avec révocation entre Prévol et effet.

### `CV-S4-2-04` — Idempotence et effet ambigu

Une même clé et une même empreinte doivent retourner le résultat existant ou l’état en cours. Une même clé avec une charge
différente doit produire un conflit sans seconde tâche. Un timeout après écriture potentielle doit déclencher une recherche
par clé/corrélation et non une nouvelle création automatique.

**Preuves runtime restantes :** `PV-IDEM-01` et `PV-IDEM-02`.

### `CV-S4-2-05` — Déduplication et rattachement

Le rattachement exact doit conserver le prospect existant et ne pas redéclencher Nouveau prospect. Une correspondance
ambiguë doit rester en quarantaine et ne créer aucune tâche. Toute fusion requiert une décision humaine explicitement
auditée par le CRM.

**Preuve runtime restante :** `PV-FUN-03` sur deux organisations et deux candidats ambigus.

### `CV-S4-2-06` — Responsable et exception

L’absence ou l’inactivité du responsable ne doit jamais entraîner de transfert aléatoire. L’interface doit proposer un
membre actif autorisé, un report ou une résolution d’exception. Le Feu relationnel ne doit pas être modifié pour masquer
cette indisponibilité.

**Preuve runtime restante :** `PV-EXC-01` avec responsable désactivé entre admission et garde.

### `CV-S4-2-07` — Minimisation de l’audit

Les événements et métriques doivent conserver la décision, la version, la corrélation et le motif minimal sans phrase
libre, secret, brouillon, destinataire ou charge sociale brute.

**Preuve runtime restante :** `PV-OBS-01` et inspection des journaux sur données synthétiques.

## 6. Compatibilité avec le socle

| Élément du socle | Vérification | Statut |
|---|---|---|
| Création prospect manuel | Réutilisable comme point d’admission canonique | Conforme à confirmer en intégration |
| Création Google par `place_id` | Réutilisable ; pas de copie du descriptif Google | Conforme à confirmer en intégration |
| Import CSV | Déclenchement après confirmation et par ligne admise | Conforme à confirmer en intégration |
| Tâche CRM | `ProspectTaskDraft` et `CreateTaskUseCase` comportent déjà responsable, échéance et idempotence | Réutilisation obligatoire |
| Organisation/tenant | `TenantContext` et isolation existants | Garde Automation à ajouter sans contourner le socle |
| File durable | Bail, corrélation et rejouabilité existants | Ne pas réutiliser un retry aveugle pour une tâche ambiguë |
| Audit | Événements d’audit du CRM disponibles | Ajouter le contrat Automation minimal, sans PII excessive |
| Meta/Facebook | Pilote conditionnel, preuves de provenance requises | Hors dépendance du premier parcours |
| LinkedIn | Connecteur non livré | Hors périmètre S4-2 |

## 7. Scénarios de preuve contre-validés

| ID | Scénario | Oracle | État de preuve |
|---|---|---|---|
| `PV-FUN-01` | Prospect admissible, responsable actif | Une seule tâche interne, prochaine action explicite, aucun contact externe | D1 défini |
| `PV-FUN-02` | Ouverture du Passeport | Données issues des objets canoniques et historique corrélé | D1 défini |
| `PV-FUN-03` | Doublon exact puis ambigu | Rattachement exact, quarantaine ambiguë, zéro fusion silencieuse | D1 défini |
| `PV-IDEM-01` | Rejeu identique | Même résultat, zéro doublon | D1 défini |
| `PV-IDEM-02` | Timeout après effet potentiel | `to_verify`, recherche par clé avant toute reprise | D1 défini |
| `PV-SEC-03` | Révocation entre Prévol et effet | Refus fermé, audit corrélé, aucune tâche nouvelle | D1 défini |
| `PV-EXC-01` | Responsable inactif | Exception ouverte, choix humain ou report | D1 défini |
| `PV-OBS-01` | Audit et télémétrie | Pas de phrase libre, secret ou PII inutile | D1 défini |

Les scénarios sont prêts pour une exécution D2/D3, mais ne doivent pas être présentés comme exécutés avant la disponibilité
de PostgreSQL, Redis, du worker de test et des fixtures d’intégration.

## 8. Risques résiduels

| Risque | Niveau | Condition de levée |
|---|---|---|
| Confusion Feu externe / tâche interne | Élevé | Contrat appliqué ; test sentinelle runtime restant |
| Travail réclamé avant commit CRM | Élevé | Admission + job transactionnels arrêtés ; preuve transactionnelle restante |
| Double tâche après timeout | Élevé | Recherche idempotente définie ; test de panne restant |
| Réattribution d’un membre inactif | Élevé | Garde finale définie ; preuve d’exception restante |
| Fuite inter-tenant | Élevé | Tests RLS et deux organisations à produire |
| Source Meta non prouvée | Moyen | Binding et provenance à vérifier en intégration |
| Données sensibles dans les traces | Moyen | Inspection télémétrie à produire |

## 9. Décision

La contre-validation donne un **GO sous prescriptions** à la définition de S4-2 et confirme sa clôture documentaire. La
tranche est suffisamment cadrée pour entrer dans le dossier de préparation de la Porte 4.

Elle ne donne pas l’autorisation de :

- créer une route ou un événement actif ;
- brancher le worker ;
- modifier ou migrer la base client ;
- créer un prospect ou une tâche réelle ;
- appeler une IA ou un connecteur externe ;
- ouvrir la production ou les sessions PME.

Le `NO-GO` d’intégration reste en vigueur jusqu’à la disponibilité de l’environnement de preuve, l’exécution D2/D3 et le
verdict explicite de Porte 4.

## 10. Suite recommandée

1. conserver les prescriptions `CV-S4-2-01` à `CV-S4-2-07` comme conditions d’intégration ;
2. préparer les fixtures multi-tenant et les pannes idempotentes ;
3. produire les preuves D2/D3 sur l’environnement isolé après la Porte 4 ;
4. n’ouvrir l’intégration S4-2 qu’après un verdict de construction explicitement limité.

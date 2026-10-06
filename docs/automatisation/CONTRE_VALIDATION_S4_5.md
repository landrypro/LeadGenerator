# Contre-validation S4-5 — Playbooks complémentaires et exceptions

> **Verdict : prescriptions appliquées — S4-5 clôturée pour définition**  
> **Runtime, intégration, worker, persistance, connecteurs, pipeline et communication : NO-GO**  
> **Date :** 1er octobre 2026  
> **Portée :** contre-validation documentaire D1 ; aucune exécution sur données client.

## 1. Objet et décision

Cette contre-validation vérifie que la définition de [S4-5 — Playbooks complémentaires et exceptions](./S4_5_PLAYBOOKS_COMPLEMENTAIRES_EXCEPTIONS.md) est cohérente avec la référence fonctionnelle V2.1, le noyau déterministe de S4-1, le parcours Nouveau prospect de S4-2 et les brouillons, approbations et cycles de vie de S4-4.

Les prescriptions CV-S4-5-01 à CV-S4-5-07 sont appliquées au niveau contractuel et documentaire, ce qui clôture
S4-5 pour sa définition. Cette décision ne prononce pas la Porte 4 : aucun Playbook n'est activé, aucune exception
n'est résolue automatiquement et aucun effet CRM ou externe n'est autorisé.

## 2. Artefacts contrôlés

- [S4-5 — Playbooks complémentaires et exceptions](./S4_5_PLAYBOOKS_COMPLEMENTAIRES_EXCEPTIONS.md) ;
- [référence fonctionnelle RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) ;
- [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ;
- [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ;
- [S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md) ;
- [backlog détaillé de l'Étape 4](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [protocole et registre des preuves](./PREUVES_VALIDATION_ETAPE_4.md) ;
- [spécification CRM V1](../SPECIFICATION_CRM_V1.md).

## 3. Résultat synthétique

| Domaine contrôlé | Résultat | Observation |
|---|---|---|
| Proposition en attente | Conforme sous prescription | Détection bornée, opportunité canonique, attente et activité prouvées. |
| Occasion oubliée | Conforme sous prescription | Revue humaine uniquement ; aucune fermeture ou relance implicite. |
| Prévol et Feu | Conforme | Réutilisation du noyau S4-1 et garde fraîche avant tout effet futur. |
| Responsable indisponible | Conforme | Pas de réattribution aléatoire ; résolution explicite. |
| Correspondance ambiguë | Conforme | Quarantaine ; aucune fusion ni création. |
| Prospect déjà connu | Conforme | Rattachement canonique ; pas de doublon. |
| Résultat to_verify | Conforme | Réconciliation par clé/corrélation ; pas de retry aveugle. |
| Cycles, suspension, expiration | Conforme sous prescription | Une suspension ou invalidation gagne sur toute proposition antérieure. |
| Audit et télémétrie | Conforme sous prescription | Événements minimisés, sans phrase sensible ni brouillon inutile. |
| Porte 4 et runtime | Non autorisé | La définition est clôturée, la construction reste bloquée. |

## 4. Matrice de contre-validation

| ID | Point vérifié | Critère attendu | Verdict |
|---|---|---|---|
| CV-S4-5-C01 | Déclencheurs canoniques | Organisation, Playbook, version, opportunité et fenêtre résolus côté serveur | Conforme |
| CV-S4-5-C02 | Proposition en attente | Étape proposal, absence d'activité/réponse qualifiante et délai de version prouvés | Conforme sous preuve |
| CV-S4-5-C03 | Occasion oubliée | Opportunité ouverte, absence d'activité/prochaine action/échéance, exclusions évaluées | Conforme sous preuve |
| CV-S4-5-C04 | Fidélité Prévol | Même snapshot, Feu, capacités et exclusions entre Prévol et future exécution | Conforme |
| CV-S4-5-C05 | Non-effet | Aucun déplacement, fermeture, conversion, réattribution silencieuse ou envoi | Conforme |
| CV-S4-5-C06 | Responsable | Responsable actif, même organisation et permission vérifiés avant toute préparation | Conforme sous preuve |
| CV-S4-5-C07 | Déduplication | Exact-match rattaché ; ambiguïté en quarantaine ; aucune fusion automatique | Conforme |
| CV-S4-5-C08 | Résultat to_verify | Recherche par clé d'idempotence/corrélation avant toute nouvelle tentative | Conforme |
| CV-S4-5-C09 | Cycle de vie | needs_review, blocked, exception, to_verify et invalidation représentés | Conforme |
| CV-S4-5-C10 | Suspension | Suspension Playbook/organisation prioritaire et observable | Conforme sous preuve |
| CV-S4-5-C11 | UX | Surfaces Playbooks/Entrées et exceptions, sans seconde saisie IA | Conforme |
| CV-S4-5-C12 | Traçabilité | Décision, version, garde, exception et acteur reconstituables | Conforme sous preuve |

## 5. Prescriptions appliquées au niveau de la définition

Les sept prescriptions sont maintenant intégrées aux contrats, aux règles, aux exceptions et aux oracles D1. Leur
preuve d'exécution D2/D3 reste volontairement différée jusqu'à l'implémentation isolée autorisée par la Porte 4.

### CV-S4-5-01 — Prouver les déclencheurs et les exclusions

La définition impose au service de produire une preuve canonique de l'étape, de l'activité, de la réponse, de la prochaine action, de l'échéance, de l'attente, de la fermeture et de la conversion. Une donnée absente ou contradictoire devient needs_review ; elle ne peut jamais être interprétée comme une occasion oubliée par défaut.

**Preuve restante :** PV-FUN-05, PV-FUN-06, PV-RULE-05.

### CV-S4-5-02 — Rendre l'idempotence et la fréquence explicites

La clé fonctionnelle combine organisation, Playbook, version, opportunité canonique et fenêtre de règle. Une seule proposition active et une seule tâche équivalente sont admissibles dans cette fenêtre. Une proposition déjà consommée ou suspendue ne doit pas renaître lors d'un rejeu.

**Preuve restante :** PV-SEC-05, PV-OBS-05.

### CV-S4-5-03 — Maintenir la frontière sans effet CRM

Les contrats et commandes interdisent explicitement toute modification de pipeline, fermeture, conversion, réattribution silencieuse, fusion et communication externe. Une tâche interne ou un brouillon éventuel passe par S4-4, son approbation et une garde fraîche.

**Preuve restante :** PV-FUN-05, PV-FUN-06, PV-SEC-05.

### CV-S4-5-04 — Protéger le responsable et la capacité

Un responsable indisponible ne doit jamais entraîner une réattribution automatique ou aléatoire. La résolution choisit un membre actif autorisé dans la même organisation, est auditée et réévalue le Prévol avant toute préparation.

**Preuve restante :** PV-EXC-01, PV-SEC-05.

### CV-S4-5-05 — Séparer doublon exact et ambiguïté

Un doublon exact est rattaché à la fiche canonique avec son identifiant. Une correspondance ambiguë est placée en quarantaine avec les candidates et la raison ; aucune fusion, création de prospect ou tâche ne peut être effectuée tant qu'un humain n'a pas tranché.

**Preuve restante :** PV-EXC-02, PV-EXC-03.

### CV-S4-5-06 — Réconcilier to_verify sans retry aveugle

Un résultat incertain est recherché par clé d'idempotence, identifiant de corrélation et journal d'événements. Il est soit réconcilié vers un résultat terminal, soit maintenu en exception ; un nouveau traitement ne peut être lancé qu'à la suite d'une résolution explicite.

**Preuve restante :** PV-EXC-04, PV-OBS-05.

### CV-S4-5-07 — Borner le périmètre et la suspension

Chaque évaluation doit appliquer le tenant, l'organisation, le rôle, le volume maximal, la génération de suspension et le snapshot de données. Une suspension en cours invalide les propositions antérieures et doit être visible dans l'audit.

**Preuve restante :** PV-SEC-05, PV-OBS-05.

## 6. Compatibilité avec les tranches précédentes

- **S4-1 :** S4-5 réutilise le même calcul déterministe du Feu, la même garde de capacité, le même Prévol et les mêmes états d'invalidation.
- **S4-2 :** les résultats concernant les prospects et tâches restent canoniques, idempotents et soumis au Passeport ; S4-5 n'introduit aucun objet parallèle.
- **S4-4 :** toute préparation de tâche ou de brouillon est déléguée au cycle d'approbation existant ; aucune communication n'est envoyée par S4-5.

## 7. Scénarios D1 à démontrer

| Scénario | Résultat attendu |
|---|---|
| Proposition ouverte sans réponse au-delà du délai | Prévol explicable ou revue selon le Feu ; pipeline inchangé |
| Proposition récemment active | Exclusion déterministe ; aucune proposition |
| Occasion ouverte sans activité ni prochaine action | Revue humaine ; aucune fermeture ni relance |
| Responsable devenu inactif | owner_unavailable ; aucune attribution automatique |
| Deux fiches plausibles | ambiguous_match en quarantaine ; aucun effet |
| Prospect déjà connu | Rattachement à l'identifiant canonique ; aucun doublon |
| Timeout ou résultat incertain | to_verify ; réconciliation obligatoire |
| Suspension pendant une proposition | Proposition invalidée ; aucun effet différé |

## 8. Risques résiduels

- La qualité du déclencheur dépend de la complétude et de la fraîcheur des données CRM.
- Le calcul de capacité et de fréquence devra être mesuré sur un volume représentatif avant toute activation.
- Les preuves de garde et d'idempotence restent à produire dans le runtime après la Porte 4.
- Les intégrations LinkedIn, Facebook, courriel et autres canaux restent hors périmètre de S4-5.

## 9. Verdict et suite

**S4-5 est clôturée pour définition : CV-S4-5-01 à CV-S4-5-07 sont appliquées au niveau contractuel.** La clôture
n'autorise aucune construction intégrée et ne prononce pas la Porte 4.

La suite est la consolidation dans le dossier de Porte 4, puis la production séparée des preuves D2/D3 pendant
l'implémentation isolée. Les données réelles, le worker, les connecteurs, les effets CRM et le déploiement restent
subordonnés à la Porte 4.

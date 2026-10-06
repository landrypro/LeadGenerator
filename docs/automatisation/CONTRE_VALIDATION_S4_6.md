# Contre-validation S4-6 — Preuves, résilience et préparation de la Porte 4

> **Verdict : prescriptions appliquées — S4-6 clôturée pour définition**  
> **Décision à la date de la contre-validation :** runtime, worker, migration, connecteurs, effets CRM et Porte 4 non autorisés. Cette conclusion D1 est remplacée, pour le seul périmètre `P4-Lite`, par le `GO avec réserves` consigné dans le [dossier Porte 4](./PORTE_4_PRET_A_CONSTRUIRE.md).  
> **Date :** 1er octobre 2026  
> **Portée :** contre-validation documentaire D1 ; aucune exécution Automation réelle.

## 1. Objet et décision

Cette contre-validation examine la définition de [S4-6 — Preuves, résilience et préparation de la Porte 4](./S4_6_PREUVES_RESILIENCE_PORTE_4.md) et son raccordement aux tranches S4-0 à S4-5, à T1-T4 et à RF-AUT-2.1.

Les prescriptions CV-S4-6-01 à CV-S4-6-07 sont appliquées au niveau contractuel et documentaire, ce qui clôture
S4-6 pour sa définition. Cette décision ne transforme pas les scénarios D1 en preuves D2/D3 et ne prononce pas la
Porte 4.

## 2. Artefacts contrôlés

- [S4-6 — Preuves, résilience et préparation de la Porte 4](./S4_6_PREUVES_RESILIENCE_PORTE_4.md) ;
- [plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md) ;
- [backlog détaillé BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [registre des preuves PV-AUT-4.1](./PREUVES_VALIDATION_ETAPE_4.md) ;
- [dossier Porte 4](./PORTE_4_PRET_A_CONSTRUIRE.md) ;
- [référence fonctionnelle RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) ;
- [contre-validations S4-1 à S4-5](./CONTRE_VALIDATION_S4_5.md).

## 3. Résultat synthétique

| Domaine contrôlé | Résultat | Observation |
|---|---|---|
| Fixtures et multi-tenant | Conforme sous prescription | Les cas nominaux, négatifs, adversariaux et deux tenants sont décrits. |
| Niveaux D0-D4 | Conforme | Les promotions et limites de preuve sont explicitement séparées. |
| Matrice de validation | Conforme sous prescription | Les scénarios P0/P1 et oracles sont définis, pas encore exécutés. |
| Charge, latence et capacité | Conforme sous preuve | T4-CAP-01..05 et les seuils sont cadrés ; aucune mesure réelle n'est revendiquée. |
| Sécurité et IA adversariale | Conforme sous prescription | Injection, tenant, capacités et sortie IA fermée sont couverts. |
| Résilience et rollback | Conforme sous preuve | Timeout, rejeu, suspension, réconciliation et arrêt sont décrits. |
| Observabilité et rétention | Conforme sous prescription | Corrélation et minimisation sont définies ; politique finale à confirmer. |
| Gouvernance Porte 4 | Conforme sous réserve | Dossier, propriétaires, risques et verdict sont listés ; capacité et environnement restent à confirmer. |
| Construction et runtime | Non autorisé à la date du contrôle D1 | La définition est clôturée ; aucune activation n'était autorisée. Le `GO avec réserves` ultérieur autorise uniquement la préparation et l'implémentation contrôlée `P4-Lite`, sous flags désactivés. |

## 4. Matrice de contre-validation

| ID | Point vérifié | Critère attendu | Verdict |
|---|---|---|---|
| CV-S4-6-C01 | Fixtures | Deux tenants, rôles, capacités, doublons, exceptions et cas d'injection sans données réelles | Conforme |
| CV-S4-6-C02 | Traçabilité des preuves | Chaque P0/P1 possède scénario, données, oracle, propriétaire et niveau D1-D4 | Conforme sous preuve |
| CV-S4-6-C03 | Promotion D1-D4 | Une preuve prévue n'est jamais présentée comme exécutée ; version et environnement conservés | Conforme |
| CV-S4-6-C04 | Capacité | Charge, p95, saturation, reprise et borne de file mesurables avant SLO | Conforme sous preuve |
| CV-S4-6-C05 | Sécurité/IA | Injection, tenant, capacité retirée, rejeu et outil IA interdit couverts par oracle fermé | Conforme |
| CV-S4-6-C06 | Résilience | Timeout, worker arrêté, doublon, suspension et résultat incertain aboutissent à un état sûr | Conforme sous preuve |
| CV-S4-6-C07 | Observabilité | Corrélation, état, Feu, garde, exception, suspension et rétention sans PII inutile | Conforme sous prescription |
| CV-S4-6-C08 | Rollback | Arrêt, annulation, réconciliation et retour de version sans doublon ni suppression silencieuse | Conforme sous preuve |
| CV-S4-6-C09 | Gouvernance | Propriétaires, dépendances, risques, réserves et tranches autorisables réunis dans la Porte 4 | Conforme sous réserve |
| CV-S4-6-C10 | Limites de lancement | Azure 4.6 et sessions PME restent reportés ; aucun GO implicite de production | Conforme |

## 5. Prescriptions appliquées au niveau de la définition

Les sept prescriptions sont maintenant intégrées au catalogue de fixtures, aux oracles, aux plans de mesure, aux
scénarios de sécurité et de panne, à l'observabilité et au dossier de Porte 4. Les preuves D2/D3 restent différées
jusqu'à l'implémentation isolée autorisée par la Porte 4.

### CV-S4-6-01 — Fermer le catalogue de fixtures

Chaque fixture doit avoir un identifiant, un tenant, un état initial, une version de règles, un propriétaire, un
oracle positif et un oracle négatif. Les données personnelles, secrets, brouillons et canaux réels sont interdits.

**Preuve restante :** PV-DATA-03.

### CV-S4-6-02 — Rendre la matrice de preuves exécutable

Chaque P0/P1 doit être relié à une procédure, un résultat attendu, un résultat de refus et une règle de promotion.
Une capture ou une intention ne peut pas être déclarée comme preuve d'exécution.

**Preuve restante :** PV-QA-01, PV-GOV-01.

### CV-S4-6-03 — Mesurer avant de publier les SLO

Les seuils de p95, saturation, taille de file et reprise doivent être mesurés sur un environnement représentatif.
Une valeur non mesurée reste une hypothèse et ne peut pas autoriser l'élargissement du périmètre.

**Preuve restante :** PV-CAP-01.

### CV-S4-6-04 — Fermer la sécurité adversariale

Les dix cas AI-ADV-01..10 doivent démontrer l'absence de franchissement de tenant, de capacité ou de rôle, ainsi que
l'absence d'outil, d'écriture CRM et de communication à partir d'une injection.

**Preuve restante :** PV-AI-06, PV-SEC-05.

### CV-S4-6-05 — Rendre la résilience idempotente

Un timeout, un worker redémarré, un événement dupliqué ou une suspension doit conduire à un état terminal sûr,
to_verify ou exception. Aucun retry aveugle, effet différé ou doublon ne doit être possible.

**Preuve restante :** PV-OPS-03, PV-EXC-04.

### CV-S4-6-06 — Tracer sans sur-collecter

Les événements doivent conserver corrélation, tenant, version, état, Feu, garde, exception, acteur et horodatage,
sans enregistrer phrases libres, secrets, brouillons ou données personnelles inutiles.

**Preuve restante :** PV-OBS-02, PV-AUD-02.

### CV-S4-6-07 — Compléter le dossier de Porte 4

Le dossier doit nommer les responsables, confirmer capacité et environnement isolé, expliciter les réserves et lister
les seules tranches constructibles. Le verdict doit être GO, GO avec réserves ou NO-GO ; il ne peut pas être implicite.

**Preuve restante :** PV-GOV-01.

## 6. Compatibilité avec les tranches précédentes

- **S4-1 :** S4-6 reprend le noyau déterministe, le Prévol, l'invalidation et la priorité du Feu.
- **S4-2 :** les fixtures et oracles utilisent les objets canoniques, la double garde, le Passeport et l'idempotence.
- **S4-3 :** les évaluations adversariales respectent l'intention structurée, l'absence d'outil et le repli.
- **S4-4 :** brouillons, approbations, expiration et absence d'envoi restent les invariants de référence.
- **S4-5 :** les deux Playbooks et quatre exceptions sont inclus dans les scénarios de charge, panne et rollback.

## 7. Risques résiduels

- Capacité de l'équipe et environnement isolé non confirmés.
- SLO de charge non mesurés.
- Politique de rétention finale à approuver.
- Preuve Azure 4.6 reportée à la fin de la Phase 5.
- Sessions PME reportées après la production.

## 8. Verdict et suite

**S4-6 est clôturée pour définition : CV-S4-6-01 à CV-S4-6-07 sont appliquées au niveau contractuel.** Cette clôture
n'autorise aucune construction intégrée et ne prononce pas la Porte 4.

La suite est la consolidation du dossier de Porte 4, puis la production séparée des preuves D2/D3 lors de
l'implémentation isolée. Le worker, les connecteurs, les effets CRM et le déploiement restent subordonnés à la Porte 4.

# Backlog détaillé — Étape 4 Automatisation

> **Version :** `BL-AUT-4.1`  
> **Statut :** backlog de planification complété ; S4-2, S4-3, S4-4, S4-5 et S4-6 clôturées pour définition ; S4-7 active sous réserves ; OpenAI choisi pour AUT-4706 ; Porte 4 clôturée avec `GO avec réserves` pour `P4-Lite`.  
> **Contrat fonctionnel :** [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md).  
> **Plan parent :** [Étape 4 — Plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md).

## 1. Règles de gestion du backlog

Chaque item possède un identifiant stable, une priorité, un résultat observable, des dépendances, un oracle et une
preuve attendue. Un item ne peut pas élargir le périmètre V2.1. Toute modification du Feu, du Prévol, d’un rôle, d’un
canal, d’un Playbook ou de la persistance doit être traitée comme un changement versionné.

### Priorités

| Priorité | Signification |
|---|---|
| `P0` | Condition de sécurité ou de cohérence nécessaire avant tout effet CRM. |
| `P1` | Nécessaire au parcours Lite V2.1 et à la Porte 4. |
| `P2` | Utile à l’exploitation ou à l’adoption, sans bloquer le premier parcours vertical. |

### États autorisés pendant l’Étape 4

`À préciser → Prêt à estimer → Estimé → Prêt pour Porte 4`.

Les états `En développement`, `En test` et `Livré` sont interdits avant un verdict positif explicite de Porte 4.

## 2. Estimation par tranche

| Tranche | Résultat planifié | Ingénierie | Produit/QA/Sécurité | Dépend de |
|---|---|---:|---:|---|
| `S4-0` | Fondations sans effet | 8–12 j.h. | 3–5 j.h. | Porte 3 |
| `S4-1` | Noyau Feu et Prévol | 10–15 j.h. | 3–5 j.h. | `S4-0` |
| `S4-2` | Nouveau prospect interne | 12–18 j.h. | 4–6 j.h. | `S4-1` |
| `S4-3` | Assistant IA encadré | 8–14 j.h. | 3–5 j.h. | `S4-1` |
| `S4-4` | Brouillons et approbations | 10–15 j.h. | 3–5 j.h. | `S4-2`, `S4-3` |
| `S4-5` | Deux Playbooks et exceptions | 12–18 j.h. | 4–6 j.h. | `S4-2`, `S4-4` |
| `S4-6` | Preuves, résilience et Porte 4 | 12–18 j.h. | 5–8 j.h. | Toutes |
| `S4-7` | Levée des réserves et suivi de la Porte 4 | À estimer | À estimer | `S4-6`, `GO avec réserves` de Porte 4 |
| **Total** | **V1 interne, sans envoi autonome** | **72–110 j.h.** | **25–40 j.h.** | — |

Ces fourchettes sont des hypothèses de planification et non un engagement de calendrier. La capacité de l’équipe et le
fournisseur IA restent à confirmer.

## 3. `S4-0` — Fondations sans effet

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4001` | P0 | Geler les constantes V2.1 et les versions | RF-AUT-2.1 | Table de correspondance comportement → règle → version ; `PV-DES-01`. |
| `AUT-4002` | P0 | Définir les flags global, organisation et Playbook | T3 ADR-009 | Valeur sûre par défaut, ordre de priorité et motif d’arrêt ; `PV-OPS-01`. |
| `AUT-4003` | P0 | Définir les capabilities Automation par rôle | Matrice T3 | Aucun droit implicite ; cas de révocation documenté ; `PV-SEC-01`. |
| `AUT-4004` | P0 | Borner le principal `automation-system` | `P3-SEC-02` | Origines, portée, TTL et audit définis ; `PV-SEC-02`. |
| `AUT-4005` | P0 | Concevoir les migrations Automation et le rollback | Modèle T2 | Tables isolées, RLS, ordre et rollback testable ; `PV-DATA-01`. |
| `AUT-4006` | P1 | Définir corrélation, événements et audit minimal | T2/T3 | Chaque commande a une décision et un événement terminal ; `PV-AUD-01`. |
| `AUT-4007` | P1 | Définir métriques et limites de cardinalité | T3/T4 | Aucune PII ni phrase libre dans les labels ; `PV-OBS-01`. |

## 4. `S4-1` — Noyau déterministe et Prévol

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4101` | P0 | Modéliser Playbook, version et snapshot | `AUT-4005` | Une version active est immuable ; `PV-DATA-02`. |
| `AUT-4102` | P0 | Définir le contexte d’évaluation canonique | CRM V1 | Tenant, acteur, objet, canal, règle et horodatage explicites ; `PV-RULE-01`. |
| `AUT-4103` | P0 | Spécifier le noyau Feu relationnel | T2 | Priorité `Rouge > Jaune > Vert`, inconnu jamais Vert ; `PV-RULE-02`. |
| `AUT-4104` | P0 | Spécifier le Prévol sans effet | `AUT-4103` | Même noyau et version que l’exécution ; `PV-RULE-03`. |
| `AUT-4105` | P1 | Normaliser raisons et explications | UX V2.1 | Motif lisible + code stable, sans décision IA ; `PV-UX-01`. |
| `AUT-4106` | P1 | Définir invalidation du Prévol | Version/snapshot | Changement matériel rend le Prévol obsolète ; `PV-RULE-04`. |

## 5. `S4-2` — Nouveau prospect et tâche interne

La définition détaillée, ses frontières et la clôture de ses prescriptions sont documentées dans [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) et sa [contre-validation](./CONTRE_VALIDATION_S4_2.md).

**État de tranche :** `AUT-4201` à `AUT-4206` sont **prêts pour la Porte 4 au niveau de la définition**. Aucun item
n’est en développement, en test intégré ou livré dans le produit actif.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4201` | P0 | Admission tenantisée et idempotente | `AUT-4003`, `AUT-4101` | Même commande → même exécution ; autre charge → conflit ; `PV-IDEM-01`. |
| `AUT-4202` | P0 | Garde juste avant effet CRM | `P3-SEC-01` | Tenant, capacité, Feu, version, suspension et état revérifiés ; `PV-SEC-03`. |
| `AUT-4203` | P0 | Interdire le retry aveugle d’effet | `P3-RES-01` | Timeout ambigu → `to_verify`, jamais seconde tâche automatique ; `PV-IDEM-02`. |
| `AUT-4204` | P1 | Préparer une tâche interne unique | `AUT-4202` | Responsable actif et prochaine action explicite ; `PV-FUN-01`. |
| `AUT-4205` | P1 | Rattacher le Passeport aux objets canoniques | CRM prospect/tâche | Aucun registre CRM parallèle ; `PV-FUN-02`. |
| `AUT-4206` | P1 | Traiter doublon exact et correspondance ambiguë | Déduplication CRM | Rattachement sûr ou quarantaine, jamais fusion silencieuse ; `PV-FUN-03`. |

## 6. `S4-3` — Assistant IA encadré

La définition détaillée et sa contre-validation sont documentées dans [S4-3 — Assistant IA encadré](./S4_3_ASSISTANT_IA_ENCADRE.md) et [CONTRE-VALIDATION-S4-3](./CONTRE_VALIDATION_S4_3.md). Les prescriptions CV-S4-3-01 à CV-S4-3-07 sont appliquées au niveau contractuel ; aucun fournisseur réel, outil IA, persistance de prompt ou effet métier n’est autorisé.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4301` | P0 | Fermer le schéma d’intention IA | T3 IA | Objet, objectif, périmètre, volume et clarification seulement ; `PV-AI-01`. |
| `AUT-4302` | P0 | Interdire tout outil ou capacité IA | `AUT-4301` | Sortie IA incapable d’appeler le CRM ou la file ; `PV-AI-02`. |
| `AUT-4303` | P0 | Minimiser les données envoyées et conservées | `P3-DATA-01` | Phrase libre non persistée par défaut ; `PV-AI-03`. |
| `AUT-4304` | P1 | Préparer un plan lisible avant action | Prototype V2.1 | Périmètre, volume, contrôles et absence d’effet visibles ; `PV-UX-02`. |
| `AUT-4305` | P1 | Définir clarification et repli déterministe | `AUT-4301` | Hors schéma, timeout ou quota → parcours guidé ; `PV-AI-04`. |
| `AUT-4306` | P1 | Définir quotas et budget IA | `P3-IA-01` | Seuils fake locaux confirmés et configurables ; prix/quota OpenAI restent réservés ; `PV-AI-05`. |

## 7. `S4-4` — Brouillons, approbations et cycles

La définition détaillée est documentée dans [S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md) et sa [contre-validation](./CONTRE_VALIDATION_S4_4.md). Les prescriptions CV-S4-4-01 à CV-S4-4-07 sont appliquées au niveau contractuel ; aucun connecteur, envoi, persistance ou API active n’est autorisé.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4401` | P0 | Créer un brouillon non envoyé | `AUT-4202` | Aucun connecteur d’envoi disponible en V1 ; `PV-FUN-04`. |
| `AUT-4402` | P0 | Lier l’approbation aux éléments matériels | T2/T3 | Contenu, destinataire, canal, Playbook, règle et justification ; `PV-APP-01`. |
| `AUT-4403` | P0 | Invalider sur changement matériel | `AUT-4402` | Toute modification pertinente exige une nouvelle lecture ; `PV-APP-02`. |
| `AUT-4404` | P1 | Définir expiration et obsolescence | Horloge/version | Brouillon expiré non exécutable ; `PV-APP-03`. |
| `AUT-4405` | P0 | Appliquer suspension générationnelle | `AUT-4002` | Aucun nouvel effet après la génération d’arrêt ; `PV-OPS-02`. |
| `AUT-4406` | P1 | Journaliser refus et approbation sans contenu sensible | Audit | Identité, version, décision et raison minimale ; `PV-AUD-02`. |

## 8. `S4-5` — Playbooks complémentaires et exceptions

La définition détaillée est documentée dans [S4-5 — Playbooks complémentaires et exceptions](./S4_5_PLAYBOOKS_COMPLEMENTAIRES_EXCEPTIONS.md) et sa [contre-validation](./CONTRE_VALIDATION_S4_5.md). Les prescriptions CV-S4-5-01 à CV-S4-5-07 sont appliquées et la définition est clôturée ; aucune modification du pipeline, aucun contact, aucune persistance, aucun worker et aucune API active ne sont autorisés.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4501` | P1 | Proposition en attente | `S4-1`, `S4-4` | Suivi proposé, pipeline inchangé ; `PV-FUN-05`. |
| `AUT-4502` | P1 | Occasion oubliée | `S4-1`, `S4-4` | Revue humaine, aucune fermeture automatique ; `PV-FUN-06`. |
| `AUT-4503` | P0 | Responsable indisponible | Capacités membres | Aucun transfert aléatoire ; exception ou choix humain ; `PV-EXC-01`. |
| `AUT-4504` | P0 | Correspondance ambiguë | Déduplication | Quarantaine sans création de tâche ; `PV-EXC-02`. |
| `AUT-4505` | P1 | Prospect déjà connu | CRM canonique | Rattachement à la fiche existante, aucun doublon ; `PV-EXC-03`. |
| `AUT-4506` | P0 | Réconciliation d’état incertain | `AUT-4203` | Résolution idempotente et auditée ; `PV-EXC-04`. |

## 9. `S4-6` — Validation, observabilité et Porte 4

La tranche est définie dans [S4-6 — Preuves, résilience et préparation de la Porte 4](./S4_6_PREUVES_RESILIENCE_PORTE_4.md)
et sa [contre-validation](./CONTRE_VALIDATION_S4_6.md). Les prescriptions CV-S4-6-01 à CV-S4-6-07 sont appliquées et
la définition est clôturée ; aucune route, worker, migration, connecteur ou effet CRM n'est créé.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4601` | P0 | Catalogue de fixtures synthétiques | Toutes tranches | Deux tenants, rôles, permissions, doublons et ambiguïtés ; `PV-DATA-03`. |
| `AUT-4602` | P0 | Matrice de tests et oracles | Protocole de preuves | Chaque P0/P1 a au moins un test positif et négatif ; `PV-QA-01`. |
| `AUT-4603` | P0 | Plan de charge `T4-CAP-01..05` | Worker/socle | `S95`, `Smax`, saturation et reprise mesurables ; `PV-CAP-01`. |
| `AUT-4604` | P0 | Évaluations adversariales IA | `AUT-4301..06` | `AI-ADV-01..10` avec oracle fermé ; `PV-AI-06`. |
| `AUT-4605` | P1 | Dashboard et alertes | `AUT-4007` | File, blocages, exceptions, âge et suspension visibles ; `PV-OBS-02`. |
| `AUT-4606` | P0 | Procédure d’arrêt et rollback | Flags/migrations | Arrêt, annulation, réconciliation et restauration définis ; `PV-OPS-03`. |
| `AUT-4607` | P1 | Dossier de décision Porte 4 | Tous livrables | Preuves, réserves et tranches autorisables assemblées ; `PV-GOV-01`. |

Les modalités d'exécution de ces items sont confirmées dans le [dossier IMP-A6](./IMP_A6_PREPARATION.md) : tests
Docker/WSL locaux, fixtures synthétiques, pannes test-only, rollback ordonné sur base jetable et rapports minimisés.
L'implémentation IMP-A6 est présente depuis le 4 octobre 2026 et ses tests ciblés sont verts ; `AUT-4601..4607`
ont ensuite passé le verrou qualité complet. Le rapport D3 minimisé est produit sous
`test-results/automation-imp-a6/evidence.json` sur Docker/WSL local et fixtures synthétiques. La revue formelle
Produit/QA/Sécurité et le dossier de décision `AUT-4607` restent à enregistrer.
Ces résultats ne constituent ni une activation, ni du staging, ni une preuve D4.

## 10. `S4-7` — Levée des réserves et réouverture de la Porte 4

La phase [S4-7 — Levée des réserves et réouverture de la Porte 4](./S4_7_LEVEE_RESERVES_PORTE_4.md) est active avec le
`GO avec réserves` de Porte 4. Elle suit les preuves D2/D3 dans un environnement isolé et réinitialisable pendant
l'implémentation `P4-Lite`. Elle n'autorise ni communication externe, ni activation IA réelle, ni production.

| ID | P | Résultat attendu | Dépendances | Acceptation et preuve |
|---|---|---|---|---|
| `AUT-4701` | P0 | Owners et capacité confirmés | Porte 4 | Réserve assignée, disponibilité et date cible ; `PV-S47-GOV-01`. |
| `AUT-4702` | P0 | Environnement isolé opérationnel | Socle Phase 4 | PostgreSQL/RLS, Redis, worker contrôlé et faux fournisseurs réinitialisables ; `PV-S47-ENV-01`. |
| `AUT-4703` | P0 | Preuves déterministes D2/D3 | S4-1, fixtures | Feu/Prévol, version, garde et idempotence reproduits ; `PV-S47-RUN-01`. |
| `AUT-4704` | P0 | Preuves d'exceptions | S4-2, S4-5 | Doublon, responsable et `to_verify` sans effet silencieux ; `PV-S47-RUN-02`. |
| `AUT-4705` | P0 | Résilience et rollback démontrés | S4-6 | Suspension, reprise, concurrence et rollback sans doublon ; `PV-S47-RES-01`. |
| `AUT-4706` | P0 | Fournisseur IA arrêté et réserves suivies | S4-3, T3 | OpenAI cible choisi ; faux fournisseur et limites locales validés pour IMP-A5 ; rétention, contrat, prix et quotas OpenAI restent réservés ; `PV-S47-AI-01`. |
| `AUT-4707` | P1 | Audit, télémétrie et risques inspectés | S4-6 | Corrélation reconstituable, PII minimisée et risques mis à jour ; `PV-S47-OBS-01`. |
| `AUT-4708` | P0 | Dossier de réouverture Porte 4 | AUT-4701..4707 | Tranches autorisables, limites et verdict explicitement listés ; `PV-S47-GATE-01`. |

## 11. Dépendances externes à confirmer

| ID | Dépendance | Décision requise | Impact si absente |
|---|---|---|---|
| `DEP-01` | Capacité réelle de l’équipe | Nommer disponibilités Produit, Backend, QA, Sécurité et Plateforme | Calendrier non engageable. |
| `DEP-02` | Fournisseur et modèle IA réel | Prix, résidence, conservation, non-entraînement et quotas OpenAI | `S4-3` reste limité au faux fournisseur local tant que ces points ne sont pas signés. |
| `DEP-03` | Environnement de test isolé | PostgreSQL, Redis, worker et services simulés | Preuves exécutables impossibles. |
| `DEP-04` | Politique de rétention | Durées pour intention, audit, brouillon et événement | Persistance IA/audit bloquée. |
| `DEP-05` | Mesure de capacité worker | Exécuter `T4-CAP-01..05` sur configuration représentative | Aucun SLO publiable. |

## 12. Ordre autorisé pour `P4-Lite`

1. implémenter les fondations isolées, flags et migrations réversibles (`IMP-A1`) ;
2. démontrer Feu/Prévol et Passeport (`IMP-A2`) ;
3. intégrer l'admission et la tâche interne sous garde/idempotence (`IMP-A3`) ;
4. brancher API et worker contrôlé, toujours sous flags désactivés (`IMP-A4`) ;
5. implémenter l'Assistant avec faux fournisseur (`IMP-A5`) ;
6. produire les preuves de résilience, audit et rollback (`IMP-A6`).

Les Playbooks complémentaires, les brouillons externes, OpenAI réel et les connecteurs restent hors `P4-Lite`. Le détail
des tranches est figé dans [Pré-Phase 5 — Préparation de l'implémentation](./PRE_PHASE_5_IMPLEMENTATION_AUTOMATISATION.md).

## 13. Statut de complétude

| Élément | État |
|---|---|
| Tranches et items | Complet pour la planification V2.1 |
| Priorités | Complètes |
| Dépendances | Identifiées, confirmations externes ouvertes |
| Estimations | Fourchettes disponibles, capacité d’équipe non confirmée |
| Critères d’acceptation | Définis et reliés aux preuves `PV-*` |
| Autorisation de construire | **Accordée avec réserves — `P4-Lite` uniquement, sous flags désactivés** |

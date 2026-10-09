# Porte 4 — Prêt à construire

> **Statut : Porte 4 clôturée avec `GO avec réserves` le 4 octobre 2026 — preuves D3 locales acceptées ; aucune activation autorisée.**  
> **Entrée :** Étape 4 — Plan de livraison et protocole de validation.  
> **Sortie possible :** `GO`, `GO avec réserves` ou `NO-GO` vers la construction des tranches autorisées.

Le [contrôle final Étapes 1 à 4 / Phases 1 à 4](./CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md) confirme une cohérence
documentaire suffisante pour **préparer** l’implémentation. Il ne prononce pas cette Porte et ne transforme pas les
preuves D1 en preuves d’exécution.

La tranche [S4-0 — Fondations sans effet](./S4_0_FONDATIONS_SANS_EFFET.md) est clôturée pour son périmètre de
préparation statique. Son résultat ne vaut pas verdict de Porte 4.

La [contre-validation S4-0](./CONTRE_VALIDATION_S4_0.md) et le GO utilisateur ont autorisé la définition puis la
réalisation isolée de [S4-1](./S4_1_NOYAU_DETERMINISTE_PREVOL.md), sans autoriser l’intégration API/persistance/worker,
la construction active ni les effets CRM.

Le noyau runtime isolé de S4-1 est contre-validé dans [CONTRE-VALIDATION-S4-1](./CONTRE_VALIDATION_S4_1.md). Cette preuve
ne prononce pas la Porte 4.

La définition de [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) est désormais
clôturée pour son périmètre documentaire. Elle fixe le parcours d’admission canonique, la tâche interne, l’idempotence,
la double garde, le Passeport et les exceptions, sans autoriser leur intégration dans le produit actif.
La [contre-validation S4-2](./CONTRE_VALIDATION_S4_2.md) confirme un `GO sous prescriptions` pour la définition et
maintient un `NO-GO` sur la construction et les effets ; les preuves D2/D3 restent à produire.

La définition de [S4-3 — Assistant IA encadré](./S4_3_ASSISTANT_IA_ENCADRE.md) est clôturée au niveau contractuel. Elle
ne change pas la décision de Porte 4 : le fournisseur, les quotas exécutés, le faux fournisseur, les évaluations
adversariales et le repli devront être prouvés avant toute intégration IA.
La [contre-validation S4-3](./CONTRE_VALIDATION_S4_3.md) confirme l’application des prescriptions et maintient un
`NO-GO` sur le modèle réel, les outils et l’intégration.

La définition de [S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md) est
clôturée au niveau contractuel. Sa [contre-validation](./CONTRE_VALIDATION_S4_4.md) confirme l’absence d’envoi, la
liaison d’une approbation à une révision exacte, l’invalidation et la garde fraîche. Elle maintient un `NO-GO` sur le
runtime de brouillon, l’approbation active, les connecteurs et toute communication externe.

La définition de [S4-5 — Playbooks complémentaires et exceptions](./S4_5_PLAYBOOKS_COMPLEMENTAIRES_EXCEPTIONS.md) est
clôturée avec les prescriptions CV-S4-5-01 à CV-S4-5-07 appliquées, comme consigné dans
[CONTRE-VALIDATION-S4-5](./CONTRE_VALIDATION_S4_5.md). Elle ne modifie pas le pipeline ni ne crée de contact ; son
runtime reste à construire après décision de Porte 4.

La définition de [S4-6 — Preuves, résilience et préparation de la Porte 4](./S4_6_PREUVES_RESILIENCE_PORTE_4.md) est
clôturée avec les prescriptions CV-S4-6-01 à CV-S4-6-07 appliquées, comme consigné dans
[CONTRE-VALIDATION-S4-6](./CONTRE_VALIDATION_S4_6.md). Elle assemble les fixtures, oracles, mesures, scénarios de
panne, observabilité, rollback et réserves nécessaires au verdict ; elle ne constitue pas encore une autorisation de
construire.

La phase [S4-7 — Levée des réserves et réouverture de la Porte 4](./S4_7_LEVEE_RESERVES_PORTE_4.md) devient le registre
des réserves à traiter au fil de l'implémentation. OpenAI est choisi pour `AUT-4706`, mais quotas, rétention, contrat,
environnement, capacité et preuves D2/D3 restent à confirmer. Ces réserves ne permettent aucun effet externe, appel
OpenAI réel ou déploiement ; elles ne bloquent pas la préparation de la tranche `P4-Lite` sous flags désactivés.

## 1. Décision attendue

La Porte 4 ne juge plus seulement l’idée ou l’architecture. Elle vérifie que l’équipe peut construire une tranche
verticale sans découvrir une dépendance critique non traitée, et qu’elle sait démontrer le résultat avec des données
synthétiques, des oracles et un retour arrière.

Un verdict positif devra préciser les tranches autorisées. Il ne débloquera pas les effets non couverts, l’IA réelle,
les envois externes ou la production par défaut.

## 2. Checklist d’entrée

- [x] [Étape 4 — Plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md) approuvée ;
- [x] [backlog vertical `BL-AUT-4.1`](./BACKLOG_DETAILLE_ETAPE_4.md) versionné et relié à `RF-AUT-2.1` ;
- [ ] estimations révisées et capacité d’équipe confirmée ;
- [ ] dépendances et responsables confirmés ;
- [x] fixtures synthétiques multi-tenant disponibles pour la validation statique ;
- [x] [matrice de preuves `PV-AUT-4.1`](./PREUVES_VALIDATION_ETAPE_4.md) et oracles définis au niveau D1 ;
- [x] définitions S4-2, S4-3 et S4-4 contre-validées et clôturées au niveau contractuel ;
- [x] définition S4-5 documentée, contre-validée et clôturée ; CV-S4-5-01..07 appliquées au niveau contractuel ;
- [x] définition S4-6 documentée, contre-validée et clôturée ; CV-S4-6-01..07 appliquées au niveau contractuel ;
- [x] réserves sécurité, IA, données et capacité identifiées et consignées ;
- [ ] stratégie de flags, suspension et rollback répétée sur le runtime ;
- [x] conditions Azure 4.6 et sessions PME toujours correctement reportées ;
- [x] dérogation au verrou documentaire explicitement limitée, sans extension à la construction/production ;
- [x] Porte 4 clôturée avec `GO avec réserves` pour préparer `P4-Lite` ; S4-7 suit les réserves et OpenAI est choisi pour `AUT-4706`.

## 3. Découpage de décision

| Verdict | Autorisation | Limite |
|---|---|---|
| `GO` | Construire les tranches explicitement listées | Aucun périmètre implicite. |
| `GO avec réserves` | Construire seulement les tranches sans réserve bloquante | Chaque réserve a un propriétaire et une date. |
| `NO-GO` | Continuer la conception ou corriger le socle | Aucun code Automation actif. |

## 4. Preuves à joindre

1. backlog et estimation ;
2. matrice de traçabilité fonctionnelle ;
3. plan de tests et jeux synthétiques ;
4. modèle de menace actualisé ;
5. stratégie d’environnement, flags et rollback ;
6. avis Produit, Ingénierie, QA, Sécurité, Données et Exploitation ;
7. registre des risques signé ;
8. décision de Porte 4 et liste précise des tranches autorisées.

## 5. Préparation finale — constat

| Contrôle de Porte 4 | État | Conséquence |
|---|---|---|
| Périmètre et référence RF-AUT-2.1 | Conforme | Aucun périmètre implicite autorisé. |
| Étapes S4-0 à S4-6 | Définitions clôturées ; S4-1 isolée | Intégration limitée autorisée dans `P4-Lite`, sous flags désactivés. |
| Fixtures et oracles | D1 documentés | D2/D3 à produire avant activation. |
| Capacité, estimation et responsables | Non confirmés | Réserve S4-7 ; bloque une activation ou un élargissement. |
| Environnement isolé PostgreSQL/Redis/worker | Non confirmé | Réserve S4-7 ; requis avant exécution de la tranche concernée. |
| Flags, suspension et rollback runtime | Non répétés | Réserve S4-7 ; requis avant activation. |
| Fournisseur IA et rétention | Fake et limites locales IMP-A5 confirmés ; quotas, contrat et rétention OpenAI à confirmer | IA réelle et persistance restent interdites. |
| Azure 4.6 et sessions PME | Reportés conformément à la décision | Ne constituent pas une autorisation de production. |

## 6. Verdict explicite de Porte 4

### GO avec réserves — décision ratifiée le 4 octobre 2026

La Porte 4 est clôturée avec un **GO avec réserves**. Elle accepte les preuves D3 locales d'IMP-A6 et le verrou qualité
complet, tout en maintenant les réserves D4, capacité et OpenAI réel comme bloquantes pour toute activation, staging
ou production.

> **Décision :** les preuves D3 locales d'IMP-A6 et le verrou qualité sont acceptés. La poursuite est autorisée
> uniquement sous flags désactivés, données synthétiques et sans effet externe. Les réserves D4, capacité et OpenAI
> réel restent bloquantes pour toute activation, staging ou production.

Cette autorisation permet :

- le code, les migrations réversibles et les routes nécessaires dans un environnement isolé ;
- l'intégration derrière des feature flags désactivés par défaut ;
- le worker contrôlé, les fixtures synthétiques, les tests D2/D3 et le faux fournisseur IA ;
- le Feu, le Prévol, le Passeport, l'admission `Nouveau prospect` et la tâche CRM interne avec garde et idempotence.

Elle n'autorise pas :

- l'appel OpenAI réel, la transmission de données réelles ou la persistance de phrases libres ;
- les envois externes, connecteurs sociaux, SMS, courriels ou brouillons envoyables ;
- la réattribution automatique, la fusion, la fermeture ou le déplacement silencieux du pipeline ;
- l'activation de flag pour une organisation cliente ou toute production générale.

## 7. Réserves à suivre avant activation

Les réserves suivantes sont maintenues dans S4-7. Elles sont traitées au fil des tranches, mais une réserve de
sécurité, tenant, permission, idempotence ou rollback bloque immédiatement la tranche concernée :

- capacité, responsables, estimations et dépendances confirmés ;
- environnement isolé opérationnel avec PostgreSQL, Redis, worker et faux fournisseurs ;
- preuves D2/D3 sur fixtures synthétiques ;
- tests de suspension, idempotence, reprise et rollback réussis ;
- paramètres OpenAI : quotas, contrat, rétention, garde et repli ;
- avis Produit, Ingénierie, QA, Sécurité, Données et Exploitation avant activation ;
- registre des risques mis à jour avant élargissement de la tranche.

La preuve Azure 4.6 reste reportée à la fin de la Phase 5, la nouvelle [Phase 4.7](../PHASE_4_7_RESERVE.md) reste en
réserve, et les sessions PME restent post-production.

## 8. Préparation de l'implémentation et suivi S4-7

La [Pré-Phase 5 — Préparation de l'implémentation](./PRE_PHASE_5_IMPLEMENTATION_AUTOMATISATION.md) organise les
tranches `IMP-A1` à `IMP-A6`. Le registre [S4-7](./S4_7_LEVEE_RESERVES_PORTE_4.md) suit les réserves `AUT-4701` à
`AUT-4708`, détaillées dans le [registre des réserves de Porte 4](./REGISTRE_RESERVES_PORTE_4.md). Toute nouvelle zone
d'ombre est qualifiée : non bloquante, bloquante pour la tranche, ou bloquante pour l'activation. Aucun élargissement
de périmètre ne découle implicitement de ce GO.

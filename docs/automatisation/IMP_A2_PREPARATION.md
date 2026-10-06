# IMP-A2 — Dossier de préparation

> **Statut :** prêt pour une autorisation de développement, sans activation.  
> **Portée :** moteur Feu, versions, Prévol et contrat de Passeport pour `P4-Lite`.  
> **Interdictions maintenues :** aucune écriture CRM, aucune route HTTP, aucun worker, aucune activation de flag,
> aucun appel IA ni envoi externe.

## 1. Point de départ vérifié

Le commit `137550f` d'IMP-A1 contient déjà le socle pur attendu pour IMP-A2 :

| Élément | Artefact existant | État |
|---|---|---|
| Version immuable et empreinte | `PlaybookVersion` | disponible |
| Contexte canonique tenantisé | `EvaluationContext` | disponible |
| Décision Feu fermée | `DeterministicAutomationEngine.evaluate` | disponible |
| Prévol sans effet, expirant | `DeterministicAutomationEngine.prepare` | disponible |
| Raisons et prochaines actions typées | `FireReasonCode`, `NextAction` | disponible |
| Invalidation par snapshot, version, suspension ou expiration | `PreflightPlan.is_current` | disponible |
| Tests de domaine | `tests/test_automation_deterministic.py` | disponible |

Les tables isolées `automation_playbook_versions` et `automation_decisions` sont déjà présentes, protégées par RLS,
mais ne sont pas encore exposées par un dépôt, une route ou un worker. Cette séparation reste intentionnelle : IMP-A2
renforce le contrat déterministe ; l'intégration applicative contrôlée relève d'IMP-A3 et IMP-A4.

## 2. Découpage de réalisation proposé

| Lot | Backlog | Travail | Sortie vérifiable |
|---|---|---|---|
| A2.1 | `AUT-4101`, `AUT-4102` | Stabiliser les contrats de version, de snapshot et de contexte canonique | Une empreinte identique pour une même entrée ; aucune donnée PII dans l'empreinte ou les motifs |
| A2.2 | `AUT-4103`, `AUT-4105` | Compléter la table de décision Feu et les explications contrôlées | Rouge prioritaire, inconnu jamais Vert, motifs fermés et action suivante bornée |
| A2.3 | `AUT-4104`, `AUT-4106` | Consolider le Prévol sans effet et toutes ses causes d'obsolescence | Le Prévol ne peut autoriser ni exécuter un effet ; divergence = `stale` ou nouveau Prévol |
| A2.4 | `AUT-4102`, `AUT-4105` | Définir le contrat de lecture du Passeport, sans persistance parallèle | Origine, permission, responsable et prochaine action référencent exclusivement le CRM canonique |
| A2.5 | `AUT-4703` | Produire les preuves reproductibles D2 puis D3 sur fixtures synthétiques | Résultats versionnés pour `PV-RULE-01` à `PV-RULE-04` et `PV-UX-01` |

## 3. Décision de conception confirmée

**Décision produit/architecture confirmée :** un Prévol est une entité dédiée, persistée dans
`automation_preflights`. Les lignes `automation_decisions` sont ses résultats enfants, un par sujet évalué.

```text
automation_preflights
  └─ automation_decisions
       ├─ sujet A : Feu et action proposée
       ├─ sujet B : Feu et action proposée
       └─ sujet C : Feu et action proposée
```

La migration IMP-A2 créera donc la table parent isolée/RLS et ajoutera une référence tenantisée `preflight_id` à
`automation_decisions`. Le Prévol portera la version du Playbook, le snapshot de périmètre, l'acteur, le statut,
l'expiration, la corrélation et les compteurs agrégés ; la décision conservera le Feu, les motifs et l'action proposée
pour un sujet précis.

Cette décision ne change pas le noyau pur. Elle devra être appliquée par une nouvelle migration, jamais par renommage
implicite après intégration.

## 4. Cas d'acceptation D2

| Preuve | Donnée synthétique | Oracle |
|---|---|---|
| `PV-RULE-01` | `ORG-ALPHA`, acteur autorisé, prospect borné | tenant, acteur, canal, sujet, version et horodatage sont requis |
| `PV-RULE-02` | Vert, permission inconnue, opposition, identité absente, données obsolètes | Rouge prévaut ; inconnu n'est jamais Vert ; raisons déterministes |
| `PV-RULE-03` | Même contexte et même version à deux évaluations | décision, empreinte et actions proposées identiques ; zéro mutation CRM |
| `PV-RULE-04` | Changement de version CRM, ruleset, Playbook ou suspension | le Prévol précédent n'est plus courant |
| `PV-UX-01` | Chaque niveau du Feu | code stable, champ bloquant et prochaine action lisibles sans phrase libre |
| `PV-DATA-02` | Version 1 puis configuration matériellement différente | nouvelle version et nouvelle empreinte ; version précédente inchangée |

Les tests négatifs doivent aussi couvrir l'organisation inactive, le membre inactif, la capacité absente et l'opposition.
Les tests ne créent ni prospect, ni tâche, ni opportunité, ni activité, ni communication.

## 5. Passage D2 vers D3

Une preuve D3 est obtenue seulement après exécution dans l'environnement Docker isolé, avec les éléments suivants :

- l'identifiant de fixture et le tenant ;
- la révision Git, la révision Alembic, la version de Playbook et celle des règles ;
- l'horodatage, l'oracle et le résultat ;
- la preuve d'absence de mutation CRM et d'envoi externe.

Les rapports suivent la convention `test-results/automation/<revision>/<preuve-id>/` et ne contiennent ni secret,
ni phrase libre, ni donnée client.

## 6. Definition of Ready IMP-A2

- IMP-A1 est committée et le verrou qualité local est vert ;
- les flags restent désactivés par défaut ;
- les données sont exclusivement synthétiques ;
- les documents de référence sont [S4-1](./S4_1_NOYAU_DETERMINISTE_PREVOL.md),
  [contrats T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) et
  [protocole de preuves](./PREUVES_VALIDATION_ETAPE_4.md) ;
- la décision de persistance du Prévol est confirmée avant toute migration additionnelle.

## 7. Definition of Done IMP-A2

- les contrats `AUT-4101` à `AUT-4106` sont couverts par des tests déterministes ;
- les six oracles de la section 4 sont exécutables en D2 ;
- le Passeport reste une vue de références CRM, sans copie ni source parallèle ;
- aucun effet CRM ou externe n'est techniquement accessible depuis le moteur ;
- les écarts entre Prévol et contexte courant produisent une invalidation explicable ;
- les preuves D3 disponibles sont reliées à `AUT-4703`, sinon la réserve reste ouverte explicitement.

## 8. Suite après autorisation

L'ordre de développement sera A2.1 → A2.3 → A2.2 → A2.4 → A2.5. Les flags ne seront ni activés ni rendus
accessibles à une organisation pendant cette tranche. L'admission idempotente et la tâche interne restent hors IMP-A2
et commencent seulement avec IMP-A3.

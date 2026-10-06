# S4-1 — Noyau déterministe et Prévol

> **Statut : RÉALISÉE EN RUNTIME ISOLÉ — noyau métier et Prévol validés ; intégration limitée `P4-Lite` autorisée sous flags désactivés**  
> **Date d’ouverture de la définition :** 1er octobre 2026  
> **Dépendance satisfaite :** [S4-0 — Fondations sans effet](./S4_0_FONDATIONS_SANS_EFFET.md) clôturée pour son périmètre de préparation  
> **Backlog :** `AUT-4101` à `AUT-4106` dans [BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md)

L’implémentation runtime isolée est portée par [`backend/app/domain/automation.py`](../../backend/app/domain/automation.py)
et ses tests par [`tests/test_automation_deterministic.py`](../../tests/test_automation_deterministic.py). Elle ne dépend
ni de la base, ni du worker, ni d’un fournisseur IA et ne peut pas produire d’effet CRM.

## 1. Décision de cadrage

Le GO utilisateur autorise la définition de S4-1. Cette tranche décrit le cœur qui transforme un contexte CRM canonique
en une décision déterministe et en un Prévol lisible, sans produire d’effet CRM.

La présente autorisation couvre :

- le contrat de version et de snapshot d’un Playbook ;
- le contexte canonique d’évaluation ;
- le calcul explicable du Feu relationnel ;
- la fidélité entre Prévol et exécution future ;
- le repli lorsqu’une intention est inconnue, obsolète ou non interprétable ;
- les tests déterministes et les preuves de comparaison.

Elle ne couvre pas :

- la création ou modification d’une tâche, d’un prospect ou d’une opportunité ;
- le branchement au worker actif ;
- l’appel IA réel ;
- l’approbation ou l’envoi externe ;
- une migration appliquée aux données client ;
- la production.

## 2. Objectif produit et invariant central

Pour une même version de Playbook, un même snapshot de règles et un même contexte CRM, le Prévol et l’exécution future
doivent aboutir à la même décision ou expliquer précisément pourquoi le Prévol est devenu obsolète.

> **Même entrée canonique + même version + même règle = même décision.**

Toute différence de données, de permission, de version, de suspension ou de fraîcheur doit invalider le Prévol avant tout
effet futur.

## 3. Périmètre fonctionnel de S4-1

| ID | Chantier | Résultat attendu | Preuve cible |
|---|---|---|---|
| `AUT-4101` | Playbook, version et snapshot | Une version active immuable et un snapshot référencé par chaque Prévol | `PV-DATA-02` |
| `AUT-4102` | Contexte d’évaluation canonique | Tenant, acteur, objet, canal, règle, version et horodatage explicites | `PV-RULE-01` |
| `AUT-4103` | Noyau Feu relationnel | Rouge prioritaire, Jaune explicable, Vert conditionnel, inconnu jamais Vert | `PV-RULE-02` |
| `AUT-4104` | Prévol sans effet | Plan lisible, aucune écriture, fidélité vérifiable avec l’exécution future | `PV-RULE-03` et `PV-RULE-04` |
| `AUT-4105` | Normaliser raisons et explications | Codes fermés et prochaine action contrôlée, sans décision IA | `PV-UX-01` |
| `AUT-4106` | Invalider le Prévol | Empreinte du contexte, version, suspension et expiration contrôlées | `PV-RULE-04` |

## 3 bis. Réalisation runtime isolée

Le noyau livré expose deux opérations pures :

- `DeterministicAutomationEngine.evaluate(context)` calcule une décision `RED`, `YELLOW`, `GREEN` ou `TO_VERIFY` ;
- `DeterministicAutomationEngine.prepare(context)` produit un `PreflightPlan` immuable, expirant et explicitement sans
  mutation CRM.

Garanties implémentées :

1. les blocages Rouges priment sur les vérifications Jaunes et les conditions Vertes ;
2. une permission inconnue ne devient jamais Verte ;
3. identité absente ou données obsolètes donnent `TO_VERIFY` ;
4. les versions de Playbook et le Prévol sont immuables ;
5. toute divergence d’empreinte CRM, de version ou d’état invalide le Prévol ;
6. aucune action proposée par le Prévol ne porte `effect_allowed=true`.

Cette réalisation constitue le runtime du **domaine déterministe**, pas l’intégration applicative. Les routes API, la
persistance, le worker et la garde juste avant effet restent des travaux ultérieurs soumis à la Porte 4.

## 4. Contrats de données

### 4.1 Version et snapshot

Un snapshot de Prévol doit contenir au minimum :

- `playbook_id` et `playbook_version` ;
- `ruleset_version` et identifiant du snapshot ;
- `organization_id` ;
- identifiant de l’acteur et capacités observées ;
- date de création et date d’expiration ;
- empreinte des données CRM utilisées ;
- suspension et génération d’arrêt au moment du calcul ;
- décision, raisons structurées et actions proposées.

Une version active ne peut pas être modifiée en place. Toute évolution produit crée une version distincte et une nouvelle
empreinte.

### 4.2 Contexte canonique

Le contexte est fermé et typé :

```text
EvaluationContext {
  organization_id,
  actor_id,
  actor_membership_id,
  role,
  capability_snapshot,
  subject_type,
  subject_id,
  playbook_id,
  playbook_version,
  channel,
  permission_state,
  relationship_fire_inputs,
  crm_version,
  evaluated_at,
  suspension_generation
}
```

Une donnée absente ou inconnue reste inconnue. Elle ne doit jamais être remplacée silencieusement par une valeur permissive.

## 5. Moteur du Feu relationnel

### 5.1 Ordre de décision

1. **Rouge** si une opposition, une permission interdite, une organisation suspendue, une capacité absente ou une donnée
   critique invalide bloque l’action.
2. **Jaune** si une permission, une identité, une correspondance ou une donnée nécessaire doit être vérifiée par un humain.
3. **Vert** uniquement si les entrées requises sont présentes, fraîches, compatibles avec le rôle et autorisées par la
   version du Playbook.
4. **`to_verify`** si le moteur ne peut pas distinguer de façon sûre un cas autorisé d’un cas bloqué.

### 5.2 Sortie minimale

```text
FireDecision {
  level: red | yellow | green | to_verify,
  reason_codes: [closed enum],
  next_action: closed enum,
  blocking_fields: [closed field names],
  evaluated_rule_version,
  evaluated_at
}
```

Le moteur ne renvoie jamais une instruction libre pouvant être exécutée comme une commande. Il renvoie une décision et une
prochaine étape contrôlée.

## 6. Prévol et fidélité future

Le Prévol doit présenter :

- la demande ou l’intention structurée ;
- le périmètre et le volume estimés ;
- le niveau du Feu et ses raisons ;
- les objets CRM concernés, sans les modifier ;
- les tâches ou brouillons proposés, explicitement marqués comme non créés ;
- les contrôles d’autorisation et de suspension observés ;
- l’expiration et les conditions d’invalidation.

Avant toute exécution future, le serveur recalculera :

- l’identité et la capacité de l’acteur ;
- l’organisation et la suspension ;
- la version du Playbook et du ruleset ;
- la fraîcheur des objets CRM ;
- l’empreinte des données et le niveau du Feu.

Toute divergence rend le Prévol obsolète et impose une nouvelle évaluation. Aucun retry aveugle n’est autorisé.

## 7. Repli et cas limites

| Situation | Réponse S4-1 |
|---|---|
| Intention non interprétable | Demander une clarification ; aucune action proposée comme certaine |
| Donnée CRM modifiée après Prévol | Invalider le Prévol et recalculer |
| Permission inconnue | Jaune ou `to_verify`, jamais Vert |
| Règle active modifiée | Nouvelle version, ancien Prévol obsolète |
| Suspension activée | Refus fermé et événement de décision |
| Timeout ou erreur du moteur | `to_verify`, aucune écriture |
| Tentative de commande directe par l’IA | Rejetée par le contrat de sortie |

## 8. Plan de preuves

| Preuve | Scénario | Oracle | Niveau visé |
|---|---|---|---|
| `PV-DATA-02` | Modifier une version active | Version immuable, nouvelle version distincte | D2 puis D3 |
| `PV-RULE-01` | Construire le contexte | Tous les champs canoniques présents, aucun cross-tenant | D2 puis D3 |
| `PV-RULE-02` | Rouge, Jaune, Vert, inconnu | Priorité correcte et raisons structurées | D2 puis D3 |
| `PV-RULE-03` | Comparer Prévol et exécution | Même version, même règle, résultat identique | D2 puis D3 |
| `PV-RULE-04` | Modifier une donnée après Prévol | Prévol invalidé et nouvelle évaluation | D2 puis D3 |
| `PV-IDEM-02` | Timeout après effet potentiel | `to_verify`, aucune reprise aveugle | D3 |
| `PV-UX-02` | Phrase → plan → Prévol | Périmètre et absence d’effet visibles | D2 puis D3 |

## 9. DoR et DoD

### Definition of Ready

- S4-0 clôturée pour son périmètre de préparation ;
- `RF-AUT-2.1` et les versions de Playbook accessibles ;
- fixtures synthétiques S4-0 disponibles ;
- propriétaires Produit, Ingénierie, QA et Sécurité confirmés ;
- environnement isolé confirmé ;
- aucun besoin d’IA réelle pour exécuter le noyau déterministe.

### Definition of Done de la définition

- les quatre contrats `AUT-4101` à `AUT-4104` sont versionnés ;
- les tables de décision du Feu sont fermées et testables ;
- le schéma du Prévol et ses invalidations sont documentés ;
- les oracles et jeux de cas sont reliés aux preuves `PV-*` ;
- les limites sans effet sont répétées dans l’API et l’interface ;
- la revue Sécurité confirme qu’aucune capacité n’est implicitement octroyée.

La réalisation runtime du domaine S4-1 est maintenant effectuée et testée en isolation. La réalisation applicative
intégrée (API, persistance, worker et garde avant effet) nécessitera une autorisation distincte ; la Porte 4 reste la
porte de construction.

## 10. Décision et suite

La réalisation isolée S4-1 est acceptée comme noyau runtime sans effet. La définition de [S4-2 — Nouveau prospect et
tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) prolonge ce noyau sans ouvrir son intégration. Aucun effet CRM
n’est déduit de cette réalisation.

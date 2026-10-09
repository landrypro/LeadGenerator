# S4-7 — Levée des réserves et réouverture de la Porte 4

> **Statut : ACTIVE SOUS RÉSERVES — Porte 4 `GO avec réserves` ; implémentation `P4-Lite` sous flags désactivés.**  
> **Date d'ouverture :** 1er octobre 2026  
> **Dépendances :** S4-0 à S4-6, T1 à T4, `RF-AUT-2.1` et le verdict `GO avec réserves` de Porte 4  
> **Backlog :** `AUT-4701` à `AUT-4708`  
> **Sortie attendue :** registre de réserves et preuves d'activation/élargissement de `P4-Lite`

## 1. Décision d'ouverture

Le commanditaire ouvre S4-7 afin de suivre les réserves de la Porte 4. Cette autorisation n'élargit pas le `GO avec
réserves` au-delà de `P4-Lite` et ne permet ni activation client ni production.

S4-7 peut préparer la gouvernance, l'environnement isolé, les fixtures, les procédures et les preuves. La Porte 4
autorise désormais les routes, migrations réversibles et worker contrôlé nécessaires à `P4-Lite`, sous flags désactivés
par défaut et sans production. Un connecteur, un appel IA réel ou un déploiement restent exclus de cette autorisation.

## 2. Objectifs

S4-7 doit répondre à cinq questions avant toute activation ou tout élargissement de `P4-Lite` :

1. l'équipe, les propriétaires et la capacité sont-ils réellement disponibles ?
2. l'environnement isolé permet-il de rejouer les scénarios sans données client ?
3. les preuves D2/D3 critiques peuvent-elles être produites et reproduites ?
4. les contrôles d'arrêt, d'idempotence, de reprise et de rollback sont-ils démontrés ?
5. le fournisseur IA est-il arrêté et les réserves de quotas, rétention, risques et approbations sont-elles explicitement suivies ?

## 3. Périmètre

### Inclus

- confirmation des propriétaires Produit, Backend, QA, Sécurité, Données, Plateforme et Exploitation ;
- révision des estimations, dépendances, capacité et séquencement des tranches ;
- réservation d'un environnement isolé avec PostgreSQL/RLS, Redis, worker contrôlé et faux fournisseurs ;
- exécution de preuves D2/D3 sur fixtures synthétiques, en priorité Feu/Prévol, idempotence, garde et exceptions ;
- répétition des scénarios de suspension, reprise, concurrence, `to_verify`, réconciliation et rollback ;
- décision sur fournisseur IA, quotas, coûts, non-entraînement, résidence et politique de rétention ;
- inspection de l'audit et de la télémétrie sans phrases libres ni PII inutile ;
- mise à jour du registre des risques et assemblage du dossier de réouverture de Porte 4.

### Exclus

- toute donnée client ou migration de production ; les migrations réversibles sont admises en environnement isolé ;
- toute communication externe, envoi ou changement silencieux du pipeline ;
- toute activation d'un Playbook ou d'un connecteur réel ;
- tout appel à un fournisseur IA réel avant décision et garde dédiée ;
- toute mise en production ou session PME, maintenue post-production ;
- la preuve Azure 4.6, maintenue à la fin de la Phase 5.

## 4. Volets de travail

| Volet | Résultat attendu | Sortie de contrôle |
|---|---|---|
| Gouvernance | owners, disponibilité, estimation, dépendances et approbateurs confirmés | `PV-S47-GOV-01` |
| Environnement | environnement isolé reproductible et réinitialisable | `PV-S47-ENV-01` |
| Preuves déterministes | D2/D3 Feu, Prévol, garde, idempotence et exceptions | `PV-S47-RUN-01` |
| Résilience | suspension, reprise, concurrence, timeout, `to_verify` et rollback | `PV-S47-RES-01` |
| IA et données | OpenAI cible choisi ; faux fournisseur, minimisation et limites locales IMP-A5 confirmés ; contrat, rétention, prix et quotas OpenAI restent réservés | `PV-S47-AI-01` |
| Observabilité | corrélation, audit, métriques et alertes inspectables | `PV-S47-OBS-01` |
| Porte 4 | registre des risques, réserves, signatures et tranches autorisables | `PV-S47-GATE-01` |

## 5. Backlog de réalisation

| ID | Priorité | Action | Critère d'acceptation | Preuve |
|---|---:|---|---|---|
| `AUT-4701` | P0 | Nommer les propriétaires et confirmer la capacité | Chaque réserve a un owner, une disponibilité et une date cible | `PV-S47-GOV-01` |
| `AUT-4702` | P0 | Réserver l'environnement isolé | PostgreSQL/RLS, Redis, worker contrôlé et faux fournisseurs réinitialisables | `PV-S47-ENV-01` |
| `AUT-4703` | P0 | Exécuter les scénarios déterministes prioritaires | Feu/Prévol, version, garde fraîche et idempotence passent les oracles | `PV-S47-RUN-01` |
| `AUT-4704` | P0 | Exécuter les scénarios d'exception | Doublon, responsable indisponible et `to_verify` restent sans effet silencieux | `PV-S47-RUN-02` |
| `AUT-4705` | P0 | Répéter arrêt, reprise et rollback | Suspension, redémarrage, réconciliation et rollback ne créent aucun doublon | `PV-S47-RES-01` |
| `AUT-4706` | P0 | Arrêter le fournisseur IA et suivre les réserves associées | OpenAI cible enregistré ; fake et limites locales validés ; contrat, rétention, prix et quotas OpenAI restent à valider | `PV-S47-AI-01` |
| `AUT-4707` | P1 | Inspecter audit, télémétrie et risques | Corrélation reconstituable, PII minimisée, risques mis à jour | `PV-S47-OBS-01` |
| `AUT-4708` | P0 | Réassembler et soumettre Porte 4 | Tranches autorisables, limites et verdict sont explicitement listés | `PV-S47-GATE-01` |

### Modalités IMP-A6 confirmées le 4 octobre 2026

La production de `PV-S47-RUN-01`, `PV-S47-RUN-02`, `PV-S47-RES-01`, `PV-S47-OBS-01` et `PV-S47-AI-01` s'effectue
localement sur données synthétiques. Les pannes restent des injections test-only ; les rapports minimisés sont
conservés sous `test-results/automation-imp-a6/`. La clôture requiert verrou vert et revue Produit/QA/Sécurité, mais
ne constitue pas une activation de `P4-Lite`, un staging, une preuve D4, ni une autorisation OpenAI réelle.

La construction IMP-A6 du 4 octobre 2026 fournit les tests et le générateur de dossier nécessaires à ces preuves.
Le verrou complet est vert, le rapport D3 minimisé est produit et la décision formelle est un `GO avec réserves`.
`AUT-4703..4708` continuent de suivre les réserves D4, capacité et OpenAI réel, qui bloquent toute activation,
staging ou production.

Le [registre des réserves de Porte 4](./REGISTRE_RESERVES_PORTE_4.md) précise pour chaque réserve active son
responsable proposé, son déclencheur, sa preuve de levée et l'effet qu'elle bloque.

## 6. Règle de preuve

Une preuve D2 est un test ou une procédure effectivement disponible sur l'environnement isolé. Une preuve D3 est un
résultat daté, versionné, reproductible et associé à une fixture, une configuration et un oracle. Les documents S4-0 à
S4-6 restent des preuves D1 lorsqu'ils décrivent seulement un scénario.

Chaque résultat S4-7 doit conserver :

- l'identifiant de fixture et son tenant ;
- la version de la règle, du schéma et du faux fournisseur ;
- l'identifiant de corrélation, l'horodatage et l'oracle ;
- l'état initial et final, y compris `blocked`, `needs_review` ou `to_verify` ;
- la preuve d'absence d'effet CRM ou d'envoi externe.

## 7. Contraintes d'exécution isolée

Le parcours de test est :

~~~mermaid
flowchart LR
    A[Réserve identifiée] --> B[Owner et critère confirmé]
    B --> C[Fixture synthétique + tenant isolé]
    C --> D[Test D2]
    D --> E{Oracle satisfait ?}
    E -->|Non| F[Corriger ou maintenir la réserve]
    E -->|Oui| G[Test reproductible D3]
    G --> H[Inspection audit + télémétrie]
    H --> I[Dossier de réouverture Porte 4]
~~~

Le reset de l'environnement doit être possible entre deux scénarios. Tout résultat ambigu est conservé en
`to_verify` et remis à une résolution humaine ; aucun retry aveugle n'est accepté. Les tests de garde doivent être
rejoués après retrait d'une capacité, modification du Feu ou suspension globale.

## 8. Critères de sortie S4-7

S4-7 est terminée lorsque :

- `AUT-4701` à `AUT-4708` ont une preuve ou une réserve explicitement acceptée ;
- les propriétaires, estimations, dépendances et approbateurs sont confirmés ;
- l'environnement isolé est réinitialisable et ses faux fournisseurs sont documentés ;
- les scénarios D2/D3 critiques sont reproduits sans effet CRM, envoi ni fuite inter-tenant ;
- suspension, reprise, idempotence, concurrence et rollback sont démontrés ;
- le fournisseur IA et la rétention ont une décision signée, ou l'IA reste explicitement hors périmètre ;
- le registre des risques indique les réserves restantes et leur impact ;
- le dossier Porte 4 contient une liste précise des tranches constructibles et des effets interdits.

## 9. Décision de suivi

S4-7 ne prononce pas elle-même l'élargissement de la tranche. La Porte 4 a rendu un `GO avec réserves` pour `P4-Lite`;
S4-7 qualifie les réserves restantes avant chaque activation ou élargissement :

| Résultat S4-7 | Suite autorisée |
|---|---|
| Toutes les réserves critiques levées | Demander l'élargissement de la tranche par décision explicite |
| Réserves non bloquantes restantes | Continuer `P4-Lite` sous flags désactivés, avec propriétaires et dates |
| Une réserve critique non maîtrisée | Suspendre la tranche concernée et maintenir les autres limites |

Un éventuel `GO` devra commencer par une tranche verticale explicitement bornée, sans envoi externe autonome, avec
mode Préparer, garde fraîche, audit et rollback obligatoires.

## 10. Definition of Ready / Definition of Done

### DoR

- dossier Porte 4 et verdict `GO avec réserves` accessibles ;
- réserves identifiées, propriétaires nommés et critères mesurables ;
- fixtures synthétiques et oracles disponibles ;
- environnement isolé et procédure de reset réservés ;
- aucune donnée client, aucun secret et aucun fournisseur IA réel requis pour démarrer.

### DoD

- rapports `PV-S47-*` versionnés et reliés au backlog ;
- résultats D2/D3 reproductibles ou réserves maintenues explicitement ;
- registre des risques et capacité mis à jour ;
- registre de réserves et décision d'élargissement assemblables ;
- aucun effet CRM, envoi externe ou déploiement produit réalisé par S4-7.

## 11. Décision d'ouverture et suite

La Porte 4 est clôturée avec un `GO avec réserves` pour `P4-Lite`. OpenAI reste le fournisseur choisi pour `AUT-4706`.
Le 3 octobre 2026, le faux fournisseur, la minimisation, la non-persistance et les limites locales d'IMP-A5 ont été
confirmés. Les réserves contractuelles propres à OpenAI réel et les autres réserves restent maintenues dans S4-7 et sont
traitées au fil des tranches. La contre-validation de S4-7,
le dossier [Propositions pour la réouverture de Porte 4](./PROPOSITIONS_PORTE_4_REOUVERTURE.md) et la
[Pré-Phase 5 — Préparation de l'implémentation](./PRE_PHASE_5_IMPLEMENTATION_AUTOMATISATION.md) encadrent ce travail.

### 11.1 Confirmation du commanditaire — 2 octobre 2026

Pour `AUT-4701`, le commanditaire assure les rôles Produit, QA et Sécurité. L'agent d'implémentation assure le
Backend et l'environnement de développement. Cette répartition vaut pour le démarrage de `P4-Lite`; les échéances
de chaque tranche seront ajoutées avec leurs preuves associées.

Pour `AUT-4702`, l'environnement local de développement est autorisé pour les premiers tests, avec données
strictement synthétiques. La base de test et les services locaux existants servent de point de départ; Redis et le
worker contrôlé seront intégrés et vérifiés avant toute preuve qui en dépend. Aucun secret, donnée client, fournisseur
IA réel ni déploiement n'est autorisé par cette confirmation.

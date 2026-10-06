# S4-5 — Playbooks complémentaires et exceptions

> **Statut : CLÔTURÉE POUR DÉFINITION — prescriptions CV-S4-5-01 à CV-S4-5-07 appliquées ; aucun runtime intégré**  
> **Date d’ouverture :** 1er octobre 2026  
> **Dépendances :** [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ; [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ; [S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md) ; [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md)  
> **Backlog :** AUT-4501 à AUT-4506 dans [BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md)  
> **Décision de porte :** Porte 4 `GO avec réserves` limité à `P4-Lite` ; les Playbooks complémentaires et leurs intégrations restent hors périmètre.

## 1. Objet

S4-5 complète le premier parcours Nouveau prospect avec deux recettes guidées :

1. **Proposition en attente** : repérer une opportunité ouverte à l’étape canonique `proposal` qui attend une réponse ou
   une activité au-delà du délai configuré ;
2. **Occasion oubliée** : repérer une opportunité ouverte qui n’a plus d’activité, de prochaine action ou d’échéance
   selon les règles configurées.

Les deux Playbooks proposent une prochaine action explicable. Ils ne déplacent jamais le pipeline, ne ferment jamais une
opportunité et ne relancent jamais un contact sans les contrôles du Feu, des permissions, des approbations et du
Prévol.

S4-5 ferme également le traitement documentaire des quatre exceptions prioritaires : responsable indisponible,
correspondance ambiguë, prospect déjà connu et résultat `to_verify`.

## 2. Portée et limites

Le GO de définition couvre :

- les déclencheurs et périmètres canoniques des deux Playbooks ;
- leurs Prévols, règles de détection, exclusions et actions proposées ;
- le partage du noyau Feu, capacités, suspension et expiration de S4-1 ;
- les cycles de vie et contrats d’exception ;
- les règles de déduplication, de rattachement et de réconciliation ;
- les preuves D1 et les oracles de non-effet.

Il ne couvre pas :

- un calcul ou une modification du pipeline CRM ;
- la fermeture, la conversion ou la réattribution silencieuse d’une opportunité ;
- un envoi courriel, SMS, réseau social ou autre communication ;
- une fusion automatique de fiches ;
- une reprise automatique d’un résultat incertain ;
- une migration, une route active, un worker ou une donnée client réelle.

## 3. Principes communs aux deux Playbooks

1. Le CRM canonique reste la source de vérité pour opportunité, étape, activité, échéance, attente, responsable et
   permission.
2. Un déclencheur système propose une évaluation ; il ne constitue pas une autorisation d’effet.
3. La détection est bornée par organisation, Playbook, version de règles et fenêtre temporelle.
4. Une même opportunité et une même fenêtre de règle ne produisent qu’une proposition active.
5. Toute action future passe par un Prévol, une garde fraîche et, si nécessaire, S4-4.
6. Le Feu Rouge bloque le contact ; le Feu Jaune crée au plus une revue ou une tâche interne ; le Feu Vert permet une
   préparation, jamais un envoi.
7. Une opportunité récente, fermée, en attente convenue ou déjà traitée est exclue sans changer son état CRM.
8. Un résultat incertain devient `to_verify` et n’est jamais transformé en succès par un retry aveugle.
9. Une suspension de Playbook ou d’organisation gagne sur toute proposition antérieure.
10. La sortie de V1 est une proposition lisible, une tâche interne admissible, un brouillon soumis à S4-4 ou une
    exception. Le pipeline reste inchangé.

## 4. Playbook « Proposition en attente »

### 4.1 Déclencheur et périmètre

Le Playbook examine les opportunités canoniques qui respectent simultanément :

- organisation résolue côté serveur ;
- opportunité ouverte à l’étape canonique `proposal` ;
- absence de réponse ou d’activité qualifiante depuis le délai de la version active ;
- absence de fermeture, de perte, de conversion ou de suppression ;
- absence de prochaine action équivalente déjà ouverte ;
- absence de fenêtre d’attente ou de fréquence qui interdit une nouvelle proposition ;
- Playbook actif, non suspendu et Prévol courant.

Le délai d’inactivité, les étapes admissibles, la fréquence et les règles de réponse sont versionnés. Aucun seuil
implicite n’est inventé par l’IA ou par l’interface.

### 4.2 Prévol

Le Prévol produit une fiche par opportunité candidate :

- référence canonique et organisation ;
- étape, montant et dates utiles si leur lecture est autorisée ;
- dernière activité qualifiante et date de réponse ;
- responsable actif ou exception ;
- prochaine action existante et échéance ;
- Feu par canal et raisons structurées ;
- suspension, expiration, version Playbook et ruleset ;
- proposition limitée : tâche de suivi, revue humaine ou brouillon admissible.

Le Prévol ne crée pas de tâche, de brouillon, d’activité ou de modification d’étape. Une absence de donnée ne devient
jamais une preuve de silence : elle produit `needs_review` ou une exception.

### 4.3 Résultats admissibles

| Résultat du Feu | Proposition | Interdit |
|---|---|---|
| Vert | Tâche de suivi et brouillon éventuellement préparable après S4-4 | Envoi ou déplacement de pipeline |
| Jaune | Tâche interne de vérification de la proposition | Brouillon de contact et relance |
| Rouge | Blocage expliqué et revue humaine | Tout contact, tâche de relance ou changement CRM |
| Inconnu / données insuffisantes | Exception ou `needs_review` | Déduire une absence de réponse |

Une proposition déjà consommée pour la même identité de règle est rattachée à l’historique et ne crée pas de doublon.

## 5. Playbook « Occasion oubliée »

### 5.1 Déclencheur et périmètre

Le Playbook examine les opportunités canoniques qui respectent simultanément :

- organisation et portée objet résolues côté serveur ;
- opportunité encore ouverte et non suspendue ;
- aucune activité récente selon la fenêtre de la règle ;
- aucune prochaine action ou échéance valide, ou échéance dépassée selon la politique ;
- aucune attente convenue, opposition ou exclusion configurée ;
- aucune proposition de revue active déjà ouverte.

Il ne déduit pas qu’une opportunité est oubliée à partir de son montant ou d’un champ libre. Les dates et activités
doivent provenir des objets CRM canoniques.

### 5.2 Prévol et résultat

Le Prévol présente :

- la référence de l’opportunité et la dernière preuve d’activité ;
- l’étape et la raison de détection ;
- les exclusions vérifiées ;
- le responsable et sa capacité ;
- la prochaine action manquante ou échue ;
- Feu et permissions, uniquement pour une éventuelle action de contact ;
- une tâche de revue humaine et sa date suggérée ;
- l’expiration du Prévol et la version des règles.

Le résultat normal est une revue humaine. Aucune fermeture, perte, réouverture, changement d’étape, attribution ou
communication n’est exécuté par ce Playbook.

## 6. Noyau de garde commun

### 6.1 Contexte d’évaluation

Les deux recettes utilisent le même contexte conceptuel :

~~~text
PlaybookEvaluationContext {
  organization_id_server,
  actor_or_system_principal,
  playbook_code,
  playbook_version,
  ruleset_version,
  opportunity_reference,
  snapshot_version,
  snapshot_fingerprint,
  relationship_fire_by_channel,
  crm_capabilities,
  suspension_generation,
  idempotency_window
}
~~~

Le contexte ne contient que les champs nécessaires à l’évaluation. Les notes libres, messages, secrets et sources brutes
ne deviennent pas des instructions et ne sont pas copiés dans l’audit.

### 6.2 Double garde

La garde est vérifiée à l’admission de la proposition, puis juste avant toute préparation de tâche ou de brouillon :

~~~text
tenant_same
playbook_active_and_version_current
organization_and_object_scope_current
crm_capability_current
responsible_active_or_exception_open
snapshot_current
relationship_fire_recomputed
waiting_and_frequency_rules_current
suspension_generation_current
identity_not_already_handled
~~~

Une différence de snapshot, de règle, de permission, de suspension ou de capacité invalide le Prévol. Une approbation
S4-4 antérieure ne suffit jamais à réhabiliter une proposition modifiée.

## 7. Exceptions prioritaires

### 7.1 Responsable indisponible — AUT-4503

Si le responsable est absent, inactif, hors organisation ou privé de capacité :

- le Playbook ouvre une exception `owner_unavailable` ;
- aucun transfert aléatoire et aucune modification silencieuse du propriétaire CRM ne sont effectués ;
- l’interface propose un membre actif autorisé ou un report ;
- la résolution exige un nouveau Prévol et une relecture des règles ;
- le Feu relationnel reste inchangé.

### 7.2 Correspondance ambiguë — AUT-4504

Si plusieurs opportunités ou prospects peuvent correspondre :

- l’entrée est mise en quarantaine ;
- aucun nouveau prospect, tâche, brouillon ou proposition de suivi n’est créé ;
- les candidats sont présentés par références minimales et critères de correspondance ;
- une décision humaine de rattachement ou d’abandon est exigée ;
- toute fusion reste interdite par défaut et doit être auditée dans le CRM canonique.

### 7.3 Prospect déjà connu — AUT-4505

Si la clé fonctionnelle ou la correspondance exacte identifie un prospect existant :

- l’entrée est rattachée à la fiche canonique ;
- aucun second prospect ni tâche de Nouveau prospect n’est créé ;
- la provenance et la date de rattachement restent consultables ;
- le Playbook peut continuer vers une revue seulement si son identité de règle est nouvelle et admissible ;
- une correspondance non exacte est traitée comme ambiguë, jamais comme un rattachement automatique.

### 7.4 Résultat incertain — AUT-4506

Si un timeout, bail perdu ou résultat CRM ambigu survient :

- l’état devient `to_verify` ;
- la clé d’identité, la corrélation, la version et l’étape sont conservées ;
- le serveur recherche d’abord un résultat existant ;
- aucune nouvelle tâche, proposition, brouillon ou notification n’est créée avant résolution ;
- la résolution humaine ou idempotente produit un état terminal explicable.

## 8. Cycles de vie

### 8.1 Évaluation d’un Playbook

~~~mermaid
stateDiagram-v2
    [*] --> queued
    queued --> evaluating: déclencheur admis
    evaluating --> prepared: Prévol construit sans effet
    evaluating --> needs_review: preuve manquante
    evaluating --> blocked: Feu Rouge ou capacité absente
    evaluating --> exception: incohérence ou responsable indisponible
    evaluating --> to_verify: résultat ambigu
    evaluating --> cancelled: suspension ou arrêt
    prepared --> completed: proposition consommée sans nouvel effet
    prepared --> invalidated: snapshot ou règle modifiés
    needs_review --> prepared: décision humaine + nouveau Prévol
    exception --> prepared: résolution + nouveau Prévol
    to_verify --> completed: résultat confirmé
    to_verify --> exception: résolution impossible
~~~

`completed` signifie que la proposition ou la revue a été enregistrée comme traitée ; il ne signifie pas qu’un message
est envoyé ou qu’une opportunité est modifiée.

### 8.2 Exception

~~~mermaid
stateDiagram-v2
    [*] --> open
    open --> in_progress: prise en charge humaine
    in_progress --> resolved: preuve ou rattachement confirmé
    in_progress --> abandoned: décision d’abandon
    resolved --> [*]
    abandoned --> [*]
~~~

Une résolution ne relance pas aveuglément la recette. Elle exige une nouvelle évaluation, une nouvelle identité
d’idempotence ou un rattachement canonique explicite.

## 9. Contrats conceptuels

Ces contrats seront implémentés seulement après la Porte 4. Les champs inconnus sont refusés et l’organisation est issue
du contexte serveur.

| Commande | Entrée minimale | Sortie D1 | Refus principal |
|---|---|---|---|
| evaluate_pending_proposal | Playbook/version, fenêtre, portée, snapshot, clé | Prévol et proposition par opportunité | playbook_suspended, snapshot_stale |
| evaluate_forgotten_opportunity | Playbook/version, fenêtre, portée, snapshot, clé | Prévol et tâche de revue proposée | insufficient_evidence, playbook_suspended |
| resolve_owner_exception | exception, membre actif ou report, version | Exception résolue ou nouvelle vérification | member_inactive, version_conflict |
| resolve_match_exception | exception, candidat canonique, décision | Rattachement ou quarantaine maintenue | ambiguous_match, capability_missing |
| reconcile_to_verify | corrélation, clé, référence, version | Résultat existant ou exception | effect_uncertain |

Les événements prévus sont :

- `automation.playbook.proposal_pending.detected.v1` ;
- `automation.playbook.forgotten_opportunity.detected.v1` ;
- `automation.exception.owner_unavailable.opened.v1` ;
- `automation.exception.ambiguous_match.opened.v1` ;
- `automation.exception.existing_prospect.resolved.v1` ;
- `automation.execution.to_verify.v1` ;
- `automation.exception.resolved.v1`.

Ils contiennent des codes, versions, références canoniques, empreintes, compteurs et corrélations minimales, jamais une
copie de note, de message ou de données sociales brutes.

## 10. UX et présentation PME

Les deux Playbooks sont consultables dans `Playbooks`, tandis que les cas bloqués ou ambigus apparaissent dans
`Entrées et exceptions`. Une nouvelle intention continue de passer par l’Assistant d’`Aujourd’hui` ; aucun second
champ libre n’est ajouté.

Chaque carte doit montrer :

- pourquoi l’opportunité est proposée ;
- les preuves et la fenêtre de détection ;
- le responsable et la prochaine action ;
- Feu, permissions et limites ;
- ce qui n’a pas été fait ;
- l’état du Prévol et sa date d’expiration ;
- l’action autorisée : voir le Prévol, préparer une tâche de revue ou examiner l’exception.

Les libellés **Fermer l’opportunité**, **Envoyer maintenant** et **Réattribuer automatiquement** sont exclus des
actions proposées par S4-5.

## 11. Audit et télémétrie

L’audit minimal conserve : organisation, Playbook/version, référence canonique, fenêtre, décision, reason_code,
responsable, corrélation, empreinte du snapshot, résultat d’exception et date d’expiration.

Sont exclus des journaux : notes CRM, contenu de message, coordonnées complètes, phrase libre, données sociales brutes,
secret, preuve brute de permission et copie de profil.

Les métriques agrégées couvrent : opportunités détectées, propositions ignorées par exclusion, revues préparées,
doublons, quarantaines, responsables indisponibles, états `to_verify`, délais de résolution et suspensions.

## 12. Preuves et critères d’acceptation

| Preuve | Scénario | Oracle | Niveau actuel |
|---|---|---|---|
| PV-FUN-05 | Proposition en attente admissible | Suivi proposé, pipeline inchangé, aucune relance automatique | D1 défini |
| PV-FUN-06 | Occasion oubliée admissible | Revue humaine proposée, aucune fermeture ou transition | D1 défini |
| PV-EXC-01 | Responsable indisponible | Exception ouverte, aucun transfert aléatoire | D1 défini |
| PV-EXC-02 | Correspondance ambiguë | Quarantaine, aucune création ni fusion | D1 défini |
| PV-EXC-03 | Prospect déjà connu | Rattachement canonique, zéro doublon | D1 défini |
| PV-EXC-04 | Réconciliation `to_verify` | Recherche par clé, un seul résultat terminal, pas de retry aveugle | D1 défini |
| PV-RULE-05 | Exclusions et attente | Fermé, récent, attendu ou déjà traité non proposé | D1 défini |
| PV-SEC-05 | Suspension et capacité | Garde bloquée après révocation ou suspension | D1 défini |
| PV-OBS-05 | Traces minimisées | Aucun contenu sensible ou donnée sociale brute | D1 défini |

Les preuves D2/D3 nécessitent un environnement isolé, des fixtures multi-tenant et l’exécution après la Porte 4. Aucun
résultat D1 n’est présenté comme un test serveur ou une action réalisée.

## 13. Definition of Ready et Definition of Done

### Definition of Ready

- S4-1, S4-2, S4-3 et S4-4 sont figées pour leur définition ;
- étapes canoniques, activités, dates, attentes et propriétaires CRM sont identifiés ;
- fenêtres d’inactivité, fréquence et exclusions possèdent une version de règle ;
- fixtures synthétiques couvrent opportunité récente, fermée, attendue, doublon, ambiguïté et timeout ;
- responsables Produit, CRM, Sécurité, Données et QA sont nommés pour la future preuve ;
- aucun connecteur ni fournisseur externe réel n’est requis.

### Definition of Done de la définition

- AUT-4501 à AUT-4506 ont un déclencheur, une règle, un résultat, une exception et une preuve ;
- les deux Prévols partagent le noyau S4-1 et ne modifient jamais le pipeline ;
- les quatre exceptions ont un cycle, une résolution et une règle d’idempotence ;
- les capacités et la double garde sont explicites ;
- `to_verify` n’a jamais de retry aveugle ;
- audit et télémétrie sont minimisés ;
- S4-6 et la Porte 4 restent nécessaires avant toute intégration.

## 14. Risques et décisions ouvertes

| ID | Risque ou décision | Réponse avant intégration |
|---|---|---|
| S4-5-R01 | Fausse occasion oubliée faute d’activité importée | Exigence de preuve canonique ou `needs_review` |
| S4-5-R02 | Relance trop fréquente d’une proposition | Fenêtre de fréquence, identité idempotente et tâche équivalente |
| S4-5-R03 | Pipeline modifié indirectement | Commandes V1 sans transition ni fermeture |
| S4-5-R04 | Responsable inactif réattribué au hasard | Exception obligatoire et garde fraîche |
| S4-5-R05 | Doublon fusionné silencieusement | Quarantaine et décision CRM explicite |
| S4-5-R06 | `to_verify` rejoué après effet possible | Réconciliation par clé et corrélation |
| S4-5-R07 | Données de source prises pour preuve | Sources non fiables, lecture canonique obligatoire |
| S4-5-R08 | Surcharge de propositions pour une PME | Borne de volume, regroupement et suspension |

## 15. Application des prescriptions

| Prescription | Application dans la définition | Preuve attendue après Porte 4 |
|---|---|---|
| CV-S4-5-01 | Déclencheurs, exclusions et données manquantes sont déterministes ; une absence ou contradiction devient `needs_review`. | PV-FUN-05, PV-FUN-06, PV-RULE-05 |
| CV-S4-5-02 | Clé d'idempotence, fenêtre de fréquence et unicité de proposition/tâche sont obligatoires. | PV-SEC-05, PV-OBS-05 |
| CV-S4-5-03 | Les commandes S4-5 sont sans effet pipeline, fermeture, conversion, fusion, réattribution silencieuse ou communication. | PV-FUN-05, PV-FUN-06, PV-SEC-05 |
| CV-S4-5-04 | Responsable actif, même organisation, capacité et résolution humaine sont requis ; aucune réattribution aléatoire. | PV-EXC-01, PV-SEC-05 |
| CV-S4-5-05 | Le doublon exact est rattaché ; l'ambiguïté est mise en quarantaine sans fusion ni création. | PV-EXC-02, PV-EXC-03 |
| CV-S4-5-06 | `to_verify` impose une réconciliation par clé/corrélation et interdit le retry aveugle. | PV-EXC-04, PV-OBS-05 |
| CV-S4-5-07 | Tenant, organisation, rôle, volume, génération de suspension et snapshot bornent chaque évaluation. | PV-SEC-05, PV-OBS-05 |

## 16. Décision et suite

S4-5 est **clôturée pour définition** : les prescriptions CV-S4-5-01 à CV-S4-5-07 sont appliquées au niveau
contractuel et leur traçabilité est consignée dans [CONTRE-VALIDATION-S4-5](./CONTRE_VALIDATION_S4_5.md).

Cette clôture ne prononce pas la Porte 4. Aucun runtime, worker, connecteur, modification du pipeline, effet CRM,
envoi externe ou donnée client réelle n'est autorisé. Les preuves D2/D3 seront produites lors de l'implémentation
isolée après décision de Porte 4.

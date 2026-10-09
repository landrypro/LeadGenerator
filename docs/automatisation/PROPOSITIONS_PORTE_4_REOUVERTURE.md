# Propositions pour la réouverture de la Porte 4

> **Statut :** recommandations retenues ; Porte 4 clôturée avec `GO avec réserves` pour la préparation `P4-Lite`.  
> **Référence :** [Porte 4 — Prêt à construire](./PORTE_4_PRET_A_CONSTRUIRE.md) et [S4-7 — Levée des réserves](./S4_7_LEVEE_RESERVES_PORTE_4.md)  
> **Décision IA connue :** OpenAI est le fournisseur cible de `AUT-4706` ; l'appel réel reste interdit.

## 1. Objectif

La réévaluation a abouti à un `GO avec réserves` pour `P4-Lite`. Les réserves restent suivies dans S4-7 et sont traitées
au fil de l'implémentation ; elles ne permettent pas d'élargir implicitement le périmètre ni d'activer un effet externe.

La proposition recommandée est un démarrage **Lite, sans envoi externe et sans autonomie silencieuse**. Elle protège le
socle CRM existant, facilite l'adoption PME et permet de démontrer la valeur du point d'entrée IA sans ouvrir tout le
périmètre Automation.

## 2. Proposition de tranche initiale

### Option recommandée — `P4-Lite`

Autoriser uniquement une tranche verticale composée de :

- point d'entrée IA unique dans `Aujourd'hui` ;
- interprétation vers une intention structurée et fermée ;
- calcul déterministe du Feu et génération d'un Prévol ;
- Playbook `Nouveau prospect` sur source manuelle, Google et CSV synthétique ;
- préparation d'une tâche CRM interne, sans envoi externe ;
- approbation humaine obligatoire avant tout effet ;
- audit minimal et Passeport explicable ;
- suspension globale et retour à l'état sûr.

Restent hors tranche : appel OpenAI réel, LinkedIn/Facebook autonomes, connecteurs d'envoi, réattribution automatique,
fermeture d'opportunité et modification silencieuse du pipeline.

### Options écartées pour la première tranche

| Option | Pourquoi elle est écartée maintenant |
|---|---|
| Tout le périmètre Automation | Trop de chemins d'effets et de preuves à produire en une seule décision. |
| IA réelle dès le premier déploiement | Ajoute coût, rétention, latence, conformité et dépendance fournisseur avant validation du noyau. |
| Playbooks complémentaires immédiatement | `Proposition en attente` et `Occasion oubliée` augmentent les exceptions avant preuve du premier parcours. |
| Connecteurs sociaux autonomes | Risques de permissions, limites API et conformité ; à traiter comme tranche séparée. |

## 3. Propositions par élément de Porte 4

| Élément de porte | Proposition recommandée | Preuve attendue | Décision proposée |
|---|---|---|---|
| Périmètre | `P4-Lite`, un seul parcours vertical et zéro envoi | Matrice RF-AUT-2.1 → backlog → oracle | Accepter |
| Propriétaires | Produit, Backend, QA, Sécurité, Données et Exploitation nommés avant exécution | `PV-S47-GOV-01` | Bloquant si absent |
| Capacité | Planifier une tranche courte avec réserve de reprise et revue quotidienne des exceptions | estimation signée + charge observée | Accepter sous réserve |
| Environnement | PostgreSQL/RLS, Redis, worker contrôlé, faux fournisseur et reset automatique | `PV-S47-ENV-01` | Bloquant si absent |
| Données | Fixtures synthétiques multi-tenant, aucun secret ni PII réelle | `PV-DATA-03` / `PV-S47-RUN-*` | Accepter |
| Feu et Prévol | Même version de règle au Prévol et à la garde fraîche | `PV-RULE-02..04`, `PV-S47-RUN-01` | Bloquant si divergent |
| Idempotence | Clé par intention, objet, tenant et version ; rejeu sans doublon | `PV-IDEM-01..03` | Bloquant |
| IA | OpenAI derrière un port fermé, faux fournisseur pour les tests, schéma strict et repli local | `PV-S47-AI-01`, `PV-AI-01..06` | OpenAI choisi, activation différée |
| Capacités | Vérification à la demande puis juste avant chaque effet | `PV-SEC-01..03` | Bloquant |
| Approbation | Approbation liée à une empreinte de brouillon et invalidée à toute modification matérielle | `PV-APP-01..03` | Bloquant |
| Résilience | `to_verify`, reprise bornée, suspension générationnelle et rollback | `PV-S47-RES-01`, `PV-OPS-02..03` | Bloquant |
| Observabilité | Corrélation, état, version, Feu, garde et acteur ; aucune phrase libre dans les logs | `PV-S47-OBS-01` | Accepter sous réserve |
| Déploiement | Feature flag désactivé par défaut, organisation pilote, arrêt immédiat | `PV-OPS-01..03` | Accepter sous réserve |
| Production | Pas de production générale ; pilote fermé et réversible uniquement après verdict positif | rapport de porte | Interdit avant verdict |

## 4. Proposition de décision IA OpenAI

OpenAI est retenu comme fournisseur cible pour `AUT-4706`, mais cette décision ne vaut pas autorisation d'appel réel.
Avant activation, il faut encore confirmer :

1. modèle et version explicitement autorisés ;
2. pays de traitement et conditions de résidence ;
3. absence d'entraînement sur les données transmises selon le contrat retenu ;
4. durée de conservation et procédure de suppression ;
5. quotas, budget par organisation et comportement en dépassement ;
6. timeout, circuit ouvert, repli local et faux fournisseur ;
7. filtrage des données envoyées et absence de secrets/PII inutile ;
8. journaux techniques minimisés et corrélés sans phrase libre.

La recommandation est donc : **OpenAI en port désactivé par défaut, faux fournisseur pour toute validation initiale,
activation réelle uniquement après preuve et décision dédiée**.

## 5. Séquence de preuves proposée

~~~mermaid
flowchart LR
    A[Réouverture Porte 4] --> B[Owners + capacité]
    B --> C[Environnement isolé]
    C --> D[Feu + Prévol]
    D --> E[Nouveau prospect + tâche interne]
    E --> F[Idempotence + garde fraîche]
    F --> G[Exceptions + to_verify]
    G --> H[Suspension + rollback]
    H --> I[Audit + télémétrie]
    I --> J[Verdict limité]
~~~

Ordre proposé :

1. confirmer les owners, la capacité et la tranche `P4-Lite` ;
2. réinitialiser l'environnement et exécuter les fixtures multi-tenant ;
3. produire les preuves Feu/Prévol et tâche interne sans effet externe ;
4. injecter rejeu, concurrence, permission retirée, timeout et suspension ;
5. vérifier audit, corrélation, minimisation et rollback ;
6. soumettre uniquement les preuves obtenues au nouveau comité de Porte 4.

## 6. Verdict retenu

| Verdict | Portée autorisée |
|---|---|
| **`GO avec réserves`** | Préparer et implémenter `P4-Lite`, sous flags désactivés, sans effet externe, appel OpenAI réel ou production. |

Le verdict cite `P4-Lite` comme seule tranche autorisée. Les preuves exactes, les versions, les tenants de test et les
effets explicitement interdits restent obligatoires avant toute activation ou extension.

## 7. Recommandation finale

La meilleure option pour Marketteo est :

> **Préparer et implémenter `P4-Lite`, conserver OpenAI derrière un port désactivé, démontrer d'abord le noyau
> déterministe et la tâche interne, puis élargir par tranches uniquement après preuves.**

Cette option est la plus compatible avec le socle des Phases 1 à 4.6, la promesse Lite PME et les règles de confiance
déjà figées.

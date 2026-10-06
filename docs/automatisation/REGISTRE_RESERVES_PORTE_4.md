# Registre des réserves — Porte 4

> **Statut :** actif après la décision Porte 4 du 4 octobre 2026 : `GO avec réserves`.
>
> **Décision de référence :** les preuves D3 locales d'IMP-A6 et le verrou qualité sont acceptés. La poursuite reste
> limitée aux flags désactivés, aux données synthétiques et à l'absence d'effet externe. Les réserves ci-dessous
> bloquent l'activation, le staging ou la production selon leur périmètre.

## 1. Règles de suivi

- Une réserve est fermée uniquement lorsque sa preuve attendue est disponible et revue par son responsable.
- Une réserve `bloquante activation` n'empêche pas les tests locaux isolés ; elle interdit toute activation client.
- Une réserve `bloquante staging` interdit également le déploiement dans un environnement de staging.
- Toute anomalie tenant, permission, idempotence, rollback ou exposition de données suspend immédiatement la tranche
  concernée, quel que soit l'état des autres réserves.
- Les dates ci-dessous sont des **propositions** : elles deviennent des engagements seulement après confirmation du
  commanditaire.

## 2. Réserves actives

| ID | Réserve et risque | Statut | Responsable proposé | Échéance / déclencheur proposé | Preuve de levée | Effet bloqué |
|---|---|---|---|---|---|---|
| `R-P4-01` | Capacité et disponibilité : les rôles sont connus, mais les créneaux et la capacité effective ne sont pas datés. | Ouverte | Produit (commanditaire) ; Backend/Environnement en appui | Confirmer une date cible avant le prochain lot Automation ; suggestion : 9 octobre 2026. | `PV-S47-GOV-01` : responsables, disponibilité, estimation et dépendances consignés. | Nouveau lot non borné ; activation. |
| `R-P4-02` | D4 absent : la preuve D3 est locale Docker/WSL ; aucun staging/pilote n'a été observé. | Ouverte | Backend / Environnement | Avant toute demande de staging ou pilote ; aucune date tant que l'environnement n'est pas autorisé. | Exécution reproductible en staging isolé, données synthétiques, journal minimisé et rollback exercé. | Staging, pilote, production. |
| `R-P4-03` | Capacité représentative : aucune mesure de charge ne permet de publier un SLO ou de dimensionner le worker. | Ouverte | Backend / Environnement | Avant D4 ou toute activation ; préparer le protocole dès que la capacité de l'équipe est confirmée. | `PV-CAP-01` : charge, saturation, reprise et seuils acceptés. | Staging, pilote, production. |
| `R-P4-04` | OpenAI réel : le faux fournisseur est validé, mais contrat, résidence, rétention, non-entraînement, prix et quotas restent inconnus. | Ouverte | Produit / Sécurité | Avant toute clé, appel réel ou transmission de données hors du faux fournisseur. | `PV-S47-AI-01` : décision fournisseur, paramètres contractuels, limites, repli et garde validés. | Appel OpenAI réel, données réelles, activation IA. |
| `R-P4-05` | Activation fonctionnelle : aucune recette avec organisation cliente ni autorisation d'activer un flag n'existe. | Ouverte | Produit / QA / Sécurité | Avant toute activation de flag hors test contrôlé. | Recette fonctionnelle signée, revue sécurité, plan de rollback et décision d'activation distincte. | Flag client, effet CRM automatique, production. |
| `R-P4-06` | Observabilité et risques : l'audit D3 est minimisé et corrélable, mais le registre de risques et les alertes d'exploitation ne sont pas validés en staging. | Ouverte | Backend / Environnement ; Sécurité en revue | Avant D4 ou élargissement de périmètre. | `PV-S47-OBS-01` : audit inspecté, métriques sans PII, alertes et risques mis à jour. | Staging, pilote, production. |

## 3. Éléments déjà couverts

| Backlog | État | Référence |
|---|---|---|
| `AUT-4701` — propriétaires | Partiel : rôles confirmés ; disponibilité et date cible restent dans `R-P4-01`. | Présent registre / `PV-S47-GOV-01`. |
| `AUT-4702` — environnement isolé | Couvert pour D3 local seulement ; staging reste `R-P4-02`. | `evidence.json`, `PV-S47-ENV-01`. |
| `AUT-4703` — preuves déterministes | Couvert au niveau D3 local. | `evidence.json` : Feu, Prévol, garde, version et idempotence. |
| `AUT-4704` — exceptions | Couvert au niveau D3 local. | `evidence.json` : doublons, indisponibilité et `to_verify`. |
| `AUT-4705` — résilience et rollback | Couvert au niveau D3 local. | `evidence.json` : suspension, reprise, concurrence et rollback. |
| `AUT-4706` — fournisseur IA | Partiel : OpenAI est cible, faux fournisseur validé ; réserve `R-P4-04`. | `PV-S47-AI-01`. |
| `AUT-4707` — audit, télémétrie, risques | Partiel : audit D3 couvert ; réserve `R-P4-06`. | `PV-S47-OBS-01`. |
| `AUT-4708` — dossier de Porte 4 | Clos : décision `GO avec réserves` enregistrée. | [Porte 4 — Prêt à construire](./PORTE_4_PRET_A_CONSTRUIRE.md). |

## 4. Plan recommandé

1. **Maintenant — fermer le cadrage `R-P4-01`.** Le commanditaire confirme la date de disponibilité Produit/QA/Sécurité
   et la capacité à consacrer aux réserves ; l'équipe Backend/Environnement confirme son créneau. Sans ces dates,
   aucun nouveau lot Automation ne doit être annoncé comme planifié.
2. **Avant tout élargissement — traiter `R-P4-06`, puis `R-P4-03`.** Compléter le registre de risques et le protocole
   de charge local, sans prétendre à une preuve de staging.
3. **Avant une intégration fournisseur — traiter `R-P4-04`.** OpenAI reste un choix cible, jamais une permission
   d'utiliser une clé ou des données réelles.
4. **Avant activation — traiter ensemble `R-P4-02`, `R-P4-03`, `R-P4-05` et `R-P4-06`.** Une décision d'activation
   séparée est obligatoire, même si toutes les preuves locales restent vertes.

## 5. Prochaine décision attendue

La seule décision nécessaire immédiatement est la confirmation ou l'ajustement de la date proposée pour `R-P4-01`.
Les autres réserves restent déclenchées par un changement de périmètre : staging, activation, fournisseur réel ou
nouveau lot Automation non borné.

## 6. Checklist de reprise — intégration des réserves

Avant tout travail Phase 5 qui touche l'Automatisation, partir du changement envisagé et appliquer la ligne
correspondante. Une ligne non satisfaite ne se contourne pas : le flag reste désactivé et le changement est réduit ou
reporté.

| Changement envisagé | Réserves à revoir | Action obligatoire avant intégration | Décision si la preuve manque |
|---|---|---|---|
| Travail interne sans activation, données synthétiques, sans fournisseur réel | `R-P4-01` | Confirmer disponibilité/capacité et maintenir les flags désactivés. | Ne pas annoncer ni ouvrir un lot non borné. |
| Déploiement ou test en staging | `R-P4-02`, `R-P4-03`, `R-P4-06` | Environnement isolé, protocole de charge, audit/alertes et rollback prouvés. | Pas de staging. |
| Appel OpenAI réel ou autre fournisseur réel | `R-P4-04`, `R-P4-06` | Contrat, rétention, résidence, quotas, budget, minimisation et repli approuvés. | Conserver le faux fournisseur. |
| Flag activé pour une organisation cliente, effet CRM automatique ou pilote | `R-P4-02` à `R-P4-06` | D4, charge, audit, recette Produit/QA/Sécurité et décision d'activation dédiée. | Pas d'activation ni de pilote. |
| Incident tenant, permission, idempotence, rollback ou données | Toutes, en priorité la réserve concernée | Désactiver le flag, préserver l'audit, mettre l'état incertain en `to_verify`, analyser puis rejouer sur fixtures. | Suspendre la tranche concernée. |

### Procédure courte

1. relire la réserve déclenchée et confirmer son propriétaire ;
2. préparer la preuve uniquement avec l'environnement et les données autorisés ;
3. exécuter les contrôles ciblés puis le verrou qualité complet avant toute décision ;
4. joindre un rapport minimisé, sans PII, secret ni phrase libre ;
5. mettre à jour l'état de la réserve : `ouverte`, `en validation`, `levée` ou `suspendue` ;
6. demander une décision explicite avant de passer à staging, fournisseur réel, pilote ou production.

# P52-08 — Preuves et recette synthétique

| Métadonnée | Valeur |
| --- | --- |
| Périmètre | P5.2 — catalogue, contrats, droits, sièges et dérogations |
| Données | Strictement synthétiques, éphémères et nettoyées par les tests |
| Effets externes | Aucun email, paiement, checkout ou appel fournisseur |
| Révision Alembic | `20261008_0050 (head)` |
| Production | Non autorisée par cette recette |

## Exécution

Depuis la racine du projet, avec Docker Desktop démarré :

```powershell
.\scripts\Test-QualityGateLocal.ps1
```

Le verrou produit les preuves suivantes :

- `test-results/pytest-quality.xml` : suite backend complète ;
- `test-results/p52-08/evidence.json` : scénarios P5.2 associés à des tests réussis et non ignorés ;
- `docs/recettes/p52-08/matrice-plan-droit.json` : registre plan/droit versionné, sans prix commercial.

## Matrice plan/droit

Les quatre codes stables (`freemium`, `starter`, `business`, `custom`) doivent porter exactement le registre fermé des huit droits. La matrice archive les types, unités et portées ; elle exclut volontairement montants, seuils commerciaux, taxes et références fournisseur. Les valeurs employées pour cette recette proviennent uniquement des fixtures de test.

## Scénarios et oracles

| ID | Preuve automatisée |
| --- | --- |
| P52-CAT-01 | Publication synthétique, approbateur distinct et audit append-only. |
| P52-CAT-02 | Tentative de modification d’un montant publié refusée par PostgreSQL. |
| P52-ENT-01 | Droit effectif, dérogation et plafond de sûreté avec provenance. |
| P52-ENT-02 | Contrat inconnu ou ambigu fermé avec code stable, sans valeur inventée. |
| P52-SEAT-01 | Réservations concurrentes : une seule place est accordée. |
| P52-SEAT-02 | Aucun chemin implicite de déclassement ne peut modifier un plan ou désactiver un membre. |
| P52-RLS-01 | Deux organisations ne lisent que leurs contrats et droits respectifs. |
| P52-AUD-01 | Création, approbation, révocation et transition sont auditées sans justification ni valeur sensible. |
| P52-API-01 | Rejeu idempotent et conflit optimiste HTTP `409` avec version courante. |
| P52-NOEXT-01 | Les mutations catalogue n’ont aucun port email, paiement, checkout ni fournisseur. |

## Conditions de conformité

La recette est conforme seulement si le verrou est vert, si `p52-08/evidence.json` contient les dix scénarios avec le statut `passed`, et si la matrice reste strictement synthétique. Une exécution verte ne vaut ni activation préproduction, ni prix réel, ni autorisation de paiement.

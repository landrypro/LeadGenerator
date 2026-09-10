# Phase 3.3-D — Rapport d’implémentation

## Résultat

Le sous-lot 3.3-D est implémenté. Les tâches commerciales ont un cycle de vie versionné (`open`, `completed`,
`cancelled`), avec annulation ou réouverture motivée. Les rappels sont internes : l’utilisateur peut les accuser ou les
reporter pour un maximum de sept jours. Aucune notification, donnée de navigateur ou automatisation externe n’est
introduite.

## Écrans et API

- la fiche prospect propose la création de tâche, sa liste et la prochaine action ;
- `/app/tasks` présente « Mes tâches » et les rappels dus, chargés en parallèle ;
- la liste de prospects et le Kanban affichent la prochaine action restituée par l’API ;
- `GET /api/prospects/tasks/next-actions` dérive une tâche ouverte par prospect sans dupliquer cet état dans
  `prospects` ;
- les tâches dont le responsable est désactivé restent visibles avec un avertissement ; une nouvelle affectation vers un
  membre désactivé est refusée.

## Garanties

- toutes les dates reçues doivent être horodatées ; elles sont persistées en UTC et rendues dans le fuseau IANA de
  l’organisation ;
- les échéances doivent être futures, les rappels ne dépassent pas l’échéance et le report est limité à sept jours ;
- les mutations restent idempotentes, protégées par version optimiste et journalisées avec l’événement métier et l’audit
  existants ;
- les composants React séparent l’affichage des tâches de la logique de dates et les chargements indépendants sont faits
  en parallèle.

## Contrôles exécutés

- Ruff et format Ruff : verts ;
- mypy ciblé : vert ;
- pytest ciblé : 13 tests verts, couvrant les rappels, idempotence, conflit de version, report borné et isolation des
  activités ;
- ESLint : vert ;
- Vitest ciblé : panneau de tâches (dont axe), « Mes tâches », liste prospects et Kanban verts ;
- build Vite : vert.

## Report explicite

Aucune migration n’est appliquée dans ce sous-lot. Les migrations `20260905_0016` et `20260905_0017`, la recette
fonctionnelle de bout en bout, la régression exhaustive et le verrou qualité global restent regroupés dans 3.3-E,
conformément à la décision produit.

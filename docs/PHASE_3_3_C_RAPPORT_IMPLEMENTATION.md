# Phase 3.3-C — Rapport d’implémentation

## Résultat livré

- La fiche prospect affiche une chronologie commerciale et les activités déclaratives associées.
- Un membre autorisé peut consigner une note, un appel, un courriel ou une réunion. La déclaration n’envoie aucun
  message, ne réalise aucun appel et ne modifie aucune permission.
- Les appels et courriels peuvent être associés à un canal du prospect ou d’un de ses contacts. L’interface avertit pour
  un canal inconnu ou restreint ; le backend vérifie l’appartenance du canal et en fige l’état de permission dans
  l’activité.
- Une correction est append-only : l’activité initiale demeure visible et une activité liée porte la correction et son
  motif.
- Les libellés nouveaux de chronologie et d’activité sont fournis en `fr-CA` et `en-CA`, à partir de la locale de
  l’organisation.

## Limites intentionnelles

Cette itération ne livre ni envoi de courriel, ni téléphonie, ni calendrier, ni tâche visible. Les tâches, rappels et la
prochaine action appartiennent au sous-lot 3.3-D. La recette fonctionnelle reste regroupée après 3.3-E, conformément à
la décision validée.

## Contrôles exécutés

Le 5 septembre 2026 :

- `npm run lint` : vert ;
- Vitest ciblé, avec pool `threads` sous Windows : 4 tests verts, dont un test axe ;
- `npm run build` : vert ;
- `python -m mypy` sur les sources API et cas d’utilisation concernés : vert ;
- pytest ciblé API et permission de canal : 3 tests verts.

Les migrations `20260905_0016` et `20260905_0017` restent additives et seront appliquées ensemble lors de la recette
fonctionnelle finale 3.3. Aucun `stamp` Alembic ne doit être utilisé.

# Phase 3.3-A — Rapport d’implémentation du socle backend

## Livré

- domaine indépendant pour les activités, tâches et événements de tâche : types contrôlés, directions, priorités,
  statuts, instantanés de permission de contact et validations pures ;
- matrice de droits étendue : lecture/création/correction d’activité et lecture/création/gestion de tâche, avec une
  séparation explicite entre correction de ses propres activités et correction de toute activité ;
- migration additive `20260905_0016`, succédant à `20260904_0015` : tables `prospect_activities`,
  `prospect_tasks` et `prospect_task_events`, contraintes, index de consultation, références composites tenantées,
  RLS forcée et privilèges PostgreSQL minimaux ;
- ports applicatifs séparés (`ActivityRepository`, `TaskRepository`, `TaskEventRepository`) et implémentations
  PostgreSQL de base intégrées à l’unité de travail Prospects ;
- référence Alembic du verrou qualité mise à jour vers `20260905_0016`.

## Hors périmètre assumé

Conformément au découpage validé, aucune route API ni écran n’est livré dans 3.3-A. La création, la correction,
l’assignation, les rappels et la chronologie visible sont réservés aux sous-lots 3.3-B, 3.3-C et 3.3-D.

## Contrôles exécutés

- Ruff et format Ruff sur le backend et les tests : verts ;
- mypy complet : vert (`169` fichiers) ;
- tests ciblés domaine/capacités/prospects : `18 passed` ;
- tests spécifiques 3.3-A : validation des dates et corrections d’activité, bornes de rappel, matrice de droits et
  enregistrement des trois modèles SQLAlchemy.

## Contrôle restant avant la recette fonctionnelle regroupée

Le verrou qualité complet n’a pas pu démarrer dans l’environnement de travail de l’agent : le service WSL requis par
Docker est désactivé. Il doit être rejoué sur l’environnement local ou staging disposant de Docker avant la clôture
de 3.3-E. Aucun échec fonctionnel ou de code n’a été constaté dans les contrôles exécutables ici.

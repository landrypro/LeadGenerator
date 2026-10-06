# IMP-A6 — Procédure de rollback contrôlé

> Cette procédure ne vaut que pour l'environnement local Docker/WSL et des données synthétiques. Elle ne donne
> aucune autorisation de rollback, de test ou d'activation en staging ou en production.

## Ordre impératif

1. désactiver `AUTOMATION_ENABLED`, puis le flag d'organisation et le Playbook concerné ;
2. arrêter la prise de nouveaux jobs par le worker ;
3. annuler les jobs `queued` qui n'ont produit aucun effet ;
4. rechercher chaque admission `to_verify` par sa clé idempotente hachée et décider `effet retrouvé` ou
   `intervention humaine`, sans rejeu aveugle ;
5. vérifier qu'aucun job Automation n'est `running` ;
6. uniquement sur la base jetable créée par le verrou qualité, exécuter le downgrade Alembic ;
7. remonter immédiatement à `head`, relancer les tests et vérifier qu'aucune tâche CRM n'a été dupliquée.

## Preuve locale versionnée

Le verrou local réalise déjà une reconstruction plus stricte que le seul retour IMP-A6 : après création d'une base
Docker jetable, il exécute un `downgrade 20260723_0002`, puis un `upgrade head`, `alembic current`, `alembic check`
et toute la suite réelle PostgreSQL/Redis/worker. La révision attendue après IMP-A6 est `20261004_0035`.

Un downgrade ne doit jamais être exécuté sur la base de développement courante, une base partagée, le staging ou la
production dans le cadre de cette tranche. En cas de doute sur la nature jetable de la base, la procédure s'arrête.

## Critères de sortie

- flags toujours désactivés par défaut ;
- zéro job Automation en cours ;
- chaque `to_verify` réconcilié ou assigné à un humain ;
- migration revenue à `20261004_0035 (head)` ;
- tests de concurrence, reprise, suspension, version périmée et effet incertain verts ;
- rapport minimisé sous `test-results/automation-imp-a6/` ;
- revue Produit, QA et Sécurité encore requise avant toute décision de porte.

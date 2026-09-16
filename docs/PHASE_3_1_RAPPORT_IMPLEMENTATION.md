# Rapport d’implémentation — Phase 3.1

## Livré

- migration `20260826_0014` : sessions, exécutions, quarantaines et empreintes d’import, toutes protégées par RLS ;
- stockage de fichier privé, référencé par jeton opaque, limite de 10 Mio et purge automatique des fichiers âgés de 24 heures ;
- aperçu limité, mapping en liste blanche, validation sans écriture CRM et confirmation atomique avec clé d’idempotence ;
- déduplication exacte, quarantaine minimisée, provenance CSV par donnée et permission `unknown` pour chaque canal importé ;
- routes JSON sans cache, contrôle de capacité, CSRF et rapport de quarantaine sans valeurs brutes ;
- assistant « Déclarations d’import » côté React et documentation/recette QA.

## Hors périmètre assumé

- correction/reprise manuelle des lignes en quarantaine ;
- déduplication approximative ou fusion automatique ;
- XLSX, ZIP, connecteurs externes, Kanban, tâches et opportunités.

## Preuves automatisées ciblées

- Ruff et mypy sur le backend ;
- 19 tests Python ciblés couvrant l’analyse UTF-8/BOM, le mapping, la suppression de fichier partiel/expiré, l’audit et la factory ;
- ESLint, test React ciblé du parcours et build Vite.

## Clôture

La recette fonctionnelle locale et le verrou qualité complet ont été validés. Le responsable produit a prononcé le 4 septembre 2026 la clôture de 3.1 avec réserve.

La réserve suivie avant préproduction concerne la recette multi-instance 2.6 en staging et l’exécution probante d’Azure Pipelines. Elle ne bloque pas le démarrage de 3.2 — Pipeline Kanban.

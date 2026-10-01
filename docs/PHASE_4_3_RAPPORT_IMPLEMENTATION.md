# Phase 4.3 — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Contrat | [`PHASE_4_3_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_3_SPECIFICATIONS_DETAILLEES.md) |
| Date | 24 septembre 2026 |
| Autorisation | Décisions `P4.3-01` à `P4.3-08`, mesure QA et GO d’implémentation validés |
| État | Code 4.3 implémenté ; verrou qualité local VERT le 24 septembre 2026 à 05:40 UTC ; recette fonctionnelle regroupée en phase 4.6 |

## Réalisation

| Périmètre | Livraison |
| --- | --- |
| Exports CRM | Six jeux CSV fermés `crm_csv_v1`, colonnes sélectionnables dans un ordre canonique, filtres bornés, périmètre personnel ou organisationnel selon le rôle, neutralisation des formules. |
| Admission et worker | `export_csv:1` rejoint la transaction d’admission du worker 4.2. Idempotence HMAC par demandeur, cinq demandes actives, réservation du quota de 250 Mio, sortie limitée à 50 000 lignes et 50 Mio. Reprise, bail, annulation et échec final synchronisent l’état public. |
| Provenance | Règles d’export explicites par source, catégorie, finalité et champs. Les données externes sans règle valide sont omises. Le profil d’un prospect d’origine externe reste fermé après une simple retouche manuelle, car la provenance actuelle est portée par le profil entier. Les contenus Google directs restent exclus. |
| Artefacts | Fichier CSV privé, provisoire puis renommé, empreinte SHA-256, durée de 24 h, téléchargement authentifié, vérification du fichier et de la source, purge et réconciliation paginée des fichiers absents ou orphelins. |
| Historique imports | Liste paginée des sessions et runs, filtres, fiche minimisée, quarantaine paginée, lien de relance vers un nouveau fichier et un nouveau lot. La source et les droits sont revérifiés ; la confirmation 3.1 reste idempotente. |
| Isolation | Migration `20260924_0023` : tables, clés composées, contraintes, RLS forcée, droits de lecture CRM limités au rôle worker, fonctions privées de balayage. |
| Interface | Pages « Exports » et « Historique des imports », accès conditionné aux capacités, états d’attente/échec/expiration et gestion Admin des règles de source. |

Les valeurs de volumétrie QA approuvées restent celles de la spécification : quatre organisations, trois prospects et une opportunité au total. Elles ne dimensionnent pas les plafonds. La sélection d’une source révoquée invalide actuellement, de façon conservatrice, tous les exports de provenance de son organisation publiés avant ce changement ; cela peut provoquer une régénération inutile, sans exposition supplémentaire.

## Vérifications exécutées

| Contrôle | Résultat |
| --- | --- |
| Ruff lint, format et mypy | VERT ; 196 fichiers source typés au dernier passage. |
| Backend sans PostgreSQL | VERT ; 263 tests réussis, 61 tests d’intégration exclus après les derniers ajustements. Tests ciblés du worker et du contrat CSV : 9 réussis. |
| Frontend | VERT ; 45 fichiers Vitest et 195 tests réussis ; ESLint et build Vite réussis. |
| Alembic | `20260924_0023 (head)` ; génération SQL hors ligne de `0022 → 0023` réussie après les derniers ajustements. |
| `git diff --check` | Code retour 0 ; avertissements de conversion LF/CRLF propres à la copie Windows. |
| Verrou qualité local complet | **VERT** le 24 septembre 2026 à 05:40 UTC, en mode Docker WSL. Révision Alembic `20260924_0023 (head)`, 324 tests backend et 195 tests frontend réussis, zéro échec et zéro skip. |
| PostgreSQL réel et `EXP-10` | Migrations, reconstruction Alembic, RLS, tests d’intégration PostgreSQL et flux worker validés par le verrou. Le scénario volumétrique synthétique `EXP-10` n’est pas identifié séparément dans les rapports JUnit et reste une qualification de capacité distincte avant ajustement éventuel des plafonds. |

Le premier verrou PostgreSQL a révélé trois tests de sécurité restés alignés sur la phase 4.2 : l’un refusait encore toute lecture CRM au worker, deux exigeaient l’ancien ensemble exact de politiques RLS. Les assertions corrigées conservent un contrôle fermé et vérifient l’absence de droits d’écriture. Le second passage a validé la migration réelle, la reconstruction Alembic, tous les tests backend et frontend, les analyses statiques et le build. Aucun déploiement QA et aucune recette fonctionnelle ne sont revendiqués ici. `EXP-10` requiert toujours un jeu synthétique adapté pour qualifier les plafonds, car la QA actuelle n’a pas de volume représentatif. La recette fonctionnelle globale reste prévue à la fin de la phase 4, conformément à la décision produit.

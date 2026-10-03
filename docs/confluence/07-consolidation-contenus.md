# Consolidation des contenus

## Objectif de consolidation

Cette consolidation transforme un corpus documentaire dense en pages Confluence exploitables. Le but n'est pas de recopier tous les documents existants, mais de fournir :

- un index navigable ;
- une synthese de l'architecture et du statut projet ;
- une analyse fonctionnelle transverse ;
- une lecture transverse du phasage et de la fragmentation du developpement ;
- une cartographie API/integrations ;
- des procedures utilisateur et exploitation ;
- une memoire des decisions ;
- une structure cible d'espace Confluence ;
- une traçabilite vers les sources.

## Corpus observe

| Zone du depot | Contenu |
| --- | --- |
| `README.md` | Guide utilisateur, installation locale, contrat API initial, architecture, securite, qualite et etat de migration. |
| `docs/SPECIFICATION_CRM_V1.md` | Reference fonctionnelle et technique V1, decisions produit, modules, API cible, exigences non fonctionnelles. |
| `docs/PHASE_1_1_ACQUISITION_CONSERVATION.md` | Acquisition Google, provenance, conservation et frontiere entre donnees externes et CRM. |
| `docs/PHASE_2_*` | Fondations CRM : PostgreSQL, Redis, identite, organisations, audit, conformite, QA. |
| `docs/PHASE_3_*` | Coeur CRM : import CSV, Kanban, activites, taches, opportunites, recettes. |
| `docs/PHASE_4_*` | Pilotage, worker, exports, usage, connecteur pilote, recette 4.6. |
| `docs/PHASE_5_SPECIFICATIONS_DETAILLEES.md` | Preproduction, abonnement, paiement, exploitation et lancement progressif. |
| `docs/manuel-utilisateur/` | Manuel utilisateur, matrice de couverture, generation DOCX/HTML. |
| `docs/automatisation/` | Vision, reference fonctionnelle V2.1, architecture, backlog, preuves, portes et contre-validations. |
| `scripts/` | Qualite, QA locale, deploiement QA, sauvegarde, recettes E2E, generation manuel. |
| `backend/` | Implementation API, domaine, application, infrastructure, migrations et worker. |
| `client/` | Application React, routes, features, tests et manuel publie. |

## Sources de verite par sujet

| Sujet | Source de verite |
| --- | --- |
| Positionnement produit | `docs/SPECIFICATION_CRM_V1.md`, `docs/automatisation/VOLET_AUTOMATISATION_MARKETTEO.md` |
| Comportement livre | Tests, routes, code, rapports d'implementation les plus recents |
| Manuel utilisateur | `docs/manuel-utilisateur/MANUEL_UTILISATEUR.md` et matrice de couverture |
| Installation locale | `README.md`, `compose.yaml`, `backend/app/config.py` |
| Staging QA | `docs/JOURNAL_DEPLOIEMENT_STAGING_AWS.md`, `compose.qa.yaml`, scripts QA |
| API | `backend/app/presentation/api/routers/`, `README.md`, specs par phase |
| Configuration | `backend/app/config.py`, `.env.example`, `.env.qa.example` |
| Qualite | `azure-pipelines.yml`, `scripts/Test-QualityGateLocal.ps1`, rapports phase |
| Automatisation | `REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md`, `CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md`, `PORTE_4_PRET_A_CONSTRUIRE.md` |

## Ce qui a ete consolide dans les pages Confluence

| Page | Contenu consolide |
| --- | --- |
| Accueil du projet et index | Statut, perimetre, domaines fonctionnels, publics, points d'attention. |
| Analyse fonctionnelle | Roles, modules, parcours utilisateurs, regles de gestion, hors-perimetre et automatisation future. |
| Phasage et fragmentation du developpement | Phases 1 a 5, lots, dependances, axe P0/P1/P2, portes et Pre-Phase 5 Automatisation. |
| Architecture et choix techniques | Stack, couches, dossiers, donnees, securite, worker, automatisation future. |
| Installation et exploitation | Local, configuration, qualite, staging QA, CI, points ouverts. |
| API et integrations | Conventions, routes par domaine, Google, Mailpit, PostgreSQL, Redis, worker, Meta, Azure. |
| Guides utilisateur et procedures | Roles, parcours utilisateur, procedures QA, manuel. |
| Decisions, changelog et FAQ | Decisions datees, phases, FAQ, questions ouvertes. |
| Structure Confluence cible | Arborescence, labels, gouvernance, regles de maintenance. |

## Elements volontairement non recopies

- Corps complets des specifications de phase, pour eviter de dupliquer la source.
- Secrets, valeurs `.env`, cles, jetons, emails reels et mots de passe.
- Sorties de tests volumineuses.
- Captures et artefacts binaires.
- Details trop fins des migrations et schemas internes, qui restent dans les specs et le code.
- Donnees AWS sensibles ou operationnelles qui doivent rester controlees.

## Duplications et hygiene documentaire

Le depot contient plusieurs familles de documents proches :

- specifications detaillees par phase ;
- fragmentations par lots, tranches et portes ;
- rapports d'implementation ;
- recettes fonctionnelles ;
- contre-validations ;
- journaux d'exploitation ;
- manuel utilisateur ;
- documents Word locaux et temporaires.

La couche Confluence doit absorber la duplication par synthese et liens, pas par copie. Une bonne page Confluence dit "ou lire le detail" et "quel statut croire", sans devenir une deuxieme source divergente.

## Recommandations de nettoyage futur

Ces actions sont recommandees mais non executees par cette consolidation :

- Classer les documents Word locaux dans une zone `docs/artifacts/` ou les exclure explicitement de la doc source.
- Ajouter un index automatique des documents `docs/PHASE_*`.
- Ajouter une table "document, statut, date, source de verite, remplace par".
- Archiver les recettes historiques qui ne sont plus la reference courante.
- Normaliser les noms de fichiers tres proches entre specifications, rapports et recettes.
- Relier chaque decision majeure a un identifiant stable.

## Regle de mise a jour

A chaque nouveau jalon :

1. identifier les documents sources modifies ;
2. mettre a jour la page Confluence de synthese concernee ;
3. ajouter la decision au changelog ;
4. mettre a jour les questions ouvertes ;
5. verifier que le manuel utilisateur et la matrice de couverture restent coherents ;
6. ne jamais transformer une reserve ou un blocage externe en statut livre sans preuve.

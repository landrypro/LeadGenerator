# Accueil du projet et index

## Resume executif

Marketteo CRM est une application CRM SaaS pour petites equipes commerciales. Le produit est construit pour gerer des prospects, des contacts, des permissions de contact, un pipeline, des taches, des opportunites, des imports/exports internes, des rapports d'usage et des connecteurs controles.

La promesse produit consolidee est :

> Chaque prospect pris en charge. Chaque suivi maitrise.

Le socle courant combine :

- une interface React/Vite bilingue `fr-CA` et `en-CA` ;
- une API FastAPI ;
- PostgreSQL avec Row-Level Security ;
- Redis pour sessions, quotas, verrous et jetons ephemeres ;
- des integrations Google Places/Maps strictement bornees ;
- un worker pour exports, imports et traitements durables ;
- un corpus QA important couvrant tests unitaires, integration, accessibilite et recettes bout en bout.

## Statut projet

| Zone | Etat consolide |
| --- | --- |
| Produit CRM V1 | Phases 1 a 4.6 documentees et majoritairement cloturees localement. |
| Phasage | Phases 1 a 5, fragmentation par lots, Pre-Phase 5 Automatisation et axe de priorites P0/P1/P2. |
| Phase 4.6 | GO local le 30 septembre 2026 ; verrou local vert sur Alembic `20260929_0030`. |
| CI/Azure | Preuve Azure encore requise avant l'entree en phase 5. |
| Phase 5 | Cadree comme preproduction, abonnements, paiement, securite, exploitation et lancement progressif ; decisions commerciales encore a valider. |
| Automatisation | Reference fonctionnelle `RF-AUT-2.1` figee ; preparation autorisee ; construction active non autorisee tant que Porte 4 n'a pas rendu son verdict. |

## Index fonctionnel

| Domaine | Ce que couvre le projet |
| --- | --- |
| Acces et identite | Connexion, session opaque, CSRF, invitations, changement d'organisation, roles. |
| Administration | Organisations, membres, invitations, audit locataire et audit plateforme. |
| Recherche Google | Recherche explicite limitee a 20 resultats, pas de pagination, pas de persistance descriptive Google. |
| Prospects CRM | Creation manuelle, ajout depuis reference Google, fiche prospect, contacts, canaux, permissions. |
| Conformite | Provenance, acquisitions, fournisseurs, permissions de contact, conservation, holds. |
| Pipeline | Kanban commercial, etapes stables, transitions auditees, conflits optimistes. |
| Activites et taches | Chronologie, notes, appels declaratifs, taches, rappels et prochaine action. |
| Opportunites | Montants par devise, echeances, probabilite, responsable, cloture gagnee/perdue, reouverture. |
| Pilotage | Tableau de bord, quotas, rapports d'usage, exports CSV internes. |
| Imports | Declaration, televersement CSV, mapping, validation, confirmation, quarantaine et historique. |
| Connecteurs | Registre fournisseurs et pilote Meta Lead Ads simule ou conditionnel. |
| Automatisation future | Assistant encadre, Feu relationnel, Prevol, trois Playbooks, mode Preparer. |

## Pages Confluence principales

| Besoin | Page |
| --- | --- |
| Comprendre le produit et l'etat du projet | Accueil du projet et index |
| Comprendre le perimetre metier, les roles, modules, parcours et regles fonctionnelles | Analyse fonctionnelle |
| Comprendre la trajectoire, les lots, les portes et les priorites de developpement | Phasage et fragmentation du developpement |
| Comprendre l'architecture logicielle, les composants techniques et les choix structurants | Architecture et choix techniques |
| Installer, tester, exploiter | Installation et exploitation |
| Lire les routes et integrations | API et integrations |
| Former les utilisateurs ou QA | Guides utilisateur et procedures |
| Retrouver les decisions et questions ouvertes | Decisions, changelog et FAQ |
| Organiser l'espace Confluence | Structure Confluence cible |
| Comprendre ce qui a ete consolide | Consolidation des contenus |

## Publics cibles

| Public | Pages utiles |
| --- | --- |
| Responsable produit | Accueil, Analyse fonctionnelle, Phasage, Decisions, Structure Confluence, Consolidation |
| Developpeur | Architecture, API, Installation |
| QA | Analyse fonctionnelle, Guides, Installation, Decisions |
| Exploitation | Installation, API, Decisions |
| Support / formation | Accueil, Analyse fonctionnelle, Guides utilisateur |
| Securite / conformite | Analyse fonctionnelle, Architecture, API, Decisions, Consolidation |

## Points d'attention

- Ne pas presenter l'activation Meta reelle comme livree : elle reste conditionnee a des autorisations externes.
- Ne pas presenter la phase 5 comme implementee : elle est cadree, pas encore validee pour livraison.
- Ne pas presenter l'Automatisation comme active dans le produit : seule la preparation documentaire et certaines preuves isolees sont autorisees.
- Ne jamais copier dans Confluence de secrets, donnees client, jetons Mailpit, cookies, CSRF, cles Google ou extraits complets de fichiers d'environnement.

# Structure Confluence cible

## Objectif

L'espace Confluence doit permettre a chaque public de trouver rapidement la bonne information sans lire tout le depot. La structure recommandee separe :

- les pages de synthese ;
- les references produit et techniques ;
- les procedures ;
- les decisions ;
- les preuves et recettes ;
- les archives par phase.

## Page racine

`Marketteo CRM - Documentation projet`

Contenu attendu :

- resume produit ;
- statut courant ;
- liens vers pages principales ;
- avertissement sur secrets et donnees reelles ;
- proprietaire de l'espace ;
- date de derniere consolidation.

## Arborescence proposee

```text
Marketteo CRM - Documentation projet
├── 1. Accueil et index
├── 2. Analyse fonctionnelle
├── 3. Produit et perimetre
│   ├── Specification CRM V1
│   ├── Modules fonctionnels
│   ├── Roles et capacites
│   └── Limites et hors-perimetre
├── 4. Architecture
│   ├── Architecture applicative
│   ├── Donnees et migrations
│   ├── Securite et isolation
│   ├── Frontend
│   ├── Backend
│   └── Worker et traitements durables
├── 5. API et integrations
│   ├── Conventions API
│   ├── Routes par domaine
│   ├── Google Places et Maps
│   ├── Meta Lead Ads pilote
│   ├── Mailpit
│   └── Azure Pipelines
├── 6. Installation et exploitation
│   ├── Installation locale
│   ├── Configuration
│   ├── Qualite et tests
│   ├── Staging QA
│   ├── Sauvegardes et rollback
│   └── Runbooks
├── 7. Guides utilisateur
│   ├── Manuel utilisateur
│   ├── Procedures par role
│   ├── Recette QA
│   └── FAQ support
├── 8. Decisions et gouvernance
│   ├── Decisions produit
│   ├── Changelog
│   ├── Questions ouvertes
│   ├── Risques
│   └── FAQ projet
├── 9. Phasage et fragmentation
│   ├── Vue Phases 1 a 5
│   ├── Lots et sous-phases
│   ├── Axe P0/P1/P2 et portes 2/3/4
│   └── Pre-Phase 5 - Automatisation
├── 10. Phases et preuves
│   ├── Phase 1 - Acquisition et conservation
│   ├── Phase 2 - Fondations
│   ├── Phase 3 - Coeur CRM
│   ├── Phase 4 - Pilotage et echanges
│   ├── Phase 4.6 - Recette finale
│   └── Phase 5 - Preproduction
└── 11. Automatisation
    ├── Vision et reference fonctionnelle
    ├── Architecture cible
    ├── Backlog et tranches S4
    ├── Portes de decision
    └── Preuves et reserves
```

## Pages creees dans ce dossier

| Page Confluence | Role |
| --- | --- |
| Accueil du projet et index | Point d'entree et carte du projet. |
| Analyse fonctionnelle | Synthese metier : roles, modules, parcours, regles, limites et automatisation future. |
| Phasage et fragmentation du developpement | Vue transverse des Phases 1 a 5, lots, priorites P0/P1/P2 et portes Automatisation. |
| Architecture et choix techniques | Synthese technique lisible par developpeurs, securite et exploitation. |
| Installation et exploitation | Runbook local, QA et CI. |
| API et integrations | Carte des routes et fournisseurs. |
| Guides utilisateur et procedures | Formation, support et QA. |
| Decisions, changelog et FAQ | Memoire projet et questions ouvertes. |
| Structure Confluence cible | Plan d'organisation de l'espace. |
| Consolidation des contenus | Traçabilite entre depot et Confluence. |

## Labels Confluence recommandes

| Label | Usage |
| --- | --- |
| `marketteo` | Toutes les pages projet. |
| `crm-v1` | Specifications et modules V1. |
| `fonctionnel` | Analyse fonctionnelle, parcours, roles et regles metier. |
| `architecture` | Architecture, API, donnees, securite. |
| `exploitation` | Installation, QA, staging, runbooks. |
| `qa` | Recettes, preuves, tests, verrous. |
| `decision` | Decisions produit et techniques. |
| `automation` | Volet Automatisation. |
| `phase-4-6` | Recette et cloture 4.6. |
| `phase-5` | Preproduction et commercialisation. |
| `phase-1` a `phase-3` | Acquisition, fondations et coeur CRM. |
| `phasage` | Trajectoire, lots, dependances et portes de passage. |

## Gouvernance editoriale

| Type de page | Proprietaire recommande | Frequence de revue |
| --- | --- | --- |
| Accueil / index | Responsable produit | A chaque jalon. |
| Analyse fonctionnelle | Responsable produit | A chaque changement de perimetre ou parcours. |
| Architecture | Lead technique | A chaque changement d'architecture ou integration. |
| API | Lead backend | A chaque lot API. |
| Exploitation | Responsable exploitation | A chaque changement d'environnement. |
| Guides utilisateur | Produit / support | A chaque changement d'ecran. |
| Decisions | Produit | A chaque decision. |
| QA / preuves | QA | A chaque campagne. |
| Automatisation | Produit + architecture | A chaque porte. |
| Phasage | Produit + lead technique | A chaque nouveau lot, changement de porte ou changement de statut. |

## Regles de maintenance

- Chaque page de synthese doit indiquer son statut et ses sources.
- Une page Confluence ne doit pas contenir de secret ou de donnee reelle.
- Les preuves volumineuses restent dans les artefacts CI ou dossiers `test-results`, pas en copie brute dans Confluence.
- Les decisions doivent rester datees, attribuees et reliees a une source.
- Les pages obsoletes doivent etre marquees `Archive` plutot que supprimees sans trace.
- Une evolution materielle de l'Automatisation exige une nouvelle version de reference, pas une modification silencieuse de `RF-AUT-2.1`.

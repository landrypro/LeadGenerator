# Phasage et fragmentation du developpement

## Objectif

Cette page fournit une lecture unique de la fragmentation du developpement Marketteo. Elle distingue clairement :

1. les macro-phases produit 1 a 5 ;
2. les lots et sous-phases qui composent chaque macro-phase ;
3. le chantier transversal **Pre-Phase 5 — Automatisation** ;
4. l'axe `P` de priorite et de portes, qui n'est pas une phase supplementaire.

La regle de lecture est : **une phase livre un socle ; un lot livre une capacite ; une porte autorise ou bloque la suite ; une priorite indique ce qui doit etre prouve en premier**.

## Modele de lecture retenu

| Axe | Fonction | Nomenclature | Source de verite |
| --- | --- | --- | --- |
| Phases produit | Decrire la trajectoire CRM de l'acquisition a la mise en production | Phase 1, 2, 3, 4, 4.6, 5 | Specifications et rapports `docs/PHASE_*` |
| Fragmentation interne | Decrire les capacites livrees dans une phase | 1.1, 2.3, 2.4, 2.5, 2.6, 3.1 a 3.4, 4.1 a 4.6, 5.1 a 5.6 | Specifications detaillees et rapports d'implementation |
| Programme transversal | Concevoir l'automatisation en reutilisant le CRM existant | Pre-Phase 5, Etapes 1 a 4, vagues A/B/C et T1 a T4, S4-0 a S4-6 | `docs/automatisation/` |
| Axe `P` | Prioriser les travaux et statuer sur les passages | `P0/P1/P2` pour le backlog ; Portes 2/3/4 pour les decisions | `BACKLOG_DETAILLE_ETAPE_4.md`, dossiers de porte |

> **Interpretation du `p` :** il est integre comme axe de priorisation et de gouvernance, et non comme une sixieme phase. Si `p` designait une autre nomenclature metier, les libelles de cet axe pourront etre renommes sans deplacer les contenus.

## Chronologie des phases produit

| Phase | Finalite | Fragmentation principale | Etat documentaire | Condition de passage |
| --- | --- | --- | --- | --- |
| **1 — Acquisition gouvernee** | Poser la recherche et les limites de conservation | Recherche Google Places ponctuelle ; Phase 1.1 acquisition, provenance, conservation et separation Google/CRM | Socle historique et contrats de conformite | Les donnees externes restent temporaires ; seule la reference autorisee peut rejoindre le CRM |
| **2 — Fondations CRM** | Rendre le CRM multi-tenant, securise et exploitable | Identite, organisations, roles, RLS, audit, provenance, retention ; 2.3 provisioning/membres ; 2.4 audit et transitions ; 2.5 prospects/contacts/permissions/fournisseurs ; 2.6 Redis, quotas et observabilite | Cloturee par lots, avec preuves et reserves explicites | Les controles d'identite, d'organisation, d'isolation et de quota sont disponibles pour les domaines metier |
| **3 — Coeur operationnel** | Donner aux equipes les objets et parcours CRM principaux | 3.1 import CSV ; 3.2 pipeline Kanban ; 3.3 activites, taches et rappels ; 3.4 opportunites | Livree et couverte par recettes de lots | Les objets canoniques prospect, contact, activite, tache et opportunite sont utilisables sans registre parallele |
| **4 — Pilotage et echanges** | Fiabiliser l'execution, le pilotage et les integrations controlees | 4.1 dashboard ; 4.2 worker durable ; 4.3 exports/imports ; 4.4 quotas et usage ; 4.5 fournisseurs/Meta pilote ; 4.6 recette finale | 4.6 : GO local le 30 septembre 2026 ; preuve Azure encore a produire | Le verrou local est vert et la preuve CI/Azure du commit de cloture est disponible |
| **5 — Preproduction et lancement** | Preparer l'exploitation SaaS commerciale et le lancement progressif | Preproduction, restauration, abonnements, paiement heberge, securite, charge, couts, exploitation et cohortes | Cadree, non implementee | La preuve Azure 4.6, les decisions commerciales, la restauration, la charge et le rollback sont valides |

### Relation entre les phases

```text
Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 -> Phase 4.6 -> [preuve Azure] -> Phase 5
                      \___________________________/
                         socle reutilise par
                  Pre-Phase 5 — Automatisation
```

La Pre-Phase 5 ne remplace pas la Phase 5 et ne constitue pas un second CRM. Elle prepare une capacite transversale qui reutilise les objets, permissions, worker, audit et integrations controles des Phases 1 a 4.

## Pre-Phase 5 — Automatisation

Le chantier Automatisation est documente a part pour ne pas melanger conception, construction et production.

| Etape interne | Objet | Etat consolide | Autorise | N'autorise pas |
| --- | --- | --- | --- | --- |
| **1 — Cadrage produit** | Promesse PME, parcours, capacites Lite et limites | Validee | Figer le perimetre et les invariants | Ajouter un constructeur libre ou une autonomie externe implicite |
| **2 — Conception fonctionnelle et UX** | Prototype V2.1, Aujourd'hui, mode Preparer, Prevol, roles et exceptions | Cloturee avec reserves de Porte 2 | Figer `RF-AUT-2.1` et les parcours testables | Declarer l'adoption demontree ou envoyer automatiquement |
| **3 — Architecture, donnees et securite** | Modele de donnees, Feu relationnel, contrats, garde avant effet, IA bornee, menaces | `GO conditionnel` de Porte 3 | Planifier l'implementation et ses preuves | Ouvrir la construction sans capacites, fixtures et rollback confirmes |
| **4 — Plan de livraison et validation** | Tranches S4-0 a S4-6, backlog, oracles, preuves et dossier Porte 4 | Preparation autorisee ; Porte 4 en `NO-GO controle` | Preparer l'environnement isole, les fixtures, les tests et les migrations reversibles | Brancher le worker actif, migrer les donnees client, appeler une IA reelle ou produire |

### Fragmentation interne S4

| Tranche | Portee | Niveau de sortie attendu |
| --- | --- | --- |
| S4-0 | Fondations sans effet : owners, flags, capacites, correlation, fixtures, rollback | Preparation et dependances nommees |
| S4-1 | Runtime isole et noyau de regles | Feu et Prevol deterministes, sans effet CRM |
| S4-2 | Admission et objets canoniques | Idempotence, Passeport et rattachement CRM verifies |
| S4-3 | Assistant IA encadre | Schema ferme, clarification, repli, quotas et budget |
| S4-4 | Brouillon, approbation et suspension | Aucun envoi autonome ; invalidation et arret verifies |
| S4-5 | Playbooks et exceptions | Nouveau prospect, Proposition en attente, Occasion oubliee |
| S4-6 | Capacite, adversarial, observabilite et rollback | Dossier de preuves pret pour la Porte 4 |

Le statut de reference a retenir est : **pret a preparer, pas encore pret a construire ni a produire**.

## Axe `P` : priorites et portes

### Priorites du backlog Automatisation

| Priorite | Signification | Regle |
| --- | --- | --- |
| `P0` | Securite ou coherence indispensable avant tout effet CRM | Doit etre prouve avant toute tranche qui modifie un objet ou un etat |
| `P1` | Necessaire au parcours Lite V2.1 et a la Porte 4 | Doit etre couvert pour declarer le parcours vertical complet |
| `P2` | Utile a l'exploitation ou a l'adoption, sans bloquer le premier parcours | Peut etre planifie apres la levee des blocages P0/P1 |

### Portes de decision

| Porte | Question | Effet documentaire |
| --- | --- | --- |
| Porte 2 | Le comportement produit et l'UX sont-ils suffisamment clairs et testables ? | Fige `RF-AUT-2.1` avec reserves explicites |
| Porte 3 | L'architecture, les donnees et la securite sont-elles maitrisables ? | Autorise la planification, pas la production |
| Porte 4 | Les preuves d'execution, de capacite, de rollback et de responsabilite sont-elles suffisantes ? | Seule cette decision peut ouvrir les tranches de construction autorisees |

Une reserve de porte reste visible jusqu'a la preuve qui la leve. Elle ne doit pas etre convertie en « acquis » par simple changement de statut.

## Matrice de dependances et de preuves

| Capacite ou preuve | Phases sources | Pre-Phase 5 | Porte / priorite |
| --- | --- | --- | --- |
| Provenance et conservation | 1, 2.5 | Passeport et admission | P0 ; verifier avant toute activation de source |
| Organisation, roles et isolation | 2 | Capacites Automatisation et garde finale | P0 ; Porte 3 puis Porte 4 |
| Prospects, taches et opportunites canoniques | 3 | Playbooks sans second CRM | P0/P1 ; tests d'idempotence |
| Worker, audit et arret | 4 | Execution durable et suspension generationnelle | P0 ; preuve de rollback |
| Recette locale et CI | 4.6 | Entree de conception | Reserve Azure jusqu'a la fin de la Phase 5 |
| Preproduction, paiement et lancement | 5 | Dependances d'exploitation futures | P0 ; decision commerciale et technique |

## Regles de maintenance

- Chaque fragment porte un identifiant stable : phase, lot, tranche ou porte.
- Une synthese Confluence indique toujours le statut, la preuve attendue et la source detaillee.
- Les specifications et rapports restent la source de detail ; Confluence fournit la lecture transverse.
- Les statuts `cadree`, `preparee`, `GO conditionnel`, `NO-GO`, `livree` et `produite` ne sont pas interchangeables.
- Une nouvelle capacite doit etre rattachee a une phase ou a la Pre-Phase 5, avec ses dependances et ses tests.
- Les secrets, donnees reelles et sorties volumineuses de CI restent hors de Confluence.

## Sources consolidees

- `docs/PHASE_1_1_ACQUISITION_CONSERVATION.md`
- `docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md` et rapports des lots 2.x
- `docs/PHASE_3_SPECIFICATIONS_DETAILLEES.md` et rapports des lots 3.x
- `docs/PHASE_4_SPECIFICATIONS_DETAILLEES.md`, `docs/PHASE_4_6_SPECIFICATIONS_DETAILLEES.md` et rapports associes
- `docs/PHASE_5_SPECIFICATIONS_DETAILLEES.md`
- `docs/automatisation/BOUSSOLE_EVOLUTION_AUTOMATISATION_MARKETTEO.md`
- `docs/automatisation/CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md`
- `docs/automatisation/BACKLOG_DETAILLE_ETAPE_4.md`
- `docs/automatisation/PORTE_4_PRET_A_CONSTRUIRE.md`


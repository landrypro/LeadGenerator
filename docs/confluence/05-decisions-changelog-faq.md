# Decisions, changelog et FAQ

## Decisions structurantes

| Date | Decision | Source |
| --- | --- | --- |
| 22 juillet 2026 | Lancer la phase 2 : PostgreSQL, Redis, identite, organisations, RLS, audit et conformite. | `PHASE_2_SPECIFICATIONS_DETAILLEES.md` |
| 9 aout 2026 | Valider le repositionnement Marketteo CRM, la conformite Google et l'acquisition multicanale. | `SPECIFICATION_CRM_V1.md` |
| 25 aout 2026 | Cloture phase 2.5 avec reserves acceptees ; phase 2.6 cadrant Redis/observabilite. | `README.md`, docs phase 2.5/2.6 |
| 26 aout 2026 | Valider le cadrage phase 3 : import CSV, Kanban, activites/taches, opportunites, bilinguisme. | `PHASE_3_SPECIFICATIONS_DETAILLEES.md` |
| 23 septembre 2026 | Valider l'ordre des lots phase 4 : dashboard, worker, exports/imports, usage, connecteur pilote, recette. | `PHASE_4_SPECIFICATIONS_DETAILLEES.md` |
| 30 septembre 2026 | GO local de cloture phase 4.6 ; verrou local vert ; preuve Azure encore requise. | `PHASE_4_6_RAPPORT_IMPLEMENTATION.md` |
| 30 septembre 2026 | Cadrer la phase 5 : preproduction, abonnements, paiement, securite, exploitation et lancement progressif. | `PHASE_5_SPECIFICATIONS_DETAILLEES.md` |
| 1er octobre 2026 | Figer `RF-AUT-2.1` pour l'Automatisation : Feu relationnel, Prevol, mode Preparer, trois Playbooks. | `REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md` |
| 1er octobre 2026 | Automatisation : pret a preparer, pas encore pret a construire ni produire. | `CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md` |

## Changelog synthetique

| Phase | Resume |
| --- | --- |
| Phase 1 | Recherche Google Places ponctuelle, limitee, non persistante. |
| Phase 1.1 | Decisions d'acquisition, conservation et separation Google/CRM. |
| Phase 2 | Fondations CRM : identite, organisations, roles, RLS, audit, provenance, retention. |
| Phase 2.3 | Provisioning, membres, invitations, organisation active, plateforme. |
| Phase 2.4 | Audit transactionnel, consultation, suspension/reactivation. |
| Phase 2.5 | Prospects, contacts, permissions, fournisseurs, acquisition et conservation. |
| Phase 2.6 | Redis partage, quotas, verrous, observabilite et regression. |
| Phase 3.1 | Import CSV conforme avec apercu, mapping, validation, quarantaine. |
| Phase 3.2 | Pipeline Kanban et transitions controlees. |
| Phase 3.3 | Activites, taches, rappels et prochaine action. |
| Phase 3.4 | Opportunites, portefeuille, montants, issues, alignement pipeline. |
| Phase 4.1 | Tableau de bord. |
| Phase 4.2 | Worker durable. |
| Phase 4.3 | Exports internes et administration des imports. |
| Phase 4.4 | Quotas et rapports d'usage. |
| Phase 4.5 | Registre fournisseurs et connecteur Meta pilote. |
| Phase 4.6 | Recette de phase, tests E2E, accessibilite, preuves locales. |
| Phase 5 | Cadree, non implementee : preproduction, SaaS commercial, paiement et lancement. |
| Pre-Phase 5 Automatisation | Cadrage produit, reference V2.1, architecture, backlog et conditions de Porte 4. |

## Lecture du phasage

La fragmentation officielle est decrite dans [Phasage et fragmentation du developpement](09-phasage-fragmentation.md). Les Phases 1 a 5 sont les macro-etapes produit ; les lots `x.y` sont leurs increments ; la Pre-Phase 5 Automatisation est un programme transversal ; `P0/P1/P2` priorisent les travaux et les Portes 2/3/4 statuent sur les passages.

## FAQ

### Marketteo CRM est-il un extracteur de leads Google ?

Non. Le produit est positionne comme CRM. Google sert a une recherche ponctuelle et dynamique, strictement limitee. Les contenus Google descriptifs ne sont pas persistés ni exportes.

### Qu'est-ce qui peut etre conserve depuis Google ?

Le `place_id` peut etre conserve comme reference. Les noms, adresses, telephones, sites Web, statuts et coordonnees Google restent temporaires, sauf affichage direct autorise et non persistant.

### Les exports contiennent-ils des donnees Google ?

Non. Les exports sont limites aux donnees CRM internes, importees ou saisies par l'organisation avec droits suffisants.

### La phase 4.6 est-elle terminee ?

Localement oui : GO de cloture locale le 30 septembre 2026, verrou local vert. Mais le passage Azure du commit de cloture reste requis avant l'entree en phase 5.

### Meta Lead Ads est-il actif en production ?

Non. Le pilote technique est valide avec simulateur/doubles locaux. L'activation reelle depend d'autorisations externes, contrat, permissions officielles et environnement approuve.

### La facturation SaaS est-elle livree ?

Non. La phase 5 la cadre : plans Freemium, Starter, Business, Sur mesure, abonnements, paiement heberge, portail, taxes et webhooks. Les valeurs commerciales restent a valider.

### L'Automatisation est-elle disponible dans le produit ?

Non. La reference fonctionnelle est figee et la preparation est autorisee. La construction active, l'IA reelle, les effets CRM et les envois externes restent interdits tant que Porte 4 n'a pas donne son verdict.

### Quel est le principe du Feu relationnel ?

Le Feu relationnel est un resultat deterministe par action/canal/prospect/instant/regle :

- Vert : action admissible selon les donnees disponibles.
- Jaune : preuve absente, contradictoire, expiree ou approbation requise.
- Rouge : opposition ou interdiction ; aucune IA ni approbation ne peut l'abaisser.

### Que signifie "Prevol" ?

Le Prevol simule un Playbook avec les memes regles que l'execution, mais sans produire d'effet metier. Il sert a voir ce qui se produirait avant activation.

### Que signifie "mode Preparer" ?

Le systeme peut preparer une tache, un brouillon, une exception ou une demande d'approbation. Il ne peut pas envoyer une communication externe, modifier silencieusement le CRM ou contourner une permission.

### Le `P` est-il une phase supplementaire ?

Non. Dans le backlog Automatisation, `P0`, `P1` et `P2` sont des niveaux de priorite. Les Portes 2, 3 et 4 sont des decisions de passage. Le detail et les dependances sont centralises dans la page de phasage.

## Questions ouvertes

| Sujet | Question |
| --- | --- |
| Phase 4.6 | Ou est la preuve Azure du commit de cloture et quel est son identifiant ? |
| Phase 5 | Quels montants, devises, cycles, essais, remises et politiques de remboursement seront approuves ? |
| Paiement | Quel fournisseur est retenu apres validation juridique/comptable ? |
| Production | Quel hebergement, gestionnaire de secrets, supervision et strategie de sauvegarde/restauration seront retenus ? |
| Meta | Quand l'autorisation externe et l'environnement de test reel seront-ils disponibles ? |
| Automatisation | Qui possede chaque tranche S4 et quelles preuves D2/D3/D4 seront exigees avant Porte 4 ? |
| Manuel | L'administration plateforme reste-t-elle dans le manuel utilisateur ou devient-elle un guide separe ? |

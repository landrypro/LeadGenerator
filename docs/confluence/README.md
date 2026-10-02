# Documentation Confluence - Marketteo CRM

Ce dossier regroupe des pages Markdown pretes a etre importees ou copiees dans Confluence. Il ne remplace pas les specifications detaillees du depot : il sert de couche de lecture organisee, avec des syntheses, des index et des renvois vers les documents source.

Etat consolide au 1er octobre 2026 :

- Marketteo CRM est documente comme un CRM SaaS React/FastAPI oriente PME.
- Les phases 1 a 4.6 sont consolidees dans le depot, avec GO local de cloture 4.6 le 30 septembre 2026.
- La preuve Azure du commit de cloture 4.6 reste requise avant l'entree effective en phase 5.
- Le volet Automatisation est au stade "pret a preparer", sans autorisation de construction active ni d'effet CRM integre.

## Arborescence recommandee

Importer les pages dans cet ordre sous une page parente Confluence nommee `Marketteo CRM - Documentation projet`.

| Ordre | Page | Fichier |
| --- | --- | --- |
| 1 | Accueil du projet et index | [00-accueil-index.md](00-accueil-index.md) |
| 2 | Analyse fonctionnelle | [08-analyse-fonctionnelle.md](08-analyse-fonctionnelle.md) |
| 3 | Phasage et fragmentation du developpement | [09-phasage-fragmentation.md](09-phasage-fragmentation.md) |
| 4 | Architecture et choix techniques | [01-architecture-choix-techniques.md](01-architecture-choix-techniques.md) |
| 5 | Installation et exploitation | [02-installation-exploitation.md](02-installation-exploitation.md) |
| 6 | API et integrations | [03-api-integrations.md](03-api-integrations.md) |
| 7 | Guides utilisateur et procedures | [04-guides-utilisateur-procedures.md](04-guides-utilisateur-procedures.md) |
| 8 | Decisions, changelog et FAQ | [05-decisions-changelog-faq.md](05-decisions-changelog-faq.md) |
| 9 | Structure Confluence cible | [06-structure-confluence.md](06-structure-confluence.md) |
| 10 | Consolidation des contenus | [07-consolidation-contenus.md](07-consolidation-contenus.md) |

## Regles d'usage

- Les pages de ce dossier sont des pages de synthese pour Confluence.
- Les documents sources restent dans `README.md`, `docs/`, `docs/manuel-utilisateur/` et `docs/automatisation/`.
- En cas de contradiction, le comportement observe, les tests et les specifications detaillees les plus recentes priment.
- Les secrets, mots de passe, cles, cookies, jetons et donnees reelles ne doivent jamais etre ajoutes a Confluence.

## Sources principales consolidees

- `README.md`
- `docs/SPECIFICATION_CRM_V1.md`
- `docs/PHASE_1_1_ACQUISITION_CONSERVATION.md`
- `docs/PHASE_2_SPECIFICATIONS_DETAILLEES.md`
- `docs/PHASE_3_SPECIFICATIONS_DETAILLEES.md`
- `docs/PHASE_4_SPECIFICATIONS_DETAILLEES.md`
- `docs/PHASE_4_6_SPECIFICATIONS_DETAILLEES.md`
- `docs/PHASE_4_6_RAPPORT_IMPLEMENTATION.md`
- `docs/PHASE_5_SPECIFICATIONS_DETAILLEES.md`
- `docs/JOURNAL_DEPLOIEMENT_STAGING_AWS.md`
- `docs/manuel-utilisateur/README.md`
- `docs/manuel-utilisateur/MATRICE_COUVERTURE.md`
- `docs/automatisation/VOLET_AUTOMATISATION_MARKETTEO.md`
- `docs/automatisation/REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md`
- `docs/automatisation/BOUSSOLE_EVOLUTION_AUTOMATISATION_MARKETTEO.md`
- `docs/automatisation/BACKLOG_DETAILLE_ETAPE_4.md`
- `docs/automatisation/CONTROLE_FINAL_ETAPES_1_A_4_PHASES_1_A_4.md`
- `docs/automatisation/PORTE_4_PRET_A_CONSTRUIRE.md`

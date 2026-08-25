# Incrément 2.5.5-A — Rapport d’implémentation

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Objet | Compléments backend du profil, routage et liste Prospects |
| Statut | Implémenté ; recette PostgreSQL regroupée en attente |
| Migration livrée | `20260814_0012_prospect_profile.py` |
| Tête Alembic | `20260814_0012 (head)` |

## Résultat livré

2.5.5-A introduit le premier portefeuille CRM opérationnel :

- route protégée `/app/prospects` et route de création `/app/prospects/new` ;
- liste de prospects paginée côté serveur, avec recherche textuelle et option d’inclure les archives ;
- création manuelle d’un établissement ;
- migration additive du profil CRM : secteur, segment, taille, adresse volontairement saisie, étiquettes, propriétaire,
  priorité et référence de provenance ;
- `PATCH /api/prospects/{id}` avec version optimiste, provenance `manual`, audit et `no-store` ;
- capacité `prospects:update` pour les rôles locataires existants ;
- tests backend et frontend ciblés ajoutés, mise à jour de la tête attendue par Azure Pipelines et le verrou qualité local.

Les valeurs descriptives Google ne sont pas persistées : la mise à jour de profil enregistre une provenance manuelle,
et le seul identifiant Google durable reste `google_place_id`.

## Contrats livrés

- `GET /api/prospects?cursor=&limit=&include_archived=&search_text=&origin=&owner_id=&priority=` ;
- `POST /api/prospects` ;
- `PATCH /api/prospects/{prospect_id}` avec `version`, champs CRM, `purpose` et `territory` ;
- réponses enrichies du profil, toujours avec `Cache-Control: no-store`.

Un conflit de concurrence retourne `409 optimistic_lock_conflict`. Un prospect archivé ne peut pas être modifié.

## Contrôles exécutés

- Ruff : vert sur les fichiers modifiés ;
- mypy : `Success: no issues found in 142 source files` ;
- pytest complet : `195 passed, 29 skipped` ;
- Alembic heads : `20260814_0012 (head)` ;
- ESLint : vert ;
- build Vite : vert ;
- Vitest ciblé : 6 tests verts (`ProspectsPage` et routes), exécutés avec le pool `forks` et sans parallélisme de
  fichiers.

Le message de nettoyage `pytest-current` sous Windows est émis après la réussite des tests par un verrou de fichier
temporaire ; il ne modifie pas leur résultat. Le Vitest global démarre et exécute les suites, mais dépasse la limite
locale de 120 secondes à cause du coût de démarrage des environnements JSDOM sous Windows. Il sera exécuté sans cette
limite, avec le pool `forks`, dans le verrou final 2.5.5-E.

## Limites assumées

- la fiche dynamique `/app/prospects/:prospectId`, l’édition visuelle du profil, les contacts et permissions sont
  réservés à 2.5.5-B ;
- les écrans fournisseurs, acquisitions, conservation et import sont réservés aux lots C et D ;
- la vérification PostgreSQL réelle de la migration et la recette humaine restent regroupées à la fin de 2.5.5 ;
- le Kanban, les activités, l’import de fichier et les connecteurs restent hors périmètre.

## Passage suivant

2.5.5-A est prêt pour **2.5.5-B — Fiche prospect, contacts, canaux et permissions**. La recette groupée et le Go de
phase 2.5 ne peuvent être prononcés qu’après le lot E.

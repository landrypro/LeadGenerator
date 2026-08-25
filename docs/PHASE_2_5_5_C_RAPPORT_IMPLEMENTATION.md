# Incrément 2.5.5-C — Rapport d’implémentation

## Résultat

L’écran **Fournisseurs et acquisitions** est disponible à `/app/compliance/sources` pour les membres ayant
`providers:read`. Il réutilise les API et règles métier déjà livrées par 2.5.3, sans migration supplémentaire.

- Les administrateurs peuvent créer un fournisseur en brouillon, compléter ses conditions, territoires, finalités,
  catégories et attestation, puis le modifier avec contrôle de version.
- L’écran signale explicitement les statuts non utilisables (`draft`, `suspended`, `retired`) ; les liens de conditions
  externes utilisent `noopener noreferrer`.
- Les rôles autorisés peuvent déclarer une acquisition seulement à partir d’un fournisseur actif. La déclaration porte
  une clé d’idempotence par action et rappelle qu’elle ne vaut pas permission de contact.
- Les administrateurs peuvent approuver ou rejeter les acquisitions en attente ou en quarantaine, après confirmation.

## Sécurité

Les mutations passent par le client HTTP commun (cookie, CSRF, erreurs normalisées) et les endpoints existants
`no-store`. Aucun document contractuel, secret, clé API ou stockage navigateur n’est introduit.

## Vérifications

- Routage et écran : tests Vitest ciblés verts.
- ESLint et build Vite : verts.
- Ruff format/check et mypy backend : verts (142 fichiers).

La recette PostgreSQL/RLS et le verrou qualité complet demeurent regroupés en 2.5.5-E.

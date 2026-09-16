# Recette fonctionnelle — Phase 3.1 Import CSV

## Préconditions

1. Démarrer PostgreSQL, Redis et Mailpit avec `docker compose up -d --wait` depuis WSL.
2. Dans PowerShell, charger `.env`, lancer `alembic upgrade head`, puis démarrer l’API et le client.
3. Se connecter avec un Administrateur ou un Gestionnaire d’une organisation active.
4. Dans « Sources et acquisitions », créer un fournisseur CSV, le rendre actif, puis créer et approuver une acquisition CSV compatible.

## CSV de recette

Créer localement `recette-3-1.csv` avec ce contenu UTF-8 :

```csv
Entreprise,Adresse,Contact,Courriel,Téléphone
Atelier Alpha,10 rue Principale,Alex Exemple,alex@example.ca,+14185550101
Atelier Alpha,10 rue Principale,Alex Exemple,alex@example.ca,+14185550101
Atelier Beta,20 rue du Port,Béatrice Exemple,adresse-invalide,+14185550102
```

## Scénario CSV-01 — Déclaration, aperçu et mapping -OK

1. Ouvrir « Conservation et imports », puis « Déclarations d’import ».
2. Créer une déclaration CSV avec les champs `Nom établissement`, `Adresse`, `Nom contact`, `Courriel` et `Téléphone`, ainsi que les catégories correspondantes.
3. Dans « 1. Téléverser un CSV », sélectionner la déclaration et le fichier de recette.
4. Vérifier que l’aperçu apparaît, limité aux premières lignes, sans création immédiate dans « Prospects ».
5. Associer les colonnes aux champs CRM correspondants puis enregistrer le mapping.

Résultat attendu : le fichier n’est jamais visible par URL publique ; l’écran indique qu’il est temporaire et aucun prospect, contact ou canal n’est encore créé.

## Scénario CSV-02 — Validation et confirmation - OK

1. Sélectionner « Valider le fichier ».
2. Vérifier les compteurs : une ligne prête, un doublon exact et une ligne en quarantaine pour courriel invalide.
3. Sélectionner « Confirmer l’import ».
4. Vérifier le rapport : une création, un doublon ignoré et une quarantaine.
5. Vérifier que la quarantaine ne montre que le numéro de ligne, le code de motif et une référence opaque.
6. Ouvrir « Prospects » et vérifier la création d’`Atelier Alpha`.
7. Ouvrir sa fiche : vérifier le contact, les canaux, la provenance CSV et la permission `non déterminée`.

Résultat attendu : le CSV est supprimé après confirmation. Aucun canal ne devient « autorisé » du seul fait de l’import.

## Scénario CSV-03 — Rejeu et isolation -OK(avec reserve)

1. Rejouer la confirmation avec le même `Idempotency-Key` au moyen du client réseau ou d’un test API contrôlé.
2. Vérifier que le même rapport est retourné sans deuxième création.
3. Changer d’organisation, puis tenter d’ouvrir l’identifiant de session ou de rapport de l’organisation initiale.

Résultat attendu : le rejeu ne crée rien ; l’accès inter-organisation retourne `404` grâce à l’API et aux politiques RLS.

## Scénario CSV-04 — Refus de conformité - OK (avec reserve)

1. Tenter un fichier non CSV, non UTF-8, de plus de 10 Mio, avec plus de 50 colonnes ou une cellule de plus de 4 096 caractères.
2. Tenter un mapping sans « Nom établissement » ou vers un champ non déclaré.
3. Tenter le téléversement avec une acquisition non approuvée ou hors période de validité.

Résultat attendu : un message sûr est affiché ; aucun prospect, contact, canal, provenance ni permission n’est créé.

## Contrôles techniques de sortie

Exécuter le verrou de qualité local en suivant le mode Docker Windows ou WSL retenu par l’équipe, puis vérifier : Ruff, mypy, pytest, Alembic, ESLint, Vitest et build verts. Conserver les rapports générés dans `test-results/` avec la fiche de recette.

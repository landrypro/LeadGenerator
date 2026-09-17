# Recette fonctionnelle QA — Phase 3.4 Opportunités

**Version :** 1.0  
**Statut :** prête à exécuter  
**Tête Alembic attendue :** `20260910_0020 (head)`

Utiliser uniquement des organisations, utilisateurs et prospects fictifs. Ne saisir aucun secret ni contenu descriptif
Google. Pour chaque scénario, consigner compte, organisation, identifiants techniques utiles, résultat et capture.

## 1. Préparation

Créer les organisations A et B ; préparer Admin A, Manager A, Sales A, Sales A2 et Admin B. Dans A, créer les prospects
`OPP Montants`, `OPP Cycle`, `OPP Concurrence` et `OPP Pipeline`. Dans B, créer `OPP Isolation`. Vérifier que les deux
organisations utilisent des devises et fuseaux connus.

## 2. Scénarios fonctionnels

### OPP-01 — Création et montant exact

Créer sur `OPP Montants` une affaire de `12500.5000 CAD`, probabilité 40 %, échéance future. Attendu : montant inchangé,
valeur pondérée `5000.2000 CAD`, une seule création dans la chronologie et aucune modification du pipeline prospect.

**Verdict : OK —** opportunité « Clinique Proximité » créée avec `12 500,5 CAD`, probabilité 40 % et valeur pondérée
affichée à `5 000,2 CAD` ; validation fonctionnelle et capture fournies le 10 septembre 2026.

### OPP-02 — Devises séparées

Créer une affaire CAD et une USD. Attendu : deux agrégats distincts sur fiche et portefeuille ; aucun total général
multidevise ni conversion implicite.

**Verdict : OK —** les valeurs pondérées sont présentées dans deux agrégats indépendants, `20 000 CAD` et
`6 250 USD`, sans total multidevise ni conversion implicite ; validation fonctionnelle et capture fournies le
10 septembre 2026.

### OPP-03 — Validations et échéance

Essayer montant nul, négatif, exponentiel, cinq décimales, devise invalide, probabilité 101 et échéance passée. Attendu :
refus sans écriture partielle. Vérifier ensuite une affaire arrivée à échéance : elle devient « En retard » sans changer
d’étape ni créer de rappel.

**Verdict : partiellement OK —** les messages accessibles pour le montant, la probabilité et l’échéance sont validés.
Le contrôle visuel de la devise invalide `ZZZ` est reporté à la recette finale : lorsqu’elle est la seule erreur, la
commande atteint l’API et le message de devise doit être présenté sous ce champ. Aucun enregistrement partiel n’a été
constaté.

### OPP-04 — Étapes ouvertes

Sur `OPP Cycle`, avancer puis reculer d’un cran. Essayer un saut. Attendu : transitions voisines acceptées, saut refusé,
versions et événements cohérents.

**Verdict : OK —** les transitions voisines dans les deux sens et leurs événements de chronologie ont été constatés.
Le saut direct `Découverte` → `Proposition` a été refusé par l’API avec le statut `422`; l’opportunité est restée à
`discovery`, en version `1`, sans écriture ni événement supplémentaire. Preuves fournies les 11 et 17 septembre 2026.

### OPP-05 — Gagnée

Depuis Proposition ou Négociation, marquer gagnée. Attendu : étape Gagnée, probabilité 100, aucun motif de perte,
lecture seule jusqu’à réouverture et aucune création automatique de client.

**Verdict : OK —** l’anomalie bloquante a été corrigée et le rejeu fonctionnel du 17 septembre 2026 est conforme.
La commande `proposal` → `won`, envoyée depuis la version `3`, retourne la version `4`, la probabilité `100`, un
`closed_at` renseigné et aucun motif de perte. L’interface affiche l’étape « Gagnée », la valeur pondérée complète
et uniquement les actions terminales « Réouvrir » et « Aligner le pipeline ». Le verrou global après correctif est
également vert : 300 tests backend et 167 tests frontend, sans skip.

### OPP-06 — Perdue et motifs

Depuis une étape ouverte, marquer perdue avec chaque motif contrôlé ; pour « Autre », omettre puis fournir la note.
Attendu : codes jamais affichés, probabilité 0, note obligatoire seulement pour « Autre », terminalité respectée.

**Verdict : OK —** les motifs sont présentés avec des libellés métier. Une opportunité clôturée affiche « Perdue » et
`0 %`, avec l'action « Réouvrir ». Le motif `other` accompagné de sa note est correctement persisté et horodaté ; une
tentative sans note a été refusée côté interface, sans requête de transition ni écriture.

### OPP-07 — Réouverture

Avec Admin A puis Manager A, rouvrir une gagnée et une perdue avec motif et probabilité ouverte. Attendu : réouverture
autorisée et historisée. Avec Sales A, l’action est absente et l’API répond 403.

**Verdict : OK avec réserve —** la réouverture autorisée remet l'affaire à une étape ouverte, à `50 %`, sans clôture ni
motif de perte ; la carte Sales ne propose pas l'action « Réouvrir ». La preuve API du refus `403
opportunity_action_forbidden` pour Sales reste à rejouer avant la recette finale.

### OPP-08 — Modification et responsable

Modifier nom, montant, devise avec montant confirmé, probabilité, échéance et responsable. Désactiver ensuite le
responsable. Attendu : lecture maintenue, mutations bloquées jusqu’à réaffectation par Admin/Manager.

### OPP-09 — Concurrence

Lire la même affaire dans deux sessions, modifier avec la première puis envoyer l’ancienne version avec la seconde.
Attendu : HTTP 409 `opportunity_version_conflict`, version courante annoncée, aucune seconde mutation.

### OPP-10 — Idempotence

Rejouer deux fois une création ou transition avec même clé et même commande, puis réutiliser la clé avec une commande
différente. Attendu : même résultat sans doublon, puis conflit d’idempotence stable.

### OPP-11 — Portefeuille et pagination

Créer plus de 25 affaires, filtrer par texte, étape, devise et retard, puis « Charger plus ». Attendu : tri stable,
aucun doublon, agrégats cohérents et filtres conservés.

### OPP-12 — Chronologie et synthèses

Créer, modifier et déplacer une affaire. Attendu : événements présents dans la chronologie ; synthèses visibles sur
fiche, liste et Kanban ; les notes et montants ne sont pas recopiés dans l’événement résumé.

### OPP-13 — Alignement pipeline

Déplacer une opportunité sans aligner le prospect, puis choisir explicitement « Aligner le pipeline ». Attendu : les
deux étapes restent indépendantes avant confirmation ; la seconde commande respecte le graphe 3.2. Un saut interdit
invite à passer par le Kanban sans annuler la transition d’opportunité.

### OPP-14 — Rôles

Admin A et Manager A voient les affaires de A. Sales A ne voit et ne modifie que ses affaires. Sales A2 ne peut pas
muter celles de Sales A. Les actions absentes dans l’interface doivent aussi être refusées par l’API.

### OPP-15 — Isolation

Depuis A, tenter de lire et muter l’affaire de B par identifiant. Attendu : ressource non révélée, aucune écriture ni
événement dans B. Vérifier l’inverse avec Admin B.

### OPP-16 — Sécurité et navigateur

Vérifier `Cache-Control: no-store` sur portefeuille, fiche, historique, chronologie et synthèses. Une mutation sans CSRF
valide est refusée. Aucun contenu 3.4 n’apparaît dans `localStorage`, `sessionStorage`, IndexedDB ou Cache API.

### OPP-17 — Français, anglais et clavier

Rejouer création, perte, réouverture et filtres en `fr-CA` puis `en-CA`, uniquement au clavier. Attendu : libellés
compréhensibles, focus visible, absence de codes backend, ordre logique et aucune violation axe.

## 3. Régression 3.1 à 3.3

| ID | Contrôle minimal | Verdict |
| --- | --- | --- |
| REG-31 | Import CSV : aperçu, mapping, confirmation et isolation | À exécuter |
| REG-32 | Kanban : neuf étapes, transition, perte/réouverture, charger plus | À exécuter |
| REG-33 | Chronologie : note, activité, tâche, prochaine action et rappel | À exécuter |

## 4. Verdict

| Élément | Résultat |
| --- | --- |
| Migration reconstruite | Conforme — `20260910_0020 (head)`, aucune dérive Alembic |
| OPP-01 | OK — création, montant exact et valeur pondérée validés par capture |
| OPP-02 | OK — agrégats CAD et USD séparés, sans total multidevise |
| OPP-03 | Partiellement OK — devise invalide à confirmer isolément en recette finale |
| OPP-04 | OK — transitions voisines, chronologie, version et refus d’un saut validés |
| OPP-05 | OK — transition Gagnée, probabilité 100, clôture, terminalité et version validées |
| OPP-06 | OK — perte avec motifs, note obligatoire pour « Autre » et terminalité validées |
| OPP-07 | OK avec réserve — action absente pour Sales ; refus API `403` à rejouer avant recette finale |
| OPP-08 à OPP-17 | À exécuter |
| REG-31 à REG-33 | À renseigner |
| Verrou global sans skip | Conforme — `Verrou qualité local 3.4 : VERT` le 17 septembre 2026 |
| Réserves transférées | À renseigner |
| GO de clôture produit | À renseigner |

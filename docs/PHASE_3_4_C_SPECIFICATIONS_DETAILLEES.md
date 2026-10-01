# Phase 3.4-C — Interface et intégrations CRM des opportunités

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3.4 — Opportunités |
| Sous-lot | 3.4-C — Interface et intégrations CRM |
| Version | 1.0 |
| Prérequis | 3.4-A et 3.4-B techniquement validés ; Alembic `20260910_0020 (head)` ; verrou local vert |
| Source de décision | Seize décisions de la section 17 de `PHASE_3_4_SPECIFICATIONS_DETAILLEES.md`, validées le 10 septembre 2026 |
| Statut | Implémentation réalisée et verrou qualité local vert le 10 septembre 2026 |
| Date | 10 septembre 2026 |

## 1. Objet et résultat attendu

Le sous-lot 3.4-C rend les opportunités utilisables dans les parcours CRM existants. Il ajoute leur création et leur
gestion sur la fiche prospect, un portefeuille dédié, leur historique dans la chronologie, une synthèse bornée dans la
liste et le Kanban, ainsi qu’une action séparée d’alignement avec le pipeline prospect.

À la sortie, un utilisateur autorisé peut travailler au clavier en `fr-CA` ou `en-CA` sans confusion entre l’étape d’une
affaire et celle du prospect. Aucun comportement de l’interface ne remplace les contrôles serveur livrés en 3.4-B.

## 2. Périmètre

### 2.1 Inclus

- section Opportunités et formulaire de création sur la fiche prospect ;
- consultation, modification, transition, clôture et réouverture selon les droits ;
- page « Opportunités » avec filtres, pagination, agrégats et états vides ;
- intégration des événements d’opportunité dans la chronologie commerciale ;
- synthèse groupée par devise sur la fiche, la liste des prospects et le Kanban ;
- proposition puis confirmation explicite d’alignement du pipeline ;
- textes, formats et messages `fr-CA` et `en-CA` ;
- accessibilité clavier, gestion du focus, annonces et tests axe ;
- adaptations API de lecture strictement nécessaires pour éviter les requêtes N+1 ;
- tests React, API client, accessibilité et régression des écrans CRM concernés.

### 2.2 Hors périmètre

- nouvelle migration, modification des tables 3.4-A ou nouvel automatisme métier ;
- conversion monétaire ou total combinant plusieurs devises ;
- glisser-déposer d’opportunités, prévisions, graphiques, objectifs ou export ;
- alignement automatique, en chaîne ou transactionnel avec une mutation d’opportunité ;
- création depuis Google, CSV, une activité ou une tâche ;
- suppression physique ou logique d’une opportunité ;
- refonte générale de la fiche prospect ou du Kanban.

## 3. Architecture frontend

Le code est regroupé sous `client/src/features/opportunities` :

- `api/opportunityApi.js` : contrats HTTP, sérialisation des décimaux et erreurs publiques ;
- `opportunityPresentation.js` : libellés, formats de date, montant exact et états visuels ;
- `components/OpportunitySection.jsx` : section de la fiche prospect ;
- `components/OpportunityFormDialog.jsx` : création et modification ;
- `components/OpportunityStageDialog.jsx` : transition, perte et réouverture ;
- `components/PipelineAlignmentDialog.jsx` : seconde action explicite sur le prospect ;
- `components/OpportunitySummary.jsx` : synthèse compacte réutilisable ;
- `OpportunitiesPage.jsx` : portefeuille ;
- tests colocalisés aux composants et adaptateurs.

Les composants reçoivent la locale, le fuseau, les capacités et les données depuis la session ou leurs propriétés. Ils
ne lisent pas directement les cookies et ne mémorisent aucune donnée métier dans un stockage navigateur persistant.

## 4. Contrats de présentation communs

### 4.1 Montants exacts

Le montant et la valeur pondérée restent des chaînes décimales de bout en bout. Le frontend n’utilise ni `Number`, ni
`parseFloat`, ni un calcul flottant pour les valeurs financières. Un formateur de présentation validé sépare partie
entière et décimales, applique les séparateurs `fr-CA` ou `en-CA` et ajoute le code de devise sans altérer la valeur.

La saisie accepte un séparateur décimal virgule en `fr-CA` et point en `en-CA`, sans séparateur de milliers. Avant
l’envoi, elle devient une chaîne canonique avec point. Une saisie ambiguë, négative, nulle, exponentielle ou comportant
plus de quatre décimales est refusée dans le formulaire puis reste validée côté serveur.

### 4.2 Dates et retard

`expected_close_on` est affiché comme date civile selon la locale, sans conversion UTC. L’état « En retard » /
« Overdue » vient de la réponse serveur ; le navigateur ne le recalcule pas à partir de son propre fuseau. Les
horodatages d’événement utilisent le fuseau IANA de l’organisation.

### 4.3 Libellés contrôlés

Les codes d’étape, de perte et de réouverture ne sont jamais montrés tels quels. Ils sont traduits par des catalogues
fermés correspondant aux codes 3.4. Un code inconnu produit « État indisponible » / « Status unavailable », une
télémétrie technique bornée et aucune interpolation du code brut dans l’interface.

La couleur complète un libellé et une icône ; elle n’est jamais le seul indicateur d’étape, de retard ou d’issue.

## 5. Fiche prospect — section Opportunités

### 5.1 Chargement et visibilité

La section est chargée avec les autres lectures CRM de la fiche, sans bloquer le profil, les contacts, les tâches ou la
chronologie si le module Opportunités échoue. Elle apparaît si l’utilisateur possède `opportunities:read`. Sans cette
capacité, aucun montant, nom ou détail d’opportunité n’est rendu.

La section contient :

- un titre et le nombre d’opportunités visibles ;
- le nombre d’affaires ouvertes ;
- les totaux et valeurs pondérées groupés par devise ;
- la prochaine échéance ouverte et son éventuel retard ;
- une liste paginée de cartes, initialement limitée à 25 ;
- « Charger plus » lorsque `has_more` est vrai ;
- l’action « Créer une opportunité » selon la capacité.

Un prospect archivé conserve la lecture et l’historique, mais la section indique « Prospect archivé — modifications
indisponibles » et ne propose aucune mutation. Un prospect `won` ou `lost` explique qu’il doit être rouvert avant de
créer une nouvelle affaire.

### 5.2 Carte d’opportunité

Chaque carte affiche le nom interne, l’étape, le montant et la devise, la valeur pondérée, la probabilité, l’échéance,
le responsable et, le cas échéant, « En retard » ou « Responsable désactivé ». Les actions visibles sont calculées à
partir des capacités, de la responsabilité, de la terminalité, de l’archivage et de l’état du responsable ; le serveur
reste l’autorité finale.

La carte propose selon le contexte : modifier, avancer, reculer, marquer gagnée, marquer perdue, rouvrir et proposer
l’alignement pipeline. Une action terminale n’est pas présentée comme une simple modification.

### 5.3 Formulaire de création et modification

Le formulaire contient :

- nom interne obligatoire, 160 caractères maximum ;
- montant strictement positif, quatre décimales maximum ;
- devise ISO 4217 ;
- probabilité entière de 0 à 100 ;
- date de conclusion prévue ;
- responsable actif lorsque le rôle peut le choisir.

`CAD`, `discovery` et 10 sont proposés à la création. Pour un Commercial, le responsable est fixé à son appartenance et
n’est pas modifiable. À la modification, changer la devise exige de confirmer le montant dans la même soumission. Une
échéance passée inchangée reste valide ; si l’utilisateur la modifie, la nouvelle date doit être le jour courant de
l’organisation ou une date future.

Le formulaire génère une clé d’idempotence par soumission logique et conserve la même clé pendant un nouvel essai
réseau. Il en crée une nouvelle après modification du contenu ou après un succès. Une mutation envoie toujours la
version affichée.

## 6. Dialogues de cycle de vie

### 6.1 Transition ouverte et gain

Les actions n’exposent que l’étape ouverte précédente ou suivante autorisée. « Marquer gagnée » n’est disponible que
depuis Proposition ou Négociation. La confirmation rappelle l’affaire et la cible. Un gain impose la probabilité 100
sans champ de motif.

### 6.2 Perte

Le dialogue affiche une liste traduite des huit motifs. `other` / « Autre » révèle une note obligatoire de 1 à 500
caractères ; les autres motifs autorisent une note facultative. Le code backend n’est jamais affiché. La confirmation
annonce que l’opportunité deviendra terminale et passera à une probabilité de 0.

### 6.3 Réouverture

La réouverture n’est visible que pour Administrateur et Gestionnaire. Le dialogue traduit les quatre motifs, rend la
note obligatoire pour « Autre » et exige une probabilité ouverte explicite. Il indique la cible calculée par le serveur
après succès : Négociation pour une affaire gagnée, dernière étape ouverte connue ou Découverte pour une affaire perdue.

### 6.4 Conflits et rejeux

Sur `opportunity_version_conflict`, l’interface ne rejoue pas automatiquement la mutation. Elle recharge la ressource,
annonce que les données ont changé et demande à l’utilisateur de vérifier puis confirmer une nouvelle commande. Un
échec réseau propose « Réessayer » avec la même clé d’idempotence et sans doubler l’événement.

Les erreurs de responsable inactif, prospect archivé, transition invalide et action interdite ont un message dédié et
ne ferment pas silencieusement le dialogue.

## 7. Portefeuille des opportunités

### 7.1 Navigation et route

La navigation principale ajoute « Opportunités » / « Opportunities » vers `/opportunities`, visible avec
`opportunities:read`. La page conserve le titre dans le document et un fil d’Ariane vers le CRM.

### 7.2 Filtres

Les filtres sont : texte interne, une ou plusieurs étapes, responsable, devise, échéance du/au, retard et prospect. Ils
sont représentés dans la chaîne de requête de la route pour permettre actualisation et partage interne, mais aucun
curseur opaque n’est conservé dans l’URL. Toute modification de filtre remet les résultats à la première page.

Un Commercial ne voit pas le filtre Responsable et sa portée reste fixée côté serveur. La recherche n’est lancée qu’à
la soumission ou après un délai de 300 ms ; deux réponses concurrentes ne doivent pas remettre à l’écran un résultat
obsolète.

### 7.3 Résultats et agrégats

Le portefeuille affiche d’abord les agrégats par devise, puis les affaires selon le tri serveur : échéance croissante,
mise à jour décroissante, UUID croissant. Chaque groupe de devise conserve son propre total et sa valeur pondérée ;
aucun « total général » multidevise n’est permis.

La page initiale contient 25 éléments. « Charger plus » ajoute la page suivante sans perdre les éléments existants et
sans déplacer le focus. L’absence de résultat, l’absence d’opportunité, le chargement partiel et l’erreur récupérable ont
des états distincts. Une erreur de curseur recharge la première page et l’explique à l’utilisateur.

## 8. Chronologie commerciale

### 8.1 Contrat unifié

`GET /api/prospects/{prospect_id}/timeline` est étendu de façon additive avec `opportunity_events`. Chaque entrée expose
uniquement : identifiant, opportunité, acteur, type, étapes source/cible, version résultante, noms de champs modifiés,
motif codé autorisé et horodatage. Les montants, noms d’opportunité et notes de motif ne sont pas recopiés dans le résumé.

La chronologie fusionne activités, tâches, transitions prospect et événements d’opportunité par horodatage décroissant,
puis par identifiant pour stabiliser les égalités. Les anciens consommateurs tolèrent l’absence du nouveau tableau.

### 8.2 Présentation

Les libellés sont : « Opportunité créée », « Opportunité modifiée », « Étape d’opportunité modifiée », « Opportunité
gagnée », « Opportunité perdue » et « Opportunité rouverte », avec leurs équivalents anglais. Une entrée pointe vers la
section Opportunités de la fiche si l’utilisateur peut lire l’affaire.

## 9. Synthèse sur liste et Kanban

### 9.1 Lecture groupée

Une lecture groupée dédiée reçoit au maximum les identifiants de prospects de la page ou des colonnes déjà chargées et
retourne, pour chacun : nombre d’opportunités ouvertes, prochaine échéance, indicateur de retard, présence d’une affaire
gagnée et totaux par devise. Elle applique la visibilité du rôle et ne révèle aucun nom d’opportunité.

Ce contrat évite une requête HTTP par carte. Les identifiants étrangers ou invisibles sont simplement absents. La
réponse porte `Cache-Control: no-store, max-age=0` et n’est pas persistée dans le navigateur.

Route proposée :

`GET /api/prospects/opportunity-summaries?prospect_id=<uuid>&prospect_id=<uuid>`

La limite est 100 identifiants uniques. Un doublon est normalisé ; une requête vide ou supérieure à la limite est
refusée avec une erreur de validation stable.

### 9.2 Présentation bornée

La ligne prospect et la carte Kanban affichent une synthèse compacte : nombre ouvert, prochaine échéance et montants
par devise. Au-delà de trois devises, elles montrent les deux premières selon le code alphabétique puis « +N devises »
avec un lien vers la fiche. Aucun chargement de synthèse ne modifie la hauteur minimale ou l’ordre des colonnes Kanban.

Un échec de la synthèse ne masque pas le prospect et ne bloque pas les actions pipeline existantes.

## 10. Alignement explicite avec le pipeline

Après une transition d’opportunité réussie, l’interface compare l’étape obtenue à la correspondance 3.4. Si le prospect
n’est pas déjà aligné, elle propose « Aligner le pipeline » / « Align pipeline » comme action secondaire distincte et
jamais présélectionnée.

Le dialogue présente :

- étape actuelle du prospect ;
- étape suggérée par l’opportunité ;
- rappel que les deux objets restent indépendants ;
- éventuel motif requis par la transition 3.2 ;
- boutons Annuler et Confirmer l’alignement.

La confirmation appelle la route 3.2 de transition du prospect avec sa version courante et une clé d’idempotence propre.
Elle ne rejoue pas la mutation d’opportunité. Si le graphe 3.2 interdit un saut, le dialogue explique qu’il faut déplacer
le prospect étape par étape dans le Kanban et n’envoie aucune commande contournant le graphe.

Pour une opportunité `lost`, l’alignement vers Perdu n’est proposé que si la synthèse serveur confirme qu’aucune autre
opportunité du prospect n’est ouverte ou gagnée. Pour `won`, l’interface peut proposer Gagné sans créer d’objet client.
Un conflit de version recharge le prospect ; un échec d’alignement laisse la mutation d’opportunité intacte.

## 11. Bilinguisme

Tous les nouveaux textes sont regroupés dans des catalogues `fr-CA` et `en-CA` couvrant navigation, titres, champs,
aides, étapes, motifs, confirmations, erreurs, états vides, retard, responsable désactivé et alignement. Le choix vient
de l’organisation active ; aucun mélange de langue n’est acceptable dans un même écran après chargement.

Les dates utilisent `Intl.DateTimeFormat` avec la locale et le fuseau de l’organisation. Les montants utilisent le
formateur décimal exact défini en 4.1, puis le code ISO ; ils ne sont jamais convertis par `Intl.NumberFormat(Number(...))`.

## 12. Accessibilité et clavier

- structure sémantique avec titres hiérarchisés, listes et tableaux accessibles ;
- libellé explicite pour chaque champ, erreur reliée par `aria-describedby` et résumé d’erreurs annoncé ;
- dialogues nommés, focus initial pertinent, boucle de focus, fermeture par Échap et restauration au déclencheur ;
- ordre clavier identique à l’ordre visuel, sans interaction exclusivement au pointeur ;
- `aria-live="polite"` pour succès, chargement additionnel et conflits récupérables ;
- `aria-live="assertive"` pour erreurs bloquantes ;
- indicateur de chargement annoncé sans remplacer brutalement le contenu existant ;
- cible tactile d’au moins 44 px pour les actions principales ;
- contraste et focus visibles conformes, sans dépendance exclusive à la couleur ;
- tableaux du portefeuille utilisables à 200 % de zoom et vue mobile sans perte d’action.

## 13. Sécurité, confidentialité et résilience

- les mutations utilisent le client HTTP central avec origine, cookie de session et CSRF ;
- les réponses de lecture et mutation exigent `no-store` ;
- aucune opportunité, filtre sensible, réponse, clé d’idempotence ou brouillon n’est écrit dans `localStorage`,
  `sessionStorage`, IndexedDB ou Cache API ;
- les textes utilisateur sont rendus comme texte, sans HTML injecté ;
- l’interface n’infère jamais l’existence d’une opportunité ou d’un prospect après un `404` ;
- aucun contenu Google n’est utilisé pour préremplir une opportunité ;
- les erreurs techniques, empreintes et détails SQL ne sont pas affichés ;
- un abandon de page annule les lectures en cours lorsque possible ;
- une erreur d’un panneau secondaire ne fait pas tomber toute la fiche ou le Kanban.

## 14. Adaptations backend sans migration

3.4-C autorise uniquement les extensions de lecture suivantes au-dessus de `20260910_0020` :

1. ajout de `opportunity_events` au read model de chronologie prospect ;
2. lecture groupée des synthèses par prospect pour la liste et le Kanban ;
3. exposition, si nécessaire, d’un catalogue serveur des devises admises afin d’éviter une divergence de validation.

Ces lectures réutilisent les dépôts, RLS, capacités, décimaux et règles de visibilité 3.4-B. Elles n’ajoutent aucune
table, colonne, écriture automatique ni privilège SQL. Toute autre lacune de contrat doit être documentée avant
d’élargir le backend.

## 15. Plan de tests obligatoire

### 15.1 Adaptateurs et présentation

- format exact des montants très grands, quatre décimales, zéro final et deux locales sans passage par un flottant ;
- normalisation des saisies décimales `fr-CA` et `en-CA`, cas ambigus et invalides ;
- traduction exhaustive des six étapes, huit motifs de perte et quatre motifs de réouverture ;
- dates civiles inchangées et horodatages dans plusieurs fuseaux ;
- synthèse de zéro à plus de trois devises.

### 15.2 Fiche prospect et formulaires

- chargement, vide, pagination, création, modification et restrictions par capacité ;
- Commercial propriétaire, Administrateur/Gestionnaire et responsable désactivé ;
- validation champ par champ, devise avec montant et échéance passée conservée ou modifiée ;
- transitions ouvertes, gain, perte, réouverture et messages d’erreur stables ;
- rejeu réseau avec même clé et conflit de version avec rechargement explicite.

### 15.3 Portefeuille et intégrations

- route et navigation selon capacité ;
- filtres combinés, remise à zéro du curseur, réponses concurrentes et « Charger plus » ;
- agrégats séparés par devise et absence de total multidevise ;
- fusion chronologique et ordre stable des quatre familles d’événements ;
- lecture groupée unique pour une page de prospects ou un Kanban, sans N+1 ;
- panne de synthèse sans disparition des cartes existantes.

### 15.4 Alignement pipeline

- aucune proposition lorsque le prospect est déjà aligné ;
- correspondance des six étapes et règle particulière de `lost` ;
- annulation sans requête, confirmation comme seconde commande et clés d’idempotence distinctes ;
- transition 3.2 directe autorisée, saut interdit, motif exigé et conflit de version ;
- échec d’alignement sans annulation de la transition d’opportunité.

### 15.5 Accessibilité et régression

- tests React Testing Library centrés utilisateur, sans dépendre de l’implémentation interne ;
- axe sans violation sur fiche, formulaires, dialogues, portefeuille, chronologie et Kanban enrichi ;
- parcours entièrement réalisables au clavier et focus restauré après chaque dialogue ;
- zoom, mobile, textes longs et deux locales ;
- régression des tests prospect, pipeline, chronologie, tâches et navigation ;
- ESLint, Vitest/axe et build Vite verts.

### 15.6 API ciblée

- read model chronologique avec événements d’opportunité et aucune donnée financière sensible ;
- synthèses groupées exactes, bornées, multi-organisation et filtrées pour le Commercial ;
- `401`, `403`, `404` non-divulgateur, validation de limite et `Cache-Control: no-store` ;
- absence de migration et `alembic check` sans écart.

## 16. Critères de sortie de 3.4-C

Le sous-lot est techniquement livrable seulement si :

1. la fiche prospect et le portefeuille couvrent tous les états et actions autorisés ;
2. chronologie, liste et Kanban utilisent des lectures bornées sans requête N+1 ;
3. l’alignement est une seconde action explicite respectant intégralement 3.2 ;
4. montants et valeurs pondérées ne passent jamais par un flottant JavaScript ;
5. tous les nouveaux textes et codes métier sont disponibles en `fr-CA` et `en-CA` ;
6. clavier, focus, annonces, contraste et axe sont conformes ;
7. ESLint, Vitest/axe, tests API ciblés, tests React et build Vite sont verts ;
8. les régressions prospect, pipeline, tâches et chronologie sont vertes ;
9. Alembic reste à `20260910_0020 (head)` et aucune migration n’est créée ;
10. un rapport d’implémentation 3.4-C consigne les commandes, résultats et réserves.

Le verrou qualité global et la recette fonctionnelle regroupée restent dus en 3.4-D.

## 17. Décision de sortie documentaire

Le GO du responsable produit du 10 septembre 2026 autorise la rédaction des présentes spécifications détaillées. Elles
traduisent les seize décisions 3.4 validées en contrats d’interface, d’intégration, de sécurité et d’accessibilité.

Cette autorisation ne lance pas l’implémentation. La réalisation de **3.4-C — Interface et intégrations CRM** exige un
GO explicite distinct.

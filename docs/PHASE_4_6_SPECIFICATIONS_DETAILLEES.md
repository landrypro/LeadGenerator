# Phase 4.6 — Recette de phase et tests de bout en bout

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 4.6 — Recette de phase et tests de bout en bout |
| Version | 0.5 — clôture locale |
| Statut | GO de clôture locale reçu le 30 septembre 2026 ; verrou qualité local VERT sur la tête Alembic `20260929_0030`. Le passage Azure sur le commit de clôture reste requis pour le verdict global. |
| Date | 30 septembre 2026 (UTC) |
| Contrat parent | [`PHASE_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_4_SPECIFICATIONS_DETAILLEES.md) |
| Prérequis | Lots 4.1 à 4.5 implémentés ; tête 4.6 `20260925_0026` validée par le verrou local |

## 1. Résultat attendu et frontière

Le lot 4.6 fournit la preuve de sortie de la phase 4. Il assemble les fonctions livrées depuis la création d’une
donnée CRM jusqu’à son pilotage, son traitement asynchrone, son export, son comptage d’usage et, pour le pilote Meta,
son admission contrôlée. La campagne doit démontrer simultanément :

1. les parcours métier complets de 4.1 à 4.5 ;
2. l’isolation entre organisations et la matrice de capacités ;
3. la reprise des cinq réserves transférées de 3.4 ;
4. l’absence de fuite de secrets, de données personnelles ou de contenus fournisseur ;
5. les interfaces `fr-CA` et `en-CA`, le clavier, le zoom à 200 % et les contrôles axe ;
6. un verrou local et un passage CI sur la même révision, sans test ignoré.

Le lot ne crée pas de nouvelle fonction métier, ne modifie pas les seuils approuvés et ne transforme pas une
simulation en autorisation fournisseur. Une anomalie découverte est corrigée dans son composant d’origine et reçoit
un test de non-régression. La préproduction, la facturation, les essais de charge de lancement et l’activation large
du connecteur relèvent de la phase 5.

## 2. État d’entrée et gel de la campagne

Le verrou local exécuté le 25 septembre 2026 à `03:19:02Z` constitue la référence d’entrée : migration
`20260924_0025 (head)`, 335 tests backend et 198 tests frontend, zéro échec et zéro skip. Cette preuve confirme le
socle technique ; elle ne remplace pas la recette 4.6.

Une campagne commence seulement lorsque les conditions suivantes sont réunies :

- le commit, l’état de l’arbre de travail et la tête Alembic sont consignés ;
- PostgreSQL, Redis et Mailpit réels sont disponibles dans un environnement jetable ;
- l’API, le worker et le client proviennent de la même révision ;
- les organisations et comptes de recette sont dédiés, sans données réelles ;
- les doubles Google et Meta sont locaux, déterministes et incapables d’effectuer un appel externe ;
- le connecteur Meta réel reste désactivé tant que les preuves externes ne sont pas réunies ;
- l’horloge, le fuseau, les locales et les secrets de test sont explicitement configurés ;
- aucun serveur de développement ni ancien worker ne partage les dépendances de la campagne.

Toute modification fonctionnelle après le début invalide le verdict global. La correction est appliquée, les tests
ciblés sont rejoués, puis la campagne P0 et le verrou complet repartent sur une nouvelle révision consignée.

### 2.1 Écarts de préparation à fermer avant la campagne

La revue du dépôt au 25 septembre 2026 identifie les écarts suivants. Le GO lance leur fermeture ; ils ne peuvent pas
être déclarés réussis sur la seule base du verrou d’entrée :

- le harnais navigateur sans dépendance supplémentaire (`scripts/phase4_6_browser_gate.mjs`) est maintenant branché au
  verrou local et à Azure ; les parcours authentifiés avec jeu de données et les états manuels restent à exécuter ;
- le harnais produit les rapports axe des 22 routes dans les deux locales ; `OPP-17-C-R1` reste ouverte jusqu’à la revue
  exhaustive des états données, vide, erreur, dialogue, clavier et zoom 200 % ;
- les cinq codes d’usage Meta de `P4.5-08` sont maintenant autorisés par la tête `20260925_0026`, comptés dans le
  rapport et émis par le pilote ; l’intégration PostgreSQL/RLS → job → worker → CRM est passée dans le verrou réel ;
- l’autorisation Meta externe n’est pas acquise et demeure une décision séparée.

Tout écart fonctionnel relevant d’un lot précédent reste attribué à ce lot dans le rapport de correction. Le lot 4.6
ajoute la preuve et l’orchestration nécessaires ; il ne réécrit pas rétroactivement le contrat source.

## 3. Environnement et jeu de données de référence

### 3.1 Organisations et identités

| Référence | Configuration | Usage |
| --- | --- | --- |
| `ORG-A` | `fr-CA`, `America/Toronto` | Organisation principale, données CRM, imports, exports, usage et pilote Meta simulé |
| `ORG-B` | `en-CA`, `UTC` | Preuve d’isolation, UUID étrangers et changement de contexte |
| `A-ADMIN-AUTEUR` | Admin de `ORG-A` | Création des fournisseurs, contrats et opérations administratives |
| `A-ADMIN-REVISEUR` | Admin distinct de `ORG-A` | Revue du contrat Meta ; séparation auteur/approbateur |
| `A-MANAGER` | Gestionnaire de `ORG-A` | Vues organisationnelles, exports et rapports d’usage |
| `A-SALES-1`, `A-SALES-2` | Commerciaux de `ORG-A` | Portées personnelles, propriété et interdictions croisées |
| `B-ADMIN`, `B-SALES` | Admin et Commercial de `ORG-B` | Contrôles inter-organisations |

Les adresses sont réservées au domaine de test. Les mots de passe, jetons, clés CSRF, secrets webhook et références
fournisseur ne figurent dans aucune capture ni pièce jointe.

### 3.2 Données déterministes

Le préparateur crée par API ou par fixture versionnée :

- des prospects répartis entre `new`, `qualifying`, `qualified` et `lost`, avec propriétaires distincts ;
- des tâches ouvertes, dues aujourd’hui, en retard, terminées et annulées autour du jour de `ORG-A` ;
- des activités corrigées afin de prouver qu’une seule version active est comptée ;
- des opportunités ouvertes, gagnées et perdues en CAD et USD, sans conversion ;
- un CSV UTF-8 contenant lignes valides, doublon exact, ambiguïté, formule de tableur et Unicode ;
- des événements d’usage Google synthétiques et des opérations import/export rapprochables ;
- un fournisseur, une acquisition et un contrat Meta fictifs, avec auteur et réviseur distincts ;
- des identifiants équivalents dans `ORG-B` pour les tentatives croisées.

Le manifeste de données conserve uniquement les identifiants techniques, nombres et valeurs fictives nécessaires au
rapprochement. Le nettoyage utilise les API ou la destruction de l’environnement jetable ; aucune suppression
directe en base n’est admise comme étape fonctionnelle.

## 4. Niveaux de preuve et statut d’un cas

| Niveau | Preuve exigée |
| --- | --- |
| Automatisé | JUnit, sortie structurée ou assertion d’intégration attachée à la révision |
| Navigateur | Capture assainie, locale, rôle, organisation, résolution et résultat observé |
| API/sécurité | Méthode, route, statut, code d’erreur et `request_id` non sensible ; corps minimisé |
| Données | Rapprochement par nombres ou identifiants fictifs ; aucun dump contenant des coordonnées |
| Exploitation | État du worker, nombre de tentatives, résultat terminal et preuve de purge sans contenu métier |

Les seuls statuts autorisés sont `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` et `N/A`. `N/A` est réservé à une variante déclarée
hors périmètre avant la campagne et ne peut viser un P0, une réserve transférée ou un contrôle de sécurité. Un test
`BLOCKED`, `NOT RUN` ou `N/A` n’est jamais compté comme réussi.

Chaque preuve porte `run_id`, commit, date UTC, environnement, testeur, organisation, rôle et identifiant du scénario.
Les captures sont relues avant archivage. Les fichiers CSV exportés restent dans le stockage temporaire contrôlé et
ne sont pas ajoutés au dépôt.

## 5. Parcours de bout en bout obligatoires

### 5.1 Matrice des parcours

| ID | Pri. | Parcours | Résultat exigé |
| --- | --- | --- | --- |
| `E2E-01` | P0 | Connexion de `A-ADMIN-AUTEUR`, lecture du tableau de bord, bascule vers `ORG-B`, retour vers `ORG-A`. | Le contexte change atomiquement ; aucune donnée, requête tardive ou agrégation de l’autre organisation ne subsiste. |
| `E2E-02` | P0 | Créer un prospect manuel, l’affecter, le déplacer dans le Kanban, ajouter activité et tâche, créer puis gagner une opportunité. | Chronologie complète, versions cohérentes, audit minimisé et indicateurs 4.1 rapprochables après actualisation. |
| `E2E-03` | P0 | Déclarer une acquisition CSV, téléverser, mapper, valider et confirmer le fichier de référence, puis consulter historique et quarantaine. | Une seule création par ligne admissible, doublon ignoré, ambiguïté quarantainée, permission inconnue et fichier source supprimé selon le contrat. |
| `E2E-04` | P0 | Demander un export autorisé issu des données de `E2E-02`/`E2E-03`, laisser le worker le produire, télécharger puis contrôler le CSV. | Colonnes en liste blanche, formule neutralisée, CAD/USD séparés, téléchargement réservé au demandeur et compteurs exacts. |
| `E2E-05` | P0 | Interrompre le worker durant un export contrôlé, laisser expirer le bail puis redémarrer deux workers. | Un artefact publié, aucun effet double, ancien jeton refusé, fichiers provisoires retirés et état terminal exact. |
| `E2E-06` | P0 | Exécuter via faux fournisseur une recherche Google autorisée, consulter quota courant, rapport personnel puis rapport organisationnel. | Une réservation et une tentative rapprochées ; scopes exacts ; aucune requête, réponse Google, coordonnée ou estimation de coût conservée. |
| `E2E-07` | P0 | Atteindre une limite synthétique, provoquer une panne du registre durable puis de Redis. | `429` avant fournisseur pour la limite ; `503` fermé si le suivi requis manque ; historique et quota courant ne sont jamais confondus. |
| `E2E-08` | P0 | Créer le dossier Meta fictif, soumettre, refuser l’auto-approbation, approuver avec le second Admin, activer le binding et envoyer un webhook signé. | Séparation des fonctions, une ingestion et un job, un prospect/contact/provenance au plus, champs non autorisés absents. |
| `E2E-09` | P0 | Rejouer dix fois le même webhook, interrompre le worker, désactiver le binding ou révoquer le fournisseur avant reprise puis tenter un nouveau webhook. | Idempotence, aucun second prospect, effet restant bloqué, admission ultérieure refusée et résultat terminal explicable. |
| `E2E-10` | P0 | Rejouer lectures et mutations avec `A-SALES-1`, `A-MANAGER`, un UUID de `A-SALES-2` et des UUID de `ORG-B`. | Capacités exactes, refus sans fuite, `404` inter-tenant et absence d’écriture vérifiée par relecture autorisée. |
| `E2E-11` | P0 | Parcourir Dashboard, Usage, Imports, Exports, Fournisseurs/Connexions, Pipeline, Opportunités et Tâches en `fr-CA` puis `en-CA`. | Même donnée et mêmes capacités ; libellés traduits ; navigation clavier, focus et zoom 200 % conformes. |
| `E2E-12` | P1 | Exécuter les purges avec données synthétiques arrivées à échéance : jobs, artefacts, usages et références d’ingestion. | Seules les données arrivées à échéance sont supprimées ou neutralisées ; audit, agrégats autorisés et données métier restent cohérents. |

### 5.2 Rapprochements obligatoires

Le rapport ne se limite pas à constater l’affichage. Il rapproche :

- `E2E-02` avec les cartes `DASH-01` à `DASH-08` et les événements d’audit ;
- `E2E-03` avec le rapport d’import, la quarantaine, les prospects créés et `platform.csv_import` ;
- `E2E-04` avec l’artefact, l’empreinte, les lignes produites et `platform.csv_export` ;
- `E2E-06` avec réservation, tentative, résultat, quota Redis et agrégat PostgreSQL ;
- `E2E-08` avec ingestion, job, provenance, permission et audit connecteur ;
- chaque tentative interdite avec une relecture autorisée de la version, des événements et des nombres avant/après.

Un écart de rapprochement est une anomalie, même si l’interface semble correcte.

### 5.3 Couverture des contrats d’incrément

| Contrat source | Scénarios repris | Preuves 4.6 principales |
| --- | --- | --- |
| 4.1 — Tableau de bord | `DASH-01` à `DASH-09` et jeux chiffrés associés | `E2E-01`, `E2E-02`, `E2E-06`, `E2E-11` et rapprochement serveur |
| 4.2 — Worker | `JOB-01` à `JOB-13` | `E2E-04`, `E2E-05`, `E2E-09`, `E2E-12` et tests de concurrence/reprise |
| 4.3 — Exports/imports | `EXP-01` à `EXP-10`, `IMP-01` à `IMP-04` | `E2E-03` à `E2E-05`, `E2E-10`, `E2E-12` |
| 4.4 — Usage | `USG-01` à `USG-15` | `E2E-06`, `E2E-07`, `E2E-10` à `E2E-12` |
| 4.5 — Connecteur pilote | `CON-01` à `CON-13` | `E2E-08` à `E2E-12`, `META-INT-01`, `META-EXT-01` |

Le dossier de traçabilité référence les tests automatiques existants pour les variantes techniques déjà démontrées.
Il ne réexécute manuellement que les étapes nécessaires à la preuve utilisateur, au rapprochement transversal et aux
réserves. Un scénario source sans test ni preuve 4.6 apparaît comme `NOT RUN` et empêche la clôture s’il est P0.

## 6. Reprise obligatoire des réserves de 3.4

| Réserve | Pri. | Exécution 4.6 | Critère de levée |
| --- | --- | --- | --- |
| `OPP-14-R1` | P0 | `A-SALES-2` tente `GET`, `PATCH` et transition sur l’opportunité de `A-SALES-1`, puis `A-ADMIN-AUTEUR` relit l’objet et ses événements. | Trois refus ; version, étape, montant et événements strictement inchangés. |
| `OPP-03-R1` | P0 | Soumettre uniquement `currency_code=ZZZ` sur une opportunité valide et conserver l’état avant/après. | Erreur attachée au champ devise, aucune écriture et aucune transition/audit métier induit. |
| `OPP-11-R1` | P0 | Saisir puis effacer progressivement une devise dans les filtres, observer Network, puis appliquer un code valide. | Aucune requête `415` pendant la saisie partielle ; filtre valide toujours fonctionnel. |
| `OPP-17-C-R1` | P0 | Produire les rapports axe exhaustifs des vues Phase 4 dans les deux locales avec données, vide, erreur et dialogue. | Zéro violation critique ou sérieuse ; anomalies mineures tracées et vues manuelles clavier/200 % réussies. |
| `REG-31-33-R1` | P0 | Rejouer import CSV, Kanban, chronologie/activités/tâches dans le parcours intégré. | Les trois régressions sont documentées et reliées aux preuves `E2E-02` et `E2E-03`. |

Ces identifiants restent uniques. Les anciens noms tels que `OPP-14-A` ou les scénarios `REG-31` à `REG-33` sont des
alias historiques, pas de nouvelles réserves. Les cinq lignes doivent être `PASS` pour un GO de phase ; elles ne
peuvent pas être transférées une seconde fois.

## 7. Sécurité, confidentialité et résilience

| ID | Pri. | Contrôle | Résultat exigé |
| --- | --- | --- | --- |
| `SEC4-01` | P0 | Accès croisés aux ressources 4.1 à 4.5 par URL, API et identifiant. | RLS et autorisations refusent sans révéler existence, statut, nombre ou métadonnée. |
| `SEC4-02` | P0 | Mutations sans CSRF, avec Origin non fiable, corps non JSON ou capacité insuffisante. | Refus avant effet, réponse `no-store`, aucune trace interne exposée. |
| `SEC4-03` | P0 | Inspection cookies, URL, stockage navigateur, console et artefact. | Aucun secret, jeton, donnée CRM, contenu fournisseur ou résultat Google persistant côté navigateur. |
| `SEC4-04` | P0 | Inspection des audits, usages, jobs et journaux après import, export et webhook. | Métadonnées fermées seulement ; aucun CSV brut, canal, référence Meta, token ou payload. |
| `SEC4-05` | P0 | Désactivation d’un membre et révocation d’un fournisseur/contrat pendant une session et un travail. | Nouvelle action refusée ; worker revalide ; aucune autorité conservée par une session ou un job ancien. |
| `SEC4-06` | P0 | Signatures Meta absente, fausse, corps modifié, événement périmé ou supérieur à la taille admise. | Aucun appel amont, job ou ingestion ; erreur générique et aucun oracle tenant. |
| `SEC4-07` | P0 | Concurrence et rejeu sur création, import, export, quota et ingestion. | Effet au plus une fois au niveau métier, conflits explicites et aucune écriture partielle. |
| `SEC4-08` | P0 | Vérification des privilèges SQL `prospect_app`, `prospect_worker` et fonctions `SECURITY DEFINER`. | Droits minimaux, RLS forcée, worker limité aux opérations nécessaires et `search_path` verrouillé. |
| `SEC4-09` | P1 | Indisponibilité PostgreSQL, Redis ou worker dans un environnement jetable. | Readiness non prête ou fonction fermée ; reprise contrôlée sans doublon ni fuite. |
| `SEC4-10` | P1 | Recherche de fichiers temporaires et exécution des purges. | Aucun artefact orphelin au-delà de sa durée, aucune suppression d’audit ou de donnée sous conservation. |

Un échec `SEC4-01` à `SEC4-08` entraîne un `NO-GO`, quelle que soit la réussite des autres parcours.

## 8. Accessibilité, langues et affichage

La matrice axe couvre au minimum les routes `/app/dashboard`, `/app/usage`, `/app/imports/history`, `/app/exports`,
`/app/compliance/sources`, `/app/pipeline`, `/app/opportunities`, `/app/tasks` et les dialogues critiques. Pour chaque
locale, elle examine les états chargement, vide, données, erreur, accès refusé et confirmation lorsque présents.

Les contrôles manuels P0 vérifient : lien d’évitement, ordre de tabulation, focus visible, restitution après dialogue,
annonce des erreurs et succès, tableaux, filtres, boutons occupés, navigation à 320 px et reflow à 200 %. Une couleur,
une icône ou une position ne peut être l’unique porteur d’information. Les nombres, dates, pourcentages et devises
changent de format selon la locale sans changer de valeur métier.

Le rapport axe brut est conservé comme preuve assainie. Une violation critique ou sérieuse bloque la phase. Une
violation mineure peut seulement soutenir un GO avec réserve si elle ne touche pas un parcours P0 et reçoit
responsable, échéance et test de non-régression prévu.

## 9. Pilote Meta : preuve interne et preuve externe

La campagne sépare deux lignes de décision :

1. `META-INT-01`, obligatoire, exécute challenge, signature, admission, file, reprise, mapping, provenance,
   permission, audit, arrêt et révocation contre un faux Meta déterministe ;
2. `META-EXT-01`, conditionnelle, exécute un lead de test sur un environnement Meta autorisé seulement après preuve
   de revue de l’application, permissions officielles, contrat, compte de test et autorisation d’appel.

L’absence d’autorisation externe place `META-EXT-01` en `BLOCKED`, avec le motif `EXTERNAL`. Elle n’autorise ni appel réel ni
activation du connecteur. La phase peut recevoir un GO avec réserve externe seulement si `META-INT-01` et tous les
autres P0 sont `PASS`, si le connecteur reste désactivé par configuration et si l’activation réelle reçoit une
décision distincte. Un échec observé lors d’un essai Meta autorisé est un `FAIL`, pas un blocage externe.

## 10. Verrou qualité de sortie sans skip

Le verrou final exécute sur des dépendances réelles :

- provisionnement des rôles PostgreSQL ;
- `alembic upgrade head`, downgrade contrôlé, reconstruction, `current` et `alembic check` ;
- Ruff, format Ruff et mypy ;
- tous les tests pytest avec PostgreSQL, Redis et Mailpit, puis contrôle JUnit `skipped=0` ;
- installation déterministe frontend, audit npm niveau élevé, ESLint ;
- tous les tests Vitest/axe, puis contrôle JUnit `skipped=0` ;
- tests navigateur 4.6, avec zéro `skip`, `todo`, `only`, quarantaine ou retry masquant un premier échec ;
- build Vite, contrôle des sources navigateur, inspection de l’artefact et `git diff --check` ;
- publication des rapports même en cas d’échec.

Le message `VERT` n’est recevable que si chaque étape réussit dans une même exécution. Une relance après erreur
produit un nouveau `run_id`; elle ne remplace pas silencieusement le rapport rouge. Le passage Azure utilise le même
commit que le verrou local, publie les JUnit et le dossier 4.6, puis fournit son URL et son identifiant.

Le contrôle « sans skip » porte sur backend, frontend et navigateur. Les marqueurs conditionnels liés aux services
réels restent acceptables dans le code seulement si l’environnement du verrou fournit ces services et exécute les
tests. Une collecte réduite, un filtre de nom, un test focalisé ou un fichier de rapport absent est un échec du verrou.

## 11. Dossier de preuves et traçabilité

Le dossier logique `test-results/phase-4-6/<run_id>/` contient :

- `manifest.json` : commit, état Git, révision Alembic, versions d’outils, configuration non secrète et horodatage ;
- rapports JUnit backend, frontend et navigateur ;
- synthèse des parcours et registre des réserves ;
- rapports axe par route et locale ;
- captures assainies nécessaires aux contrôles manuels ;
- synthèse de sécurité avec statuts et codes d’erreur ;
- référence du verrou local et du passage Azure ;
- anomalies, décisions et réserves avec responsable et échéance.

Un index Markdown relie chaque exigence à au moins un scénario et une preuve. Les preuves volumineuses générées ne
sont pas ajoutées à l’artefact applicatif. La publication CI des preuves est distincte de l’artefact Marketteo.

## 12. Sévérité, correction et décision de sortie

| Sévérité | Définition | Effet sur la décision |
| --- | --- | --- |
| Bloquante | Fuite inter-tenant, contournement d’autorisation, secret exposé, perte/corruption, double effet irréversible, verrou rouge | `NO-GO` |
| Majeure | Parcours P0 impossible ou résultat métier faux sans contournement sûr | `NO-GO` jusqu’à correction et rejeu |
| Mineure | Défaut localisé sans erreur métier ni sécurité, avec contournement acceptable | Réserve possible avec responsable et échéance |

Le verdict global est :

- `GO` : tous les P0, les cinq réserves, les contrôles sécurité et les deux verrous sur le même commit sont verts ;
  aucune anomalie bloquante ou majeure ouverte ;
- `GO avec réserves` : mêmes conditions, avec seulement des anomalies mineures bornées ou `META-EXT-01` bloqué par
  une autorisation externe, connecteur désactivé ;
- `NO-GO` : toute autre situation.

Le rapport publie séparément `Verdict Phase 4`, `Pilote Meta technique` et `Activation Meta réelle`. Aucun verdict
global n’est déduit automatiquement d’un nombre de cas réussis.

## 13. Plan d’implémentation du lot 4.6

1. Ajouter le préparateur et le nettoyeur idempotents du jeu de recette, sans donnée réelle.
2. Ajouter le harnais navigateur et les doubles locaux Google/Meta, puis les parcours P0 automatisables.
3. Ajouter les contrôles de réserves, sécurité, rapprochement et conservation manquants.
4. Étendre le verrou local et Azure au rapport navigateur et au refus de tout skip/focus/retry masqué.
5. Générer le manifeste, l’index de traçabilité et le registre d’exécution.
6. Exécuter la campagne manuelle bilingue, clavier, zoom et revue des preuves.
7. Corriger les anomalies, rejouer le périmètre requis puis le verrou complet.
8. Publier le rapport de recette et soumettre le verdict produit distinct de l’activation Meta.

## 14. Décisions validées par le responsable produit

| ID | Décision validée | Effet |
| --- | --- | --- |
| `P4.6-01` | Geler chaque campagne sur un commit, une tête Alembic, un manifeste et un jeu de données fictif déterministe à deux organisations. | Preuves reproductibles et isolation mesurable. |
| `P4.6-02` | Ajouter une couche navigateur pour les parcours P0, en complément des tests pytest/Vitest, avec PostgreSQL, Redis et Mailpit réels et fournisseurs externes simulés localement. | Véritable chaîne UI/API/worker/DB sans coût ni dépendance fournisseur. |
| `P4.6-03` | Refuser skip, todo, only, quarantaine et retry masquant un échec sur backend, frontend et navigateur ; toute relance reçoit un nouveau `run_id`. | Aucun vert artificiel ni disparition d’un premier échec. |
| `P4.6-04` | Exiger la levée en `PASS` des cinq réserves transférées de 3.4 ; aucun nouveau transfert n’est admis. | Dette de recette réellement soldée à la sortie de phase. |
| `P4.6-05` | Séparer `META-INT-01` obligatoire de `META-EXT-01` conditionnel ; autoriser au plus un GO avec réserve externe si le connecteur reste désactivé. | La qualité interne est prouvée sans inventer une approbation Meta. |
| `P4.6-06` | Rendre bloquants isolation tenant, capacités, CSRF, minimisation, révocation, privilèges SQL et idempotence ; vérifier l’absence d’écriture après chaque refus critique. | Porte de sécurité explicite et vérifiable. |
| `P4.6-07` | Exiger axe par vue et locale, parcours clavier et zoom 200 % ; aucune violation critique ou sérieuse au verdict. | Levée de `OPP-17-C-R1` et expérience bilingue contrôlée. |
| `P4.6-08` | Prononcer le verdict seulement après verrou local et Azure verts sur le même commit, preuves publiées et décisions distinctes Phase 4 / pilote technique / activation Meta. | Sortie auditable et absence d’ambiguïté opérationnelle. |

Le responsable produit a validé explicitement les huit décisions `P4.6-01` à `P4.6-08` le 25 septembre 2026 et a donné
le GO d’implémentation le même jour. Cette autorisation lance l’outillage et les scénarios ; elle ne vaut pas verdict de
recette ni autorisation Meta externe.

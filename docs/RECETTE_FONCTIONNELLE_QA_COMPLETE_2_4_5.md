# Marketteo CRM — Recette fonctionnelle QA complète

| Métadonnée | Valeur à renseigner |
| --- | --- |
| Version | 2.0 |
| Périmètre | CRM V1 livré jusqu’à l’itération 2.4.5 incluse |
| Environnement | Local / QA / préproduction : __________ |
| URL testée | __________ |
| Révision Git | __________ |
| Migration | `20260813_0008 (head)` |
| Date | __________ |
| Testeur QA | __________ |
| Navigateur, version et résolution | __________ |
| Décision | GO / NO-GO / GO avec réserves |

## 1. Objet et règles d’exécution

Ce document constitue le parcours de recette fonctionnelle de référence pour Marketteo CRM jusqu’à l’itération 2.4.5.
Il couvre l’authentification, les organisations, les rôles, les invitations, le multi-organisation, l’audit,
la suspension/réactivation, l’historique des invitations, la recherche Google bornée, la sécurité observable,
l’accessibilité, le responsive, la résilience et le verrou qualité.

Statuts à utiliser :

- **PASS** : résultat conforme à l’attendu ;
- **FAIL** : résultat différent de l’attendu ;
- **BLOCKED** : un prérequis empêche l’exécution ;
- **NOT RUN** : test non exécuté ;
- **N/A** : test hors périmètre de l’environnement, avec justification.

Une anomalie est bloquante lorsqu’elle permet une fuite de secret, un franchissement d’organisation ou de rôle,
une perte de données, un appel Google incontrôlé ou empêche l’authentification.

Précautions :

- utiliser uniquement des comptes et courriels de test ;
- ne jamais capturer de mot de passe, cookie, jeton CSRF, jeton d’invitation ou clé Google ;
- ne pas copier un lien Mailpit ailleurs que dans le navigateur de recette ;
- ne pas modifier PostgreSQL directement pour faire réussir un scénario fonctionnel ;
- utiliser un suffixe `<RUN>` unique, par exemple `20260814-QA01` ;
- n’exécuter qu’un seul Text Search Google réel pendant la campagne ;
- consigner une preuve assainie pour chaque cas P0.

## 2. Jeu de données recommandé

| Référence | Exemple | Usage |
| --- | --- | --- |
| `PLATFORM` | `qa.platform.<RUN>@example.ca` | Administrateur de plateforme |
| `ORG-A` | `QA Alpha <RUN>` | Organisation principale |
| `ORG-B` | `QA Bêta <RUN>` | Deuxième organisation |
| `ORG-R` | `QA Renvoi <RUN>` | Renvoi d’invitation |
| `ORG-V` | `QA Révocation <RUN>` | Révocation d’invitation |
| `ADMIN` | `qa.admin.<RUN>@example.ca` | Administrateur de ORG-A et ORG-B |
| `MANAGER` | `qa.manager.<RUN>@example.ca` | Gestionnaire de ORG-A |
| `SALES` | `qa.sales.<RUN>@example.ca` | Commercial de ORG-A |
| `SECOND-ADMIN` | `qa.admin2.<RUN>@example.ca` | Second administrateur |
| `NO-ORG` | `qa.noorg.<RUN>@example.ca` | Membre ensuite désactivé |
| `PENDING` | `qa.pending.<RUN>@example.ca` | Invitation renvoyée ou révoquée |

Tous les mots de passe de recette doivent comporter entre 12 et 128 caractères.

## 3. Matrice fonctionnelle attendue

| Fonction | Plateforme seule | Admin | Gestionnaire | Commercial | Sans organisation |
| --- | --- | --- | --- | --- | --- |
| Administration plateforme | Oui | Non | Non | Non | Non |
| Recherche Google | Non | Oui | Oui | Oui | Non |
| Organisation | Non | Lecture/édition | Lecture | Lecture | Non |
| Membres | Non | Lecture/édition | Lecture | Non | Non |
| Invitations membres | Non | Lecture/édition | Non | Non | Non |
| Audit organisation | Non | Oui | Oui | Non | Non |
| Audit plateforme | Oui | Non | Non | Non | Non |
| Compte et déconnexion | Oui | Oui | Oui | Oui | Restreint |

## 4. Environnement et services

### ENV-01 — Services

1. Dans WSL, exécuter `docker compose ps`.
2. Vérifier que PostgreSQL, Redis et Mailpit sont `healthy`.
3. Ouvrir `http://127.0.0.1:8000/api/health/live`.
4. Ouvrir `http://127.0.0.1:8000/api/health/ready`.

Attendu : le backend répond et la readiness indique PostgreSQL et Redis à `ok`.

### ENV-02 — Migration

Dans PowerShell :

```powershell
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:55432/prospect"
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
```

Attendu : `20260813_0008 (head)`.

### ENV-03 — Interfaces

1. Ouvrir `http://localhost:5173`.
2. Ouvrir `http://127.0.0.1:8025`.
3. Vérifier l’absence d’erreurs répétitives dans les terminaux.

Attendu : écran de connexion et Mailpit accessibles, services stables.

## 5. Pages publiques et routage

### PUB-01 — Protection des routes

1. Sans session, ouvrir `/`, `/app/search` et `/app/audit`.
2. Observer la redirection.

Attendu : redirection vers `/login`, sans affichage fugitif de contenu protégé.

### PUB-02 — Pages légales

1. Ouvrir `/conditions.html` puis `/confidentialite.html`.
2. Vérifier les liens croisés et le retour vers l’application.
3. Vérifier les mentions Google, la conservation des données et l’absence d’export actif.

Attendu : pages lisibles, cohérentes et sans lien cassé.

### ROUTE-01 — Erreurs contrôlées

1. Ouvrir `/app/inconnue` avec une session valide.
2. Ouvrir une route interdite avec un rôle insuffisant.

Attendu : pages 404 et 403 contrôlées, sans trace technique.

## 6. Authentification et compte

### AUTH-01 — Échec générique

1. Essayer un courriel inexistant.
2. Essayer un compte valide avec un mauvais mot de passe.

Attendu : même message générique, sans révéler l’existence d’un compte.

### AUTH-02 — Connexion et restauration

1. Se connecter avec un compte valide.
2. Actualiser la page.
3. Ouvrir « Mon compte ».

Attendu : session restaurée ; identité, rôle, organisations et organisation active exacts ; aucun secret affiché.

### AUTH-03 — Déconnexion

1. Se déconnecter.
2. Utiliser Retour navigateur.
3. Ouvrir directement une route protégée.

Attendu : ancienne session inutilisable et retour à la connexion.

### AUTH-04 — Compte sans organisation active

1. Désactiver ultérieurement la seule appartenance de `NO-ORG`.
2. Se reconnecter avec ce compte.

Attendu : écran « Aucune organisation accessible » et seule la déconnexion est possible.

## 7. Administration plateforme et provisioning

### PLAT-01 — Navigation plateforme

1. Se connecter comme `PLATFORM`.
2. Vérifier les entrées du menu.
3. Ouvrir `/app/platform/organizations`.

Attendu : Plateforme et Compte visibles ; fonctions locataires absentes si aucune appartenance.

### PLAT-02 — Validation du formulaire

1. Soumettre les champs obligatoires vides.
2. Tester un courriel invalide.
3. Tester un fuseau invalide.

Attendu : aucune organisation ni invitation créée.

### PLAT-03 — Création de ORG-A

1. Saisir `ORG-A`, `fr-CA`, `America/Toronto` et le courriel `ADMIN`.
2. Cliquer une seule fois sur la création.

Attendu : une seule organisation en activation, une invitation active et une livraison envoyée.

### PLAT-04 — Courriel initial

1. Ouvrir Mailpit.
2. Rechercher le message de `ADMIN`.
3. Vérifier expéditeur, organisation, rôle et lien.

Attendu : un seul lien, aucun mot de passe ni secret.

### PLAT-05 — Renvoi initial

1. Créer `ORG-R` avec `PENDING`.
2. Conserver l’ancien lien.
3. Renvoyer l’invitation.
4. Tester l’ancien puis le nouveau lien.

Attendu : ancien lien invalide, nouveau lien valide, aucun doublon d’organisation.

### PLAT-06 — Révocation initiale

1. Créer `ORG-V` avec un courriel unique.
2. Cliquer Révoquer puis annuler.
3. Recommencer et confirmer.
4. Tester le lien.

Attendu : annulation sans effet, puis invitation révoquée et lien refusé.

## 8. Acceptation des invitations

### INV-01 — Nouveau compte

1. Ouvrir le lien initial de `ADMIN`.
2. Vérifier la disparition immédiate du jeton dans l’adresse.
3. Vérifier organisation et rôle.
4. Tester deux mots de passe différents.
5. Tester un mot de passe de moins de 12 caractères.
6. Saisir un nom et un mot de passe valide.
7. Accepter.

Attendu : compte créé, ORG-A active, session ouverte dans ORG-A.

### INV-02 — Lien consommé ou invalide

1. Se déconnecter puis réouvrir le lien accepté.
2. Ouvrir `/accept-invitation` sans jeton.
3. Tester si possible un lien expiré et un lien révoqué.

Attendu : même état terminal générique, aucun détail sensible.

### INV-03 — Compte existant

1. Créer ORG-B avec une invitation destinée à `ADMIN`.
2. Ouvrir le lien déconnecté.
3. Se connecter depuis la page d’invitation.
4. Accepter.

Attendu : nouvelle appartenance, ORG-B active, aucun second compte.

### INV-04 — Mauvais compte connecté

1. Ouvrir une invitation avec la session d’un autre compte.
2. Tenter de poursuivre.
3. Se déconnecter puis utiliser le destinataire attendu.

Attendu : seul le destinataire peut accepter.

## 9. Organisation active

### ORG-01 — Droits d’affichage

1. Ouvrir Organisation comme Admin, Gestionnaire et Commercial.

Attendu : tous voient les informations ; seul Admin peut modifier.

### ORG-02 — Modification

1. Modifier temporairement le nom, la langue ou le fuseau.
2. Enregistrer et actualiser.
3. Restaurer les valeurs initiales.

Attendu : valeurs persistantes, version serveur respectée, aucune autre organisation modifiée.

### ORG-03 — Validation

1. Tester un nom vide.
2. Tester un fuseau invalide.

Attendu : refus lisible, sans trace technique.

### ORG-04 — Concurrence

1. Ouvrir ORG-A dans deux fenêtres.
2. Modifier dans la première.
3. Modifier la version devenue obsolète dans la seconde.

Attendu : conflit explicite, aucun écrasement silencieux, rechargement possible.

## 10. Membres, rôles et invitations

### MINV-01 — Création des invitations

Inviter `MANAGER`, `SALES`, `SECOND-ADMIN` et `NO-ORG` avec les rôles prévus.

Attendu : une invitation par courriel, état et livraison visibles, aucun identifiant technique affiché.

### MINV-02 — Doublon

1. Tenter de recréer une invitation active identique.

Attendu : refus contrôlé et aucun doublon.

### MINV-03 — Courriels

1. Vérifier chaque message dans Mailpit.

Attendu : destinataire, organisation et rôle exacts ; aucun secret.

### MINV-04 — Renvoi et révocation

1. Renvoyer une invitation et tester les deux liens.
2. Révoquer une autre invitation, d’abord en annulant puis en confirmant.

Attendu : ancien lien invalidé après renvoi ; lien révoqué refusé.

### MINV-05 — Acceptation

1. Accepter les invitations de `MANAGER`, `SALES`, `SECOND-ADMIN` et `NO-ORG`.
2. Actualiser Membres et Invitations.

Attendu : membres actifs avec les rôles prévus ; invitations acceptées non actionnables.

### MEM-01 — Gestionnaire

1. Se connecter comme `MANAGER`.
2. Ouvrir Membres et Organisation.

Attendu : membres et organisation en lecture seule ; aucun onglet de gestion des invitations.

### MEM-02 — Commercial

1. Se connecter comme `SALES`.
2. Vérifier le menu.
3. Ouvrir directement `/app/admin/users`, `/app/audit` et `/app/platform/organizations`.

Attendu : Membres et Audit absents ; liens profonds refusés par une 403 contrôlée.

### MEM-03 — Changement de rôle

1. Comme Admin, modifier `SALES` de Commercial vers Gestionnaire.
2. Reconnecter `SALES`.
3. Vérifier les nouvelles capacités.
4. Restaurer Commercial.

Attendu : capacités recalculées après renouvellement de session.

### MEM-04 — Désactivation

1. Désactiver `NO-ORG`, d’abord en annulant puis en confirmant.
2. Utiliser son ancienne session.
3. Le reconnecter.

Attendu : ancienne session refusée ; écran sans organisation après reconnexion.

### MEM-05 — Protection du dernier Admin

1. Lorsque ORG-A n’a qu’un Admin actif, tenter de le rétrograder ou de le désactiver.

Attendu : refus indiquant qu’un second Admin actif est requis.

### MEM-06 — Auto-rétrogradation

1. Activer `SECOND-ADMIN`.
2. Depuis `ADMIN`, rétrograder son propre rôle.
3. Se reconnecter.
4. Faire restaurer le rôle par `SECOND-ADMIN`.

Attendu : mutation autorisée avec second Admin ; session recalculée.

### MEM-07 — Concurrence

1. Ouvrir le même membre dans deux fenêtres Admin.
2. Modifier dans la première puis avec la version obsolète dans la seconde.

Attendu : conflit explicite, aucune mutation silencieuse.

## 11. Multi-organisation et isolation

### MULTI-01 — Sélecteur

1. Avec `ADMIN` actif dans ORG-A et ORG-B, se connecter.
2. Vérifier le bandeau et Mon compte.

Attendu : deux organisations visibles, une seule active.

### MULTI-02 — Changement d’organisation

1. Basculer de ORG-A vers ORG-B puis revenir.

Attendu : contexte remplacé atomiquement, données de la seule organisation active.

### MULTI-03 — Isolation

1. Créer un membre uniquement dans ORG-A.
2. Lister les membres de A puis de B.
3. Tester une URL profonde et Retour navigateur.

Attendu : aucune donnée de A visible dans B, même transitoirement.

### MULTI-04 — Échec réseau

1. Bloquer temporairement la requête de changement d’organisation.
2. Demander ORG-B puis rétablir le réseau.

Attendu : erreur contrôlée, ORG-A reste active, aucune interface hybride.

### MULTI-05 — Purge Google

1. Après une recherche Google, changer d’organisation.
2. Revenir sur Recherche.

Attendu : résultats, carte, filtre et requêtes en vol supprimés.

## 12. Audit de l’organisation

Créer d’abord plusieurs événements : modification d’organisation, invitation, acceptation ou révocation, changement de
rôle et changement d’organisation active.

### AUD-ORG-01 — Consultation et filtres

1. Ouvrir `/app/audit` comme Admin.
2. Vérifier l’ordre antéchronologique.
3. Tester période, action, type d’entité et acteur.
4. Ouvrir les détails.
5. Cliquer Actualiser puis Charger la suite si disponible.

Attendu : événements cohérents, aucun doublon, curseur et filtres correctement appliqués.

### AUD-ORG-02 — Capacités

1. Rejouer comme Gestionnaire, Commercial et compte sans organisation.

Attendu : Admin et Gestionnaire autorisés ; Commercial et compte sans organisation refusés.

### AUD-ORG-03 — Confidentialité

Vérifier l’absence de courriel, téléphone, site Web, clé, contenu Google, jeton ou cookie dans la projection.

Attendu : uniquement les métadonnées autorisées et une fenêtre de trente jours par défaut.

## 13. Audit de plateforme

### AUD-PLAT-01 — Consultation

1. Ouvrir `/app/platform/audit` comme `PLATFORM`.
2. Vérifier les événements de provisioning, invitations initiales, suspension et réactivation.
3. Tester période, action, entité et pagination.

Attendu : portée plateforme correcte, sans données locataires internes ni donnée sensible.

### AUD-PLAT-02 — Accès interdit

1. Ouvrir la route comme simple Admin d’organisation.

Attendu : 403 et aucune donnée chargée.

## 14. Suspension et réactivation

### SUSP-01 — Suspension

1. Choisir une organisation active et conserver une session membre ouverte.
2. Comme `PLATFORM`, cliquer Suspendre.
3. Tenter sans raison.
4. Choisir une raison valide et, facultativement, une référence courte.
5. Confirmer.

Attendu : raison obligatoire, statut Suspendue et version incrémentée.

### SUSP-02 — Blocage immédiat

1. Revenir dans la session membre ouverte.
2. Tenter une page locataire et une recherche Google.

Attendu : session et routes locataires bloquées ; aucun appel Google fournisseur.

### SUSP-03 — Autre organisation

1. Si le compte possède une autre organisation active, basculer vers elle.

Attendu : l’autre organisation reste utilisable et aucune donnée suspendue n’est visible.

### REACT-01 — Réactivation

1. Comme `PLATFORM`, réactiver avec une raison.
2. Reconnecter un membre encore actif.

Attendu : organisation Active et accès restauré pour les membres actifs seulement.

### REACT-02 — États terminaux et audit

1. Vérifier qu’un membre désactivé reste désactivé.
2. Vérifier que les invitations acceptées, révoquées ou expirées restent terminales.
3. Ouvrir l’audit plateforme.

Attendu : un événement `organization.suspended` et un événement `organization.reactivated`, sans doublon sur rejeu.

## 15. Historique des invitations

### HIST-01 — En cours

1. Ouvrir Membres puis Invitations.
2. Sélectionner « En cours ».

Attendu : seules les invitations actionnables sont visibles.

### HIST-02 — Tout l’historique

1. Sélectionner « Tout l’historique ».
2. Examiner les invitations actives, acceptées, révoquées et expirées.
3. Charger la suite si disponible.

Attendu : états et dates fiables ; aucune action sur une invitation terminale ; aucun doublon.

## 16. Recherche Google facturable bornée

Les étapes `GOOG-03` à `GOOG-06` ne doivent être exécutées qu’une seule fois pendant la campagne.

### GOOG-01 — Ouverture sans appel

1. Ouvrir Recherche avec une organisation active.
2. Vérifier le badge API configurée et les compteurs à zéro.

Attendu : aucun appel Google au simple affichage.

### GOOG-02 — Validation locale

1. Tester un type vide et des coordonnées ou rayon invalides.

Attendu : validation lisible, compteur à zéro, aucun appel facturable.

### GOOG-03 — Recherche réelle unique

1. Saisir `plombier`, latitude `46.8139`, longitude `-71.208`, rayon `15 km`.
2. Cliquer une seule fois sur Rechercher.
3. Attendre sans recliquer.

Attendu : exactement un Text Search, 20 résultats maximum, compteur à 1, aucun suivi de `nextPageToken`.

### GOOG-04 — Contenu et conformité

1. Examiner plusieurs résultats.
2. Vérifier nom, adresse, distance, type, état et lien Maps lorsqu’ils existent.
3. Rechercher téléphone et site Web.
4. Examiner le bouton Export et l’attribution.

Attendu : aucun téléphone/site Web ; Exporter Excel visible mais désactivé ; attribution Google Maps visible ; aucun
terme « générateur » ou « leads ».

### GOOG-05 — Filtre local et purge

1. Utiliser puis effacer le filtre local.
2. Actualiser la page après collecte des preuves.

Attendu : aucun appel supplémentaire ; effacement restaure les lignes ; actualisation supprime résultats et carte.

### GOOG-06 — Carte

1. Observer la carte produite.

Attendu : au plus une Maps Static ; échec éventuel lisible et sans nouvelle tentative facturable automatique.

### GOOG-07 — Profils interdits et anciennes routes

1. Tester Recherche avec `PLATFORM` seul puis `NO-ORG`.
2. Vérifier que `/api/leads/search` et `/api/leads/export` ne sont pas disponibles.

Attendu : aucun appel fournisseur et anciennes routes absentes.

## 17. Confidentialité et sécurité observables

### SEC-01 — Stockages navigateur

Examiner Local Storage, Session Storage, IndexedDB, Cache Storage et Service Workers après les parcours.

Attendu : aucun secret, jeton, résultat Google, filtre d’audit, curseur ou ressource CRM persisté.

### SEC-02 — URL et erreurs

Vérifier toutes les adresses et erreurs visibles.

Attendu : aucun secret ou identifiant d’autorité dans l’URL ; aucune trace Python, SQL ou SMTP.

### SEC-03 — Réseau

Examiner les réponses Auth, Audit, Google et Administration sans copier les valeurs sensibles.

Attendu : `Cache-Control: no-store`, cookie de session `HttpOnly`, clés Google absentes.

### SEC-04 — Double soumission

Double-cliquer rapidement sur Connexion, Créer organisation, Créer invitation, Renvoyer, Suspendre et Rechercher avec
des jeux de données dédiés.

Attendu : un seul effet métier, aucun doublon et aucun double appel Google.

### SEC-05 — Console et isolation

1. Observer la console pendant la campagne.
2. Tester une URL d’administration avec un rôle inférieur et entre deux organisations.

Attendu : aucune erreur React ou donnée sensible ; le serveur refuse tout accès non autorisé.

## 18. Accessibilité

Exécuter les contrôles critiques sans souris.

### A11Y-01 — Navigation générale

1. Tester Tab, Maj+Tab et le lien Aller au contenu principal.
2. Vérifier l’ordre et la visibilité du focus.

### A11Y-02 — Menu mobile

1. Ouvrir le menu au clavier.
2. Fermer avec Échap puis avec le bouton.

Attendu : focus géré et restitué, arrière-plan non actionnable.

### A11Y-03 — Onglets et dialogues

1. Utiliser Gauche, Droite, Home et End dans Membres/Invitations.
2. Ouvrir un dialogue sensible.
3. Tester Tab, Maj+Tab et Échap.

Attendu : onglets annoncés ; focus piégé dans le dialogue puis restitué.

### A11Y-04 — Erreurs et lecteur d’écran

1. Provoquer une erreur de connexion et de formulaire.
2. Vérifier le focus et l’annonce.
3. Contrôler les pages principales avec Narrateur ou NVDA si disponible.

Attendu : erreurs compréhensibles sans couleur et noms accessibles corrects.

## 19. Responsive, zoom et compatibilité

Tester Connexion, Invitation, Recherche, Compte, Organisation, Membres, Invitations, Audit, Plateforme, 403 et 404 :

1. à `320 × 568` CSS pixels ;
2. à `1280 × 720` avec zoom navigateur `200 %` ;
3. dans Chrome ou Edge ;
4. idéalement dans Firefox comme navigateur secondaire.

Attendu : aucun défilement horizontal global, chevauchement, texte essentiel tronqué ou action inaccessible ; contraste
et focus conformes.

## 20. Résilience

### RES-01 — Services

Dans un environnement jetable et avec accord de l’exploitant, arrêter Redis ou PostgreSQL, vérifier la readiness et
une action, puis redémarrer.

Attendu : readiness non prête, erreur contrôlée, récupération après redémarrage.

### RES-02 — Réseau et idempotence

1. Passer hors ligne pendant une mutation dédiée.
2. Revenir en ligne et réessayer explicitement.

Attendu : aucune relance automatique et un seul objet final.

### RES-03 — Purge de contexte

1. Commencer un formulaire sans soumettre.
2. Changer d’organisation ou se déconnecter.

Attendu : saisie temporaire purgée.

### RES-04 — Session révoquée

1. Désactiver un membre pendant que sa session est ouverte.
2. Tenter de naviguer ou de muter depuis cette session.

Attendu : aucune action autorisée et droits recalculés à la reconnexion.

### RES-05 — Conflits de version

Provoquer un conflit Organisation puis Membre avec deux fenêtres.

Attendu : aucun écrasement silencieux, aucun retry automatique, récupération claire.

## 21. Verrou qualité local 2.4.5

Le port `55432` est actuellement utilisé par la base de développement et par la composition isolée du verrou qualité.
Arrêter les serveurs Vite et la composition de développement avant le verrou :

```bash
docker compose stop
```

Puis, depuis PowerShell :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-QualityGateLocal.ps1
```

Attendus obligatoires :

- Alembic à `20260813_0008 (head)` ;
- 185 tests pytest, zéro échec et zéro skip ;
- Ruff, format Ruff et mypy verts ;
- 133 tests Vitest, zéro échec et zéro skip ;
- ESLint et audit npm verts ;
- build Vite et contrôles d’artefact verts ;
- message final `Verrou qualité local 2.4.5 : VERT`.

## 22. Azure Pipelines

1. Sélectionner exactement la révision Git testée localement.
2. Lancer Azure Pipelines.
3. Vérifier toutes les étapes et les rapports JUnit.
4. Vérifier qu’aucun test obligatoire n’est ignoré.
5. Vérifier que l’artefact `MarketteoCRM` n’est publié qu’après toutes les barrières vertes.
6. Consigner l’identifiant et le lien du passage.

Attendu : pipeline vert sans relance inexpliquée et sans clé Google injectée.

## 23. Clôture de campagne

1. Se déconnecter de tous les comptes.
2. Fermer tous les liens d’invitation.
3. Vérifier qu’aucune preuve ne contient de secret.
4. Consigner les comptes et organisations créés pour nettoyage ultérieur.
5. Ne rien supprimer directement en base.
6. Vérifier qu’un seul Text Search et au plus une Maps Static ont été consommés.
7. Compiler les anomalies par sévérité.
8. Renseigner la décision finale.

Le GO exige :

- tous les cas P0 exécutés et PASS ;
- aucune anomalie bloquante ou majeure ouverte ;
- aucun franchissement d’organisation ou de rôle ;
- verrou local et Azure verts sur la même révision ;
- aucun test obligatoire ignoré ;
- conformité Google confirmée ;
- recette signée.

## 24. Registre d’exécution

Copier une ligne par cas exécuté.

| ID | Statut | Date/heure | Testeur | Preuve assainie | Anomalie | Commentaire |
| --- | --- | --- | --- | --- | --- | --- |
| __________ | PASS / FAIL / BLOCKED / N/A | __________ | __________ | __________ | __________ | __________ |

## 25. Modèle d’anomalie

```text
Titre : [ID] Résumé précis
Sévérité : Bloquante / Majeure / Mineure
Révision et environnement :
Navigateur, version et résolution :
Compte et rôle utilisés, sans mot de passe :
Organisation active :
Préconditions :
Étapes exactes :
Résultat observé :
Résultat attendu :
Reproductibilité : x/y
Impact utilisateur, sécurité ou facturation :
Preuves assainies :
Request ID non sensible :
Contournement éventuel :
```

## 26. Signatures

| Rôle | Nom | Décision | Date | Signature ou commentaire |
| --- | --- | --- | --- | --- |
| Responsable QA | __________ | GO / NO-GO | __________ | __________ |
| Responsable produit | __________ | GO / NO-GO | __________ | __________ |
| Responsable technique | __________ | GO / NO-GO | __________ | __________ |
| Sécurité / exploitation | __________ | GO / NO-GO | __________ | __________ |


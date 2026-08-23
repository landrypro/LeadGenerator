1. Vérifier l’environnement
Vérifier les services WSL :
docker compose ps
Vérifier la migration dans PowerShell :
$env:MIGRATION_DATABASE_URL = "postgresql+asyncpg://prospect:prospect-development-only@127.0.0.1:55432/prospect"

.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
Attendu :
20260813_0008 (head)
Vérifier le backend :
Invoke-RestMethod "http://127.0.0.1:8000/api/health/live"
Invoke-RestMethod "http://127.0.0.1:8000/api/health/ready"
Attendu : PostgreSQL et Redis à ok.
Vérifier les interfaces :Marketteo : http://localhost:5173
Mailpit : http://127.0.0.1:8025

2. Pages publiques et protection des routes
Sans être connecté, ouvrir :
http://localhost:5173/
http://localhost:5173/app/search
http://localhost:5173/app/audit
Vérifier la redirection vers /login.
Vérifier qu’aucun contenu protégé ne s’affiche brièvement.
Ouvrir les pages légales :
http://localhost:5173/conditions.html
http://localhost:5173/confidentialite.html
Vérifier les liens croisés, les mentions Google, la conservation des données et l’absence d’export actif.
3. Authentification
Essayer un courriel inexistant.
Essayer un compte existant avec un mauvais mot de passe.
Vérifier que le même message générique est affiché.
Se connecter avec un compte valide.
Actualiser la page et vérifier la restauration de session.
Ouvrir « Mon compte » et vérifier :nom affiché ;
courriel ;
rôle ;
organisations accessibles ;
organisation active.

Se déconnecter.
Utiliser le bouton Retour du navigateur.
Vérifier qu’aucune route protégée ne reste accessible.
4. Administration de plateforme
Avec l’administrateur de plateforme :
Se connecter.
Vérifier que le menu propose « Plateforme » et « Compte ».
Vérifier que la recherche Google et les fonctions locataires ne sont pas accessibles sans appartenance.
Ouvrir la liste des organisations.
Vérifier les statuts :Activation en cours ;
Active ;
Suspendue.

Tester le formulaire avec :champs obligatoires vides ;
courriel invalide ;
fuseau invalide.

Vérifier qu’aucune organisation n’est créée lors d’une validation incorrecte.
5. Provisioning d’une organisation
Utiliser un suffixe unique, par exemple QA-20260814.
Créer une organisation :
Nom : QA Alpha 20260814
Langue : fr-CA
Fuseau : America/Toronto
Administrateur : une adresse de test
Cliquer une seule fois sur la création.
Vérifier :une seule organisation créée ;
statut « Activation en cours » ;
invitation active ;
livraison indiquée comme envoyée.

Ouvrir Mailpit.
Vérifier :destinataire exact ;
nom de l’organisation ;
rôle Administrateur ;
présence d’un seul lien ;
absence de mot de passe ou secret dans le courriel.

6. Acceptation de l’invitation initiale
Ouvrir le lien depuis Mailpit.
Vérifier que le jeton disparaît immédiatement de l’adresse du navigateur.
Vérifier le nom de l’organisation et le rôle proposé.
Tester deux mots de passe différents.
Tester un mot de passe de moins de 12 caractères.
Saisir ensuite un nom et un mot de passe valide.
Accepter l’invitation.
Vérifier :création du compte ;
activation de l’organisation ;
connexion automatique ;
organisation active correcte.

Se déconnecter et réouvrir le même lien.
Vérifier que l’invitation consommée est refusée sans révéler de détail sensible.
7. Renvoi et révocation des invitations
Pour une invitation encore active :
Renvoi
Conserver l’ancien lien.
Cliquer « Renvoyer ».
Vérifier la réception d’un nouveau message dans Mailpit.
Essayer l’ancien lien : il doit être refusé.
Essayer le nouveau lien : il doit être valide.
Vérifier qu’aucun doublon d’organisation ou d’invitation active n’est créé.
Révocation
Cliquer « Révoquer ».
Annuler la confirmation.
Vérifier que l’invitation reste active.
Recommencer et confirmer.
Essayer le lien.
Vérifier qu’il est refusé et que l’état devient « Révoquée ».
8. Gestion de l’organisation active
Avec un administrateur d’organisation :
Ouvrir « Organisation ».
Vérifier le nom, la langue, le fuseau, le statut et la version.
Modifier temporairement le nom, la langue ou le fuseau.
Enregistrer.
Actualiser la page.
Vérifier la persistance.
Restaurer les valeurs initiales.
Tester un nom vide et un fuseau invalide.
Vérifier que la modification est refusée proprement.
Avec un gestionnaire et un commercial :
Gestionnaire : organisation en lecture seule.
Commercial : organisation en lecture seule.
Aucun des deux ne doit voir le formulaire de modification.
9. Invitations de membres
Depuis « Membres et invitations », inviter :
un Gestionnaire ;
un Commercial ;
un second Administrateur ;
un utilisateur destiné au test de désactivation.
Pour chaque invitation :
Vérifier l’adresse et le rôle.
Cliquer une seule fois.
Vérifier qu’un seul courriel est envoyé.
Vérifier que la tentative de recréer une invitation active identique est refusée.
Accepter chaque invitation depuis Mailpit.
Vérifier que chaque utilisateur apparaît dans la liste des membres avec le bon rôle.
10. Rôles et capacités
Gestionnaire
Se connecter comme Gestionnaire.
Vérifier l’accès en lecture aux membres.
Vérifier l’absence des boutons de modification.
Vérifier l’absence de l’onglet de gestion des invitations.
Vérifier l’accès à l’audit de l’organisation.
Commercial
Se connecter comme Commercial.
Vérifier que « Membres » et « Audit » sont absents du menu.
Ouvrir directement :
/app/admin/users
/app/audit
/app/platform/organizations
Vérifier une page 403 contrôlée.
Vérifier que Recherche et Organisation restent accessibles.
Modification d’un rôle
Comme Admin, modifier Commercial vers Gestionnaire.
Reconnecter cet utilisateur.
Vérifier ses nouvelles capacités.
Restaurer son rôle Commercial.
Désactivation
Désactiver un membre.
Annuler une première fois.
Refaire et confirmer.
Utiliser son ancienne session.
Vérifier que cette session est refusée.
Se reconnecter.
Vérifier l’écran « Aucune organisation accessible ».
Dernier administrateur
Tenter de rétrograder ou désactiver le dernier Admin actif.
Vérifier que l’opération est refusée.
Ajouter un second Admin.
Refaire la rétrogradation.
Vérifier qu’elle réussit et que la session est recalculée.
11. Multi-organisation
Créer une seconde organisation vers un compte déjà existant.
Ouvrir le lien d’invitation.
Se connecter depuis la page d’invitation.
Accepter l’appartenance.
Vérifier que le sélecteur affiche les deux organisations.
Basculer de l’organisation A vers B.
Vérifier immédiatement :nom de l’organisation ;
rôle actif ;
membres ;
invitations ;
audit ;
résultats Google effacés.

Revenir vers l’organisation A.
Vérifier qu’aucune donnée de A n’apparaît dans B et inversement.
Tester également le bouton Retour du navigateur.
Simuler une erreur réseau pendant le changement d’organisation.
Vérifier que l’ancienne organisation reste active sans interface hybride.
12. Audit de l’organisation
Produire d’abord quelques actions :
modification de l’organisation ;
création et renvoi d’une invitation ;
acceptation ou révocation d’une invitation ;
modification d’un rôle ;
changement d’organisation active.
Ensuite :
Se connecter comme Admin.
Ouvrir /app/audit.
Vérifier l’ordre antéchronologique.
Vérifier les actions et entités affichées.
Tester les filtres :période ;
action ;
type d’entité ;
acteur.

Ouvrir les détails d’un événement.
Vérifier l’absence de :courriel ;
téléphone ;
site Web ;
clé API ;
contenu Google ;
jeton ou cookie.

Cliquer « Actualiser ».
Tester « Charger la suite » si disponible.
Vérifier l’absence de doublons.
Rejouer avec :
Gestionnaire : accès autorisé ;
Commercial : accès refusé ;
utilisateur sans organisation : accès refusé.
13. Audit de plateforme
Avec l’administrateur de plateforme :
Ouvrir /app/platform/audit.
Vérifier les événements de plateforme :création d’organisation ;
invitations initiales ;
suspension ;
réactivation.

Tester période, action, entité et pagination.
Vérifier que les opérations locataires internes ne sont pas exposées comme des données plateforme.
Vérifier l’absence de courriel et de données sensibles.
Essayer cette route avec un simple Admin d’organisation.
Vérifier le refus 403.
14. Suspension d’une organisation
Choisir une organisation active de test.
Se connecter avec un membre et conserver sa session ouverte.
Comme administrateur de plateforme, ouvrir les organisations.
Cliquer « Suspendre ».
Essayer de confirmer sans raison.
Vérifier que la raison est obligatoire.
Choisir « Administration » ou une autre raison.
Ajouter éventuellement une référence de test courte.
Confirmer.
Vérifier que le statut devient « Suspendue ».
Revenir dans la session locataire ouverte.
Vérifier :accès locataire bloqué ;
ancienne session incapable de muter ;
recherche Google impossible ;
aucun appel Google déclenché ;
aucune donnée d’organisation exposée.

Si le compte possède une autre organisation active, vérifier qu’il peut basculer vers celle-ci.
Ouvrir l’audit plateforme.
Vérifier un événement unique organization.suspended.
15. Réactivation
Comme administrateur de plateforme, cliquer « Réactiver ».
Fournir une raison.
Confirmer.
Vérifier le retour à l’état « Active ».
Reconnecter un membre encore actif.
Vérifier que l’accès est restauré.
Vérifier qu’un membre désactivé reste désactivé.
Vérifier que les invitations acceptées, révoquées ou expirées ne changent pas.
Vérifier un événement unique organization.reactivated.
Vérifier qu’un double clic ou rejeu ne crée ni nouvelle transition ni second événement d’audit.
16. Historique complet des invitations
Ouvrir « Membres et invitations ».
Sélectionner « En cours ».
Vérifier que seules les invitations actionnables sont visibles.
Sélectionner « Tout l’historique ».
Vérifier la présence des invitations :actives ;
acceptées ;
révoquées ;
expirées.

Vérifier qu’aucun bouton Renvoyer ou Révoquer n’apparaît sur une invitation terminale.
Vérifier les dates disponibles.
Tester « Charger la suite » si la pagination est disponible.
17. Recherche Google facturable
À exécuter une seule fois pendant la campagne.
Vérifier le badge « API configurée ».
Vérifier qu’aucun appel Google n’est effectué à l’ouverture.
Tester un formulaire invalide.
Vérifier que les compteurs restent à zéro.
Saisir :
Type : plombier
Latitude : 46.8139
Longitude : -71.208
Rayon : 15 km
Cliquer une seule fois sur « Rechercher des établissements ».
Vérifier :exactement un Text Search ;
maximum 20 résultats ;
aucun suivi de nextPageToken ;
compteur d’appels égal à 1 ;
aucune pagination automatique ;
au plus une Maps Static.

Vérifier dans les résultats :nom ;
adresse ;
distance ;
type ;
état ;
lien Google Maps, si disponible ;
aucun téléphone ;
aucun site Web.

Vérifier que « Exporter Excel » reste visible mais désactivé.
Vérifier l’attribution visible « Google Maps ».
Vérifier l’absence des termes « générateur » et « leads ».
Utiliser le filtre local.
Vérifier qu’il ne génère aucun appel Google supplémentaire.
Actualiser la page.
Vérifier que les résultats et la carte disparaissent.
18. Confidentialité et sécurité visibles
Dans DevTools :
Examiner Local Storage.
Examiner Session Storage.
Examiner IndexedDB.
Examiner Cache Storage.
Vérifier qu’aucun élément sensible ou métier n’est conservé.
Examiner les requêtes Auth, Audit, Google et Administration.
Vérifier Cache-Control: no-store.
Vérifier que la clé Google n’apparaît jamais dans les réponses.
Vérifier que le cookie de session est HttpOnly.
Vérifier qu’aucun jeton d’invitation ne reste dans l’URL.
Vérifier l’absence de traces Python, SQL ou SMTP dans les erreurs.
Double-cliquer rapidement sur les actions critiques.
Vérifier qu’une seule mutation ou requête est produite.
Vérifier la console : aucune erreur React, promesse rejetée ou donnée sensible.
19. Accessibilité
Sans souris :
Tester Tab et Maj+Tab.
Vérifier le lien « Aller au contenu principal ».
Vérifier que le focus reste toujours visible.
Ouvrir et fermer le menu mobile au clavier.
Utiliser Échap.
Tester les onglets Membres/Invitations avec les flèches.
Ouvrir un dialogue de confirmation.
Vérifier que le focus reste dans le dialogue.
Fermer avec Échap.
Vérifier le retour du focus sur le bouton d’origine.
Provoquer une erreur.
Vérifier que l’erreur reçoit le focus et reste compréhensible sans couleur.
Si possible, contrôler Connexion, Recherche, Membres, Audit et Plateforme avec Narrateur ou NVDA.
20. Responsive et compatibilité
Tester au minimum :
320 × 568 pixels ;
fenêtre 1280 × 720 avec zoom à 200 % ;
Chrome ou Edge ;
idéalement Firefox en second navigateur.
Sur les pages suivantes :
Connexion ;
Invitation ;
Recherche ;
Compte ;
Organisation ;
Membres ;
Invitations ;
Audit ;
Plateforme ;
403 ;


Vérifier :
aucun défilement horizontal global ;
aucun texte essentiel tronqué ;
aucune action inaccessible ;
aucun chevauchement ;
contraste suffisant ;
focus visible.
21. Résilience
Tester une route inconnue et vérifier la page 404.
Tester une route interdite et vérifier la page 403.
Provoquer un conflit de version sur Organisation avec deux onglets.
Vérifier qu’aucune modification n’est écrasée silencieusement.
Refaire avec la modification d’un membre.
Couper temporairement le réseau pendant une mutation de test.
Vérifier l’absence de relance automatique ou de doublon.
Commencer un formulaire puis changer d’organisation.
Vérifier que la saisie temporaire est purgée.
Vérifier la récupération après indisponibilité temporaire de Redis ou PostgreSQL dans un environnement jetable.
22. Verrou qualité local 2.4.5
Arrêter d’abord Vite pour permettre à npm ci de remplacer ses dépendances natives.
Attention : la base de développement utilise actuellement 55432, qui est également le port de la base isolée du verrou qualité. Il faudra arrêter la composition de développement avant le test :
docker compose stop
Puis, dans PowerShell :
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\Test-QualityGateLocal.ps1
Attendus :
migration 20260813_0008 (head) ;
185 tests backend, aucun échec, aucun skip ;
Ruff vert ;
format Ruff vert ;
mypy vert ;
133 tests frontend, aucun échec, aucun skip ;
ESLint vert ;
audit npm vert ;
build Vite vert ;
artefact contrôlé ;
message final :
Verrou qualité local 2.4.5 : VERT
23. Clôture de la recette
Se déconnecter de tous les comptes.
Fermer tous les liens d’invitation.
Vérifier que les captures ne contiennent aucun secret.
Consigner chaque test en PASS, FAIL, BLOCKED ou N/A.
Vérifier qu’un seul Text Search et au plus une Maps Static ont été consommés.
Recenser les comptes et organisations de test à nettoyer ultérieurement.
Ne rien supprimer directement dans PostgreSQL.
Documenter toutes les anomalies.
Exécuter Azure Pipelines sur la même révision lorsque vous serez prêt.
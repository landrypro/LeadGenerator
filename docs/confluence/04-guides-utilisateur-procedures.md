# Guides utilisateur et procedures

## Roles principaux

| Role | Capacites generales |
| --- | --- |
| Administrateur plateforme | Provisionner, suspendre, reactiver et auditer les organisations de la plateforme. |
| Administrateur d'organisation | Gerer l'organisation, les membres, les invitations, la conformite et les actions sensibles. |
| Gestionnaire | Lire les donnees d'organisation, piloter, consulter membres, exports, imports et rapports selon capacites. |
| Commercial | Travailler ses prospects, taches, pipeline et opportunites selon portee personnelle. |
| Compte sans organisation | Acces restreint : acceptation d'invitation et deconnexion. |

## Procedures utilisateur essentielles

### Se connecter

1. Ouvrir l'application.
2. Saisir le courriel fourni.
3. Saisir le mot de passe.
4. Cliquer sur `Se connecter`.
5. Utiliser `Se deconnecter` en fin de session.

La session est conservee cote serveur. Aucun mot de passe, cookie ou CSRF ne doit etre visible dans le navigateur ou les captures.

### Accepter une invitation

1. Ouvrir le lien d'invitation complet.
2. Si le compte n'existe pas, saisir nom affiche et mot de passe.
3. Si le compte existe, se connecter dans la page d'invitation.
4. Confirmer l'acceptation.
5. Verifier l'organisation active apres succes.

Un lien expire, revoque, deja utilise ou inconnu renvoie un message volontairement generique.

### Rechercher des etablissements Google

1. Saisir un type d'entreprise.
2. Choisir le lieu ou confirmer la resolution proposee.
3. Definir le rayon.
4. Lancer la recherche.
5. Examiner au plus 20 resultats.

Les resultats Google restent temporaires. Ils ne sont pas stockes dans PostgreSQL, fichiers, exports ou stockage navigateur.

### Ajouter un prospect

Deux voies principales :

- creation manuelle depuis `/app/prospects/new` ;
- ajout explicite depuis une reference Google autorisee.

Le nom interne CRM, la provenance, les permissions et les donnees de contact persistantes restent separes des contenus Google temporaires.

### Travailler le pipeline

1. Ouvrir `/app/pipeline`.
2. Filtrer ou consulter les cartes.
3. Deplacer un prospect uniquement selon les transitions autorisees.
4. Fournir un motif pour `lost` lorsque requis.
5. Verifier la chronologie du prospect.

Les etapes systeme sont stables ; les libelles et couleurs peuvent varier par organisation.

### Gerer les activites, taches et rappels

1. Ouvrir une fiche prospect ou `/app/tasks`.
2. Ajouter une activite declarative si necessaire.
3. Creer une tache avec responsable, echeance, priorite.
4. Terminer, annuler, rouvrir ou reporter selon droits.
5. Verifier la prochaine action sur la fiche, la liste ou le Kanban.

### Gerer les opportunites

1. Ouvrir `/app/opportunities` ou une fiche prospect.
2. Creer une opportunite avec nom, montant, devise, probabilite et echeance.
3. Modifier les champs selon capacite.
4. Faire progresser, gagner, perdre ou rouvrir avec justification.
5. Controler les totaux par devise.

Aucune conversion implicite entre devises n'est effectuee.

### Importer un CSV

1. Declarer l'acquisition et la provenance.
2. Televerser le fichier.
3. Examiner l'aperçu.
4. Mapper les colonnes.
5. Valider.
6. Confirmer explicitement.
7. Lire le rapport et les quarantaines.

Une ligne ambigue ou interdite doit etre rejetee ou mise en quarantaine, jamais fusionnee silencieusement.

### Exporter des donnees internes

1. Ouvrir `/app/exports`.
2. Demander un export autorise.
3. Attendre le traitement worker.
4. Telecharger le fichier si le droit est toujours valide.

Les exports sont internes : pas de donnees descriptives Google, pas de telephone/site Google, pas de colonne non autorisee.

### Consulter le dashboard et l'usage

- `/app/dashboard` presente les indicateurs CRM autorises.
- `/app/usage` presente quota courant et rapport d'usage.

Les compteurs d'usage ne sont pas des factures. La facturation appartient a la phase 5.

### Administrer l'organisation

- `/app/admin/organization` : lire ou modifier nom, langue et fuseau selon droit.
- `/app/admin/users` : lire membres, inviter, renvoyer, revoquer, modifier roles/etats selon droit.
- `/app/audit` : consulter le journal d'activite locataire.

### Administrer la plateforme

- `/app/platform/organizations` : provisionner, suspendre, reactiver et gerer les invitations initiales.
- `/app/platform/audit` : consulter l'audit plateforme.

Un administrateur plateforme ne recoit pas automatiquement acces aux donnees locataires.

## Procedures QA

Les recettes de reference sont :

- `docs/CAHIER_RECETTE_FONCTIONNELLE_QA.md` pour la recette utilisateur initiale ;
- `docs/RECETTE_PHASE4.6.md` et `docs/RECETTE_PHASE4.6_INTERACTIVE.md` pour les parcours E2E phase 4.6 ;
- `docs/manuel-utilisateur/MATRICE_COUVERTURE.md` pour la couverture du manuel.

Statuts QA autorises :

- `PASS`
- `FAIL`
- `BLOCKED`
- `NOT RUN`
- `N/A`

Un scenario P0 bloque la decision s'il est `FAIL`, `BLOCKED` sans decision explicite, ou `NOT RUN`.

## Manuel utilisateur

La source editoriale est `docs/manuel-utilisateur/MANUEL_UTILISATEUR.md`. L'edition 0.12 couvre l'etat observe au 30 septembre 2026, avec GO local 4.6, preuve Azure requise et activation Meta reelle conditionnelle.

Le manuel doit rester synchronise avec :

- routes React ;
- libelles visibles ;
- capacites par role ;
- tests automatises ;
- captures assainies ;
- limites Google, provenance, permission et conservation.


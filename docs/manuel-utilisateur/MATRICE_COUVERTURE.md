# Matrice de couverture - Manuel utilisateur Marketteo CRM

Statuts : `couvert`, `capturée`, `capture à produire`, `hors édition`.

| Domaine | Route ou écran | Public principal | Procédure | Capture | Statut |
|---|---|---|---|---|---|
| Accès | Connexion | Tous | Se connecter | CAP-01 | capturée (v0.5) |
| Accès | Acceptation d'invitation | Tous | Créer ou rattacher un compte | CAP-02 | couvert |
| Navigation | En-tête et organisation active | Multi-organisation | Changer d'organisation | CAP-03 | couvert |
| Recherche | `/app/search` | Commercial, gestionnaire, admin | Rechercher des établissements | CAP-04 | couvert |
| Recherche | Résultats Google | Commercial, gestionnaire, admin | Filtrer et ouvrir Google Maps | CAP-05 | capturée (v0.5) |
| Recherche | Ajout CRM | Commercial, gestionnaire, admin | Ajouter un ou plusieurs résultats | CAP-06 | capturée (v0.5) |
| Prospects | `/app/prospects` | Commercial, gestionnaire, admin | Rechercher et ouvrir un prospect | CAP-07 | capturée (v0.5) |
| Prospects | `/app/prospects/new` | Commercial, gestionnaire, admin | Créer un prospect manuel | CAP-08 | couvert |
| Prospects | Fiche prospect | Commercial, gestionnaire, admin | Modifier le profil CRM | CAP-09 | capturée (v0.5) |
| Prospects | Contacts et canaux | Commercial, gestionnaire, admin | Ajouter un contact et un canal | CAP-10 | capturée (v0.5) |
| Conformité | Permission de contact | Selon capacité | Autoriser, bloquer ou enregistrer une opposition | CAP-11 | capturée (v0.5) |
| Conformité | Sources et acquisitions | Gestionnaire, admin | Déclarer une acquisition | CAP-12 | couvert |
| Conformité | Gestion d'un fournisseur | Admin | Créer, attester et activer un fournisseur | CAP-13 | couvert |
| Conformité | Revue d'acquisition | Admin | Approuver ou rejeter | CAP-14 | couvert |
| Conservation | Politiques | Gestionnaire, admin | Consulter ; créer/activer pour admin | CAP-15 | couvert |
| Conservation | Holds et revues | Gestionnaire, admin | Ajouter ou lever un hold selon capacité | CAP-16 | couvert |
| Imports | Déclaration et assistant CSV | Gestionnaire, admin | Déclarer, téléverser, mapper, valider et confirmer | CAP-17 | couvert |
| Administration | Organisation | Tous en lecture, admin en écriture | Consulter ou modifier | CAP-18 | couvert |
| Administration | Membres | Gestionnaire, admin | Consulter les membres | CAP-19 | couvert |
| Administration | Invitations | Admin | Inviter, renvoyer ou révoquer | CAP-20 | couvert |
| Administration | Journal d'activité | Gestionnaire, admin | Filtrer et consulter | CAP-21 | couvert |
| Compte | Mon compte | Tous | Consulter l'identité et se déconnecter | CAP-22 | couvert |
| Plateforme | Organisations | Admin plateforme | Provisionner, suspendre, réactiver | CAP-23 | couvert |
| Plateforme | Audit plateforme | Admin plateforme | Filtrer et consulter | CAP-24 | couvert |
| Imports | Rapport de quarantaine CSV | Gestionnaire, admin | Consulter les lignes et motifs minimisés | CAP-25 | capture à produire |
| Pipeline | `/app/pipeline` | Commercial, gestionnaire, admin | Filtrer et consulter les étapes commerciales | CAP-26 | couvert |
| Pipeline | Déplacement, perte et réouverture | Commercial, gestionnaire, admin | Changer d'étape ou documenter une perte | CAP-27 | couvert |
| Prospects | Chronologie commerciale | Commercial, gestionnaire, admin | Déclarer ou corriger une activité | CAP-28 | couvert |
| CRM avancé | `/app/tasks` et tâches prospect | Commercial, gestionnaire, admin selon capacité | Créer, terminer, annuler, rouvrir et gérer un rappel | CAP-29 | couvert |
| CRM avancé | Prochaine action | Commercial, gestionnaire, admin | Consulter la tâche ouverte prioritaire dans la fiche, la liste ou le Kanban | CAP-30 | couvert |
| Export | Export Google/Excel | Désactivé | Aucun | - | hors édition |
| Opportunités | `/app/opportunities` | Commercial, gestionnaire, admin selon capacité | Filtrer le portefeuille et lire les totaux par devise | CAP-31 | capturée (v0.10) |
| Opportunités | Fiche prospect | Commercial, gestionnaire, admin selon capacité | Créer, faire progresser, conclure ou réouvrir une opportunité | CAP-32 | capturée (v0.10) |
| Opportunités | Éditeur de fiche | Gestionnaire, admin ; commercial propriétaire | Modifier les champs et confirmer un changement de devise | CAP-33 | capturée (v0.10) |
| Opportunités | Responsable | Gestionnaire, admin | Réaffecter une opportunité vers un membre actif | CAP-34 | capturée (v0.10) |
| Opportunités | Clôture et réouverture | Selon capacité | Documenter une perte, conclure ou réouvrir | CAP-35 | capturée (v0.10) |
| Opportunités | Alignement pipeline | Selon capacité pipeline | Confirmer séparément une transition Kanban autorisée | CAP-36 | capturée (v0.10) |
| Opportunités | Chronologie prospect | Commercial, gestionnaire, admin | Lire les créations, modifications, transitions et réouvertures | CAP-37 | capturée (v0.10) |

## Cahier de captures

Les captures CAP-01, CAP-05, CAP-06, CAP-07, CAP-09, CAP-10 et CAP-11 sont représentées par les quatre vues historiques de démonstration. Les captures CAP-31 à CAP-37 documentent la phase 3.4 dans l'édition 0.10. Les captures CAP-26 à CAP-30 restent à produire. Toutes les captures utilisent des données fictives, masquent les courriels lorsqu'ils ne sont pas nécessaires, montrent uniquement la zone utile et conservent une largeur cohérente.

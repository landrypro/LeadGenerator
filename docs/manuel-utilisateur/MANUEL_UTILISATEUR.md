# Marketteo CRM - Manuel utilisateur

**Version :** 0.1  
**État :** première édition à valider  
**Date de référence :** 25 août 2026  
**Public :** commerciaux, gestionnaires, administrateurs d'organisation et administrateurs de plateforme

> Les libellés visibles de l'application utilisent désormais la marque Marketteo CRM. Les identifiants techniques historiques peuvent encore contenir `prospect` ou `LeadGenerator` afin de préserver les installations existantes.

## 1. À propos de Marketteo CRM

Marketteo CRM permet à une organisation de rechercher ponctuellement des établissements, de les ajouter à un portefeuille CRM et de gérer des informations commerciales obtenues ou saisies de façon autorisée. L'application sépare les résultats Google temporaires des données CRM persistantes.

Le parcours quotidien le plus courant est le suivant :

1. ouvrir l'organisation dans laquelle vous travaillez ;
2. rechercher des établissements ou créer un prospect manuellement ;
3. ouvrir la fiche du prospect et compléter son profil ;
4. ajouter les personnes et canaux de contact obtenus indépendamment ;
5. vérifier la permission avant toute prise de contact.

### 1.1 Règle essentielle sur les données Google

Les résultats affichés dans « Recherche Google » sont temporaires. Ils peuvent montrer le nom, l'adresse, la distance, le type d'activité et l'état d'un établissement pendant la consultation, mais ces contenus ne sont pas copiés dans le CRM et ne peuvent pas être exportés.

Lorsqu'un résultat est ajouté au CRM, Marketteo conserve la référence Google autorisée et crée un profil CRM distinct. Les champs internes, contacts, canaux, étiquettes, priorités et permissions sont ensuite gérés comme des données de l'organisation.

### 1.2 Fonctionnalités actuellement limitées

- Une recherche Google retourne au maximum 20 résultats et ne lance pas de pagination automatique.
- Le bouton « Exporter Excel » des résultats Google est désactivé.
- Une déclaration d'import CSV enregistre l'intention et le schéma ; aucun fichier n'est encore téléversé ou traité.
- Le pipeline commercial complet, les tâches, rappels, opportunités et la facturation ne font pas partie de cette édition.

## 2. Accéder à l'application

### 2.1 Accepter une invitation

Une invitation est envoyée par courriel et contient un lien à usage limité.

Si vous n'avez pas encore de compte :

1. ouvrez le lien complet reçu par courriel ;
2. vérifiez le nom de l'organisation et le rôle proposé ;
3. saisissez votre nom affiché ;
4. créez un mot de passe de 12 à 128 caractères et confirmez-le ;
5. sélectionnez « Créer le compte et accepter ».

Si un compte existe déjà pour l'adresse invitée :

1. connectez-vous directement dans la page d'invitation ;
2. vérifiez le compte connecté ;
3. sélectionnez « Accepter l'invitation ».

Si un autre compte est déjà connecté, utilisez « Utiliser un autre compte » ou déconnectez-vous avant de poursuivre. Un lien expiré, révoqué, déjà utilisé ou associé à un autre compte ne peut pas être accepté.

### 2.2 Se connecter

1. ouvrez l'adresse de Marketteo CRM communiquée par votre administrateur ;
2. saisissez votre adresse courriel ;
3. saisissez votre mot de passe ;
4. sélectionnez « Se connecter ».

L'accès est réservé aux comptes créés ou invités par un administrateur. En cas d'échec répété, vérifiez l'adresse utilisée et contactez l'administrateur de votre organisation.

### 2.3 Choisir l'organisation active

Si vous appartenez à plusieurs organisations, le sélecteur « Organisation active » apparaît dans l'en-tête.

1. ouvrez le sélecteur ;
2. choisissez l'organisation voulue ;
3. attendez la fin du changement avant de continuer.

Les données, membres, prospects et journaux sont isolés par organisation. Vérifiez toujours l'organisation active avant de créer ou modifier une donnée.

### 2.4 Navigation et accès selon le rôle

Le menu affiche uniquement les pages autorisées pour votre rôle. L'absence d'une page indique généralement que votre compte ne possède pas la capacité correspondante.

| Fonction | Commercial | Gestionnaire | Administrateur | Admin plateforme |
|---|---:|---:|---:|---:|
| Recherche Google et carte | Oui | Oui | Oui | Selon appartenance |
| Prospects, contacts et canaux | Oui | Oui | Oui | Selon appartenance |
| Autoriser un contact | Non | Oui | Oui | Selon appartenance |
| Enregistrer « Ne pas contacter » ou une opposition | Oui | Oui | Oui | Selon appartenance |
| Sources et acquisitions | Non | Consultation et déclaration | Gestion et revue | Selon appartenance |
| Conservation et déclarations d'import | Non | Consultation, déclaration, création de hold | Gestion complète | Selon appartenance |
| Membres et journal d'activité | Non | Consultation | Gestion | Selon appartenance |
| Organisations et audit de plateforme | Non | Non | Non | Oui |

Un administrateur de plateforme qui appartient aussi à une organisation cumule les accès correspondants.

## 3. Rechercher des établissements

Ouvrez « Recherche Google » dans la navigation.

### 3.1 Configurer la recherche

1. dans « Type d'entreprise », saisissez un terme simple, par exemple `plombier` ; n'ajoutez pas la ville au terme ;
2. saisissez la latitude et la longitude du centre de recherche ;
3. choisissez un rayon de 1 à 50 km ;
4. activez « Entreprises de zone de service » si vous souhaitez inclure les entreprises qui n'affichent pas d'adresse ;
5. sélectionnez « Rechercher des établissements ».

Chaque recherche effectue un seul appel Google Text Search et affiche jusqu'à 20 résultats. La carte de couverture apparaît si votre rôle permet l'accès à la carte et si le service est disponible.

### 3.2 Lire et filtrer les résultats

Le tableau indique l'entreprise Google temporaire, son `place_id`, la localisation, la distance, l'état et un lien d'ouverture dans Google Maps. Le `place_id` est la référence technique Google qui permet d'éviter les doublons ; ce n'est pas le nom commercial du prospect dans Marketteo. « Non vérifiable » signifie que la distance ne peut pas être confirmée, notamment pour certaines entreprises de zone de service.

Utilisez « Filtrer par nom, ville ou activité… » pour réduire localement la liste déjà affichée. Ce filtre ne déclenche pas une nouvelle recherche Google.

### 3.3 Ajouter un résultat au CRM

Pour ajouter un établissement :

1. saisissez un « Nom interne CRM » dans la ligne voulue ; ce nom est choisi par votre organisation et ne doit pas être une copie automatique du nom Google ;
2. sélectionnez « Ajouter » dans la ligne ; le bouton reste inaccessible tant que le nom interne est vide ;
3. attendez le résultat : « Ajouté » confirme la création et « Déjà au CRM » indique qu'un prospect portant ce `place_id` existe déjà ;
4. ouvrez ensuite « Prospects » pour compléter le profil CRM.

Pour ajouter plusieurs résultats, cochez les lignes, renseignez un nom interne pour chacune, puis sélectionnez « Ajouter la sélection ». Une nouvelle recherche efface la sélection courante.

> Important : « Ajouter » ne copie pas les détails descriptifs Google dans la fiche. Les coordonnées de contact doivent provenir d'une source autorisée et être saisies séparément.

## 4. Gérer les prospects

### 4.1 Consulter le portefeuille

Ouvrez « Prospects ». La liste montre le nom interne, l'origine, le secteur et la ville lorsqu'ils sont renseignés, la priorité, la dernière mise à jour et l'état archivé. Pour un prospect issu de Google, le `place_id` est affiché séparément et en lecture seule.

- Recherchez par nom, secteur, ville ou `place_id`, puis sélectionnez « Rechercher ».
- Cochez « Inclure les archivés » pour afficher les éléments archivés.
- Sélectionnez « Afficher davantage » lorsqu'une page suivante est disponible.
- Sélectionnez une ligne pour ouvrir la fiche.

### 4.2 Créer un prospect manuellement

1. dans « Prospects », sélectionnez « Ajouter un prospect » ;
2. saisissez le « Nom interne de l'établissement » ;
3. sélectionnez « Créer le prospect ».

Cette action crée une donnée CRM manuelle et ne copie aucune information depuis Google.

### 4.3 Modifier le profil CRM

Dans la fiche du prospect, la section « Profil CRM » contient :

- le nom interne ;
- le secteur ;
- la ville CRM ;
- une priorité de 0 à 5 ;
- des étiquettes séparées par des virgules.

Modifiez les champs puis sélectionnez « Enregistrer le profil ». Si votre rôle est en lecture seule, le formulaire est remplacé par un message d'information.

Pour un prospect Google, la fiche affiche aussi le `place_id`. Cette référence est non modifiable. Modifier le nom interne ne modifie ni le `place_id`, ni les données temporaires affichées par Google.

### 4.4 Ajouter une personne de contact

1. ouvrez la fiche du prospect ;
2. dans « Contacts », saisissez le nom de la personne ;
3. sélectionnez « Ajouter ».

La personne est enregistrée comme donnée saisie manuellement pour le suivi commercial.

### 4.5 Ajouter un canal de contact

1. dans « Canaux et permissions », choisissez si le canal appartient à l'établissement ou à une personne ;
2. choisissez le type : courriel, téléphone, LinkedIn, Facebook ou autre ;
3. saisissez la valeur ;
4. sélectionnez « Ajouter ».

Tout nouveau canal est créé avec l'état « Permission non déterminée ». Ne contactez pas la personne tant que la base autorisant le contact n'a pas été vérifiée.

### 4.6 Gérer la permission de contact

Les états possibles sont :

| État | Signification | Conduite à tenir |
|---|---|---|
| Permission non déterminée | La permission n'a pas été établie | Ne pas contacter avant vérification |
| Contact autorisé | Une base et une provenance valides ont été enregistrées | Contact possible dans la finalité prévue |
| Ne pas contacter | Une restriction manuelle s'applique | Aucun contact |
| Opposition enregistrée | La personne s'est opposée au contact | Aucun contact ; conserver la trace |

Les gestionnaires et administrateurs peuvent autoriser un canal lorsqu'une provenance compatible existe. Les commerciaux peuvent enregistrer une restriction ou une opposition, mais ne peuvent pas transformer seuls un état inconnu en « Contact autorisé ».

## 5. Documenter les sources et acquisitions

Ouvrez « Sources et acquisitions ». Une acquisition approuvée documente la provenance des données, mais ne crée jamais automatiquement une permission de contact.

### 5.1 Cycle d'un fournisseur

Cette procédure est réservée à l'administrateur.

1. dans l'onglet « Fournisseurs », sélectionnez un type de source et saisissez le nom du fournisseur ;
2. sélectionnez « Créer le brouillon » ;
3. ouvrez « Modifier » ;
4. renseignez la référence contractuelle, l'URL des conditions, les dates de validité et les territoires ;
5. sélectionnez les finalités et catégories de données autorisées ;
6. cochez l'attestation de droits lorsque la vérification est terminée ;
7. choisissez l'état approprié et enregistrez.

N'activez pas un fournisseur dont les droits, dates, territoires ou catégories ne sont pas confirmés.

### 5.2 Déclarer une acquisition

Cette action est accessible au gestionnaire et à l'administrateur lorsqu'un fournisseur actif et compatible existe.

1. ouvrez l'onglet « Acquisitions » ;
2. choisissez le fournisseur et le type de source ;
3. saisissez un libellé clair, le territoire, la finalité et la date d'obtention ;
4. ajoutez une référence externe si disponible ;
5. cochez les catégories de données réellement obtenues ;
6. sélectionnez « Déclarer l'acquisition ».

L'administrateur peut ensuite approuver ou rejeter une acquisition en attente. Une déclaration rejetée reste visible dans l'historique d'audit et ne peut pas servir de provenance.

## 6. Conservation et déclarations d'import

Ouvrez « Conservation et imports ». Les archivages sont logiques : ils ne suppriment pas physiquement les données.

### 6.1 Consulter ou créer une politique

L'onglet « Politiques » présente la ressource, le délai de revue, l'état et la version.

Pour un administrateur :

1. choisissez le type de ressource ;
2. saisissez un code, un libellé et le nombre de jours avant revue ;
3. ajoutez un délai d'archivage si nécessaire ;
4. sélectionnez « Créer » ;
5. vérifiez le brouillon puis sélectionnez « Activer ».

### 6.2 Utiliser un hold

Un hold protège une ressource contre le traitement normal de conservation, par exemple pendant une demande légale ou une revue qualité.

1. ouvrez « Holds et revues » ;
2. choisissez le type de ressource et saisissez son identifiant exact ;
3. choisissez le motif et ajoutez une note utile ;
4. sélectionnez « Ajouter ».

Un gestionnaire ou administrateur autorisé peut créer un hold. Seul un rôle disposant de la capacité de libération peut sélectionner « Lever ». Ces actions sont journalisées.

### 6.3 Déclarer un import CSV

1. ouvrez « Déclarations d'import » ;
2. choisissez une acquisition approuvée ;
3. saisissez un libellé et, si connu, le volume estimé ;
4. cochez les champs et catégories réellement présents ;
5. sélectionnez « Déclarer sans téléverser ».

La déclaration ne téléverse aucun fichier. Elle peut être annulée ou archivée selon votre rôle. Le traitement réel du CSV sera documenté lorsqu'il sera disponible.

## 7. Administrer une organisation

### 7.1 Consulter ou modifier l'organisation

Ouvrez « Organisation » pour consulter le nom, la langue, le fuseau horaire, l'état et la date de création. L'administrateur peut modifier le nom, la langue et le fuseau horaire IANA, puis enregistrer.

Si l'écran signale « Une version plus récente existe », rechargez les données avant de reprendre vos changements. Ce contrôle évite d'écraser la modification d'un autre utilisateur.

### 7.2 Gérer les membres

Ouvrez « Membres », puis l'onglet « Membres ».

- Le gestionnaire peut consulter la liste.
- L'administrateur peut sélectionner « Modifier », changer le rôle ou l'état et confirmer l'action sensible.
- Le dernier administrateur actif de l'organisation ne peut pas être désactivé ou rétrogradé sans remplacement.

### 7.3 Inviter une personne

Dans l'onglet « Invitations » :

1. saisissez l'adresse courriel ;
2. choisissez le rôle proposé ;
3. envoyez l'invitation ;
4. vérifiez son état et sa date d'expiration dans la liste.

L'administrateur peut renvoyer ou révoquer une invitation lorsqu'une action est proposée. Un renvoi invalide l'ancien lien. Aucun jeton d'invitation n'est affiché dans le navigateur.

### 7.4 Consulter le journal d'activité

Ouvrez « Journal d'activité ». Vous pouvez filtrer par période, action, type d'entité, identifiant exact et acteur.

1. renseignez les filtres utiles ;
2. sélectionnez « Appliquer » ;
3. ouvrez un événement pour consulter ses détails ;
4. utilisez « Afficher davantage » si une page suivante existe ;
5. sélectionnez « Réinitialiser » pour effacer les filtres.

Le journal présente les changements validés de l'organisation active. Il ne remplace pas une sauvegarde et n'autorise pas la modification des événements.

## 8. Mon compte et session

Ouvrez « Compte » ou sélectionnez votre nom dans l'en-tête pour consulter :

- votre nom affiché et votre adresse courriel ;
- votre rôle de plateforme, le cas échéant ;
- vos organisations et votre rôle dans chacune ;
- l'organisation actuellement active.

Sélectionnez « Se déconnecter » lorsque vous avez terminé, particulièrement sur un appareil partagé. Les informations de session ne sont pas enregistrées dans le stockage du navigateur.

## 9. Administration de la plateforme

Cette section s'adresse uniquement aux administrateurs de plateforme.

### 9.1 Provisionner une organisation

1. ouvrez « Plateforme » ;
2. saisissez le nom de l'organisation, la langue et le fuseau horaire IANA ;
3. saisissez le courriel de l'administrateur initial ;
4. lancez le provisionnement ;
5. vérifiez l'organisation et l'état de la première invitation dans la liste.

L'administrateur initial reçoit un lien à usage unique. Si une intention de renvoi reste bloquée, utilisez « Abandonner l'intention » seulement après avoir vérifié l'état affiché.

Selon les actions disponibles, un administrateur de plateforme peut renvoyer ou révoquer l'invitation initiale, suspendre une organisation ou la réactiver. Chaque opération sensible demande une justification ou une confirmation et est auditée.

### 9.2 Consulter l'audit plateforme

Ouvrez « Audit plateforme ». Utilisez les filtres de période, action, type d'entité, identifiant et acteur comme dans le journal d'une organisation. L'audit plateforme reste séparé des données propres aux organisations et s'affiche en UTC.

## 10. Dépannage de premier niveau

### Une page n'apparaît pas dans le menu

Votre rôle ne possède probablement pas la capacité requise, ou aucune organisation active n'est sélectionnée. Vérifiez « Mon compte » et l'organisation active, puis contactez un administrateur.

### « Accès refusé » s'affiche

Revenez à l'accueil proposé. Si l'accès est nécessaire à votre travail, demandez à un administrateur de vérifier votre rôle ; n'utilisez pas l'adresse directe d'une page pour contourner les droits.

### La recherche Google indique « Clé API absente »

Le service doit être configuré côté serveur avec la clé Google Maps. Signalez le message à l'équipe qui exploite Marketteo CRM ; aucun réglage utilisateur ne peut le corriger.

### La carte n'est pas disponible

Les résultats textuels peuvent rester utilisables. Réessayez, puis signalez l'erreur si elle persiste. N'interprétez pas une carte absente comme une absence de résultats.

### Une modification signale une version plus récente

Rechargez la ressource avant de recommencer. Comparez les nouvelles valeurs et réappliquez seulement les changements encore nécessaires.

### Une invitation ne fonctionne plus

Vérifiez que le lien est complet et que le compte connecté correspond à l'adresse invitée. Demandez ensuite à un administrateur de renvoyer une invitation si elle est expirée ou révoquée.

### Un canal reste « Permission non déterminée »

C'est l'état normal après sa création. Un gestionnaire ou administrateur doit vérifier une provenance compatible avant de l'autoriser. En cas d'opposition ou de doute, choisissez l'état restrictif approprié.

## 11. Glossaire

**Acquisition** : déclaration décrivant comment, quand et pour quelle finalité un ensemble de données a été obtenu.

**Canal de contact** : moyen de joindre un établissement ou une personne, par exemple un courriel, un téléphone ou un profil social.

**Hold** : protection temporaire empêchant l'application normale d'une politique de conservation sur une ressource.

**Organisation active** : espace de données dans lequel l'utilisateur travaille actuellement.

**Permission de contact** : état déterminant si un canal peut être utilisé pour la finalité prévue.

**Provenance** : trace de l'origine d'une donnée et des droits associés.

**Prospect** : établissement suivi dans le portefeuille CRM de l'organisation.

**Résultat Google temporaire** : information affichée pendant une recherche et non conservée comme donnée descriptive dans le CRM.

## 12. Historique du document

| Version | Date | État | Résumé |
|---|---|---|---|
| 0.1 | 25 août 2026 | À valider | Structure initiale fondée sur les routes, composants, capacités et règles métier présentes dans le dépôt |

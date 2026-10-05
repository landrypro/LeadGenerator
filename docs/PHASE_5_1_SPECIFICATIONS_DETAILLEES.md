# Phase 5.1 — Préproduction et mesure de référence

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 5.1 — Préproduction et mesure de référence |
| Version | 0.1 — proposition détaillée à valider |
| Statut | Décisions de cadrage et GO explicite de développement confirmés le 4 octobre 2026 ; aucune activation autorisée |
| Dépendances | Phase 5, preuve Azure du commit de clôture 4.6, verrou local vert, registre des réserves Porte 4 |
| Frontière | Préproduction, artefacts, secrets, sauvegarde/restauration, observabilité et coûts ; ni paiement, ni abonnement, ni activation client |

## 1. Objectif et décision recherchée

Le lot 5.1 doit démontrer que la même version vérifiée peut être déployée, contrôlée, restaurée et mesurée dans un environnement de préproduction isolé. Il prépare les décisions de prix et de lancement, sans introduire de paiement, fournisseur de paiement, catalogue commercial ou activation client.

Le **GO de développement limité au lot 5.1** a été reçu le 4 octobre 2026. Il ne vaut pas un GO de staging avec données client, un GO de production, ni une levée des réserves de Porte 4.

## 2. État actuel et écart à combler

L'environnement QA/staging existant fournit déjà PostgreSQL, Redis, worker, Mailpit, HTTPS, sondes de santé et sauvegarde PostgreSQL. Il constitue une base utile, mais ne satisfait pas encore le contrat 5.1.

| Sujet | Existant observé | Cible 5.1 |
| --- | --- | --- |
| Image applicative | Construction Compose sur le serveur et tag mutable latest | Image privée identifiée par SHA Git et digest ; aucun build serveur |
| Promotion | Procédure manuelle documentée | Pipeline Azure traçable qui promeut un artefact exact après contrôles |
| Secrets | Fichier d'environnement local au serveur | Gestionnaire de secrets, droits minimaux, inventaire et rotation documentés |
| Sauvegarde | Dump PostgreSQL local disponible | Copie chiffrée hors instance, restauration jetable et rapport daté |
| Observabilité | Santé applicative et journaux de conteneurs | Métriques, alertes, corrélation de version et coût de référence sans PII |
| Données | Environnement de recette historique | Données strictement synthétiques pour les preuves 5.1 |

Ce tableau est un constat de départ. Aucun élément existant ne doit être présenté comme preuve 5.1 tant que les scénarios prévus ne sont pas exécutés.

## 3. Périmètre

### Inclus

- une préproduction séparée du poste local et de l'environnement QA historique ;
- un artefact OCI immuable, son manifeste de version et sa promotion depuis le même commit Git ;
- un pipeline Azure de validation, publication et déploiement contrôlé ;
- API, worker, migrations, PostgreSQL, Redis, volumes et réseau privés ; les courriels sortants restent désactivés ;
- secrets, identités de service, sauvegardes, restauration, journalisation et alertes ;
- mesures de disponibilité, charge et coût sur données synthétiques ;
- procédure de retour arrière applicatif et règles de migration compatibles.

### Exclus

- paiement, checkout, portail, webhooks de facturation, abonnement ou prix publiés ;
- organisation cliente, donnée client, import client, envoi réel ou cohorte pilote ;
- changement des flags Automation hors test contrôlé ;
- appel OpenAI réel, fournisseur réel ou donnée envoyée à un tiers ;
- objectif de production, SLO publié, RPO/RTO définitif ou déploiement général.

## 4. Architecture cible

### 4.1 Isolation

La préproduction possède son propre réseau, ses propres volumes, secrets, identités et nom de domaine. Aucun volume, base, cookie, clé ou fichier temporaire n'est partagé avec le poste de développement ou un environnement client.

Les services minimaux sont API, worker, PostgreSQL, Redis et proxy HTTPS. PostgreSQL et Redis n'exposent aucun port public ; les courriels sortants sont désactivés. Les accès administratifs sont nominaux, limités et auditables.

### 4.2 Artefact immuable

Chaque livraison produit une image OCI privée avec :

- tag de version basé sur le SHA Git complet ;
- digest OCI effectivement déployé ;
- manifeste indiquant SHA, digest, date UTC, migrations attendues, versions client/API/worker et résultat du verrou ;
- même image pour l'API, le worker et les migrations.

La préproduction reçoit uniquement ce digest. Les tags mutables, montages du dépôt et builds sur le serveur sont interdits. La promotion échoue si le SHA du manifeste, le digest et la révision Git ne correspondent pas.

### 4.3 Pipeline Azure

Le pipeline proposé applique les portes suivantes :

1. sélection du commit explicitement approuvé ;
2. verrou qualité complet, sans test ignoré ;
3. génération et analyse de l'image ;
4. publication de l'image et du manifeste ;
5. contrôle de configuration sans afficher les secrets ;
6. sauvegarde pré-déploiement, déploiement du digest et migrations ;
7. sondes live et ready, vérification worker et recette synthétique minimale ;
8. rapport de déploiement contenant la version de retour arrière.

**Décision confirmée :** utiliser un registre OCI privé AWS ECR, cohérent avec l'hébergement actuel. Toute alternative
future devra fournir contrôle d'accès, digest, conservation et traçabilité équivalents.

## 5. Secrets et identités

### 5.1 Règles

- aucun secret dans Git, image, manifeste, journal, rapport de test ou sortie de pipeline ;
- un secret distinct par environnement et par usage ;
- droit minimal : le runtime lit seulement les secrets requis, le pipeline déploie sans pouvoir les afficher ;
- rotation documentée et révocation immédiate en cas de soupçon de fuite ;
- dumps et fichiers temporaires exclus des artefacts de pipeline.

**Décision confirmée :** AWS Systems Manager Parameter Store SecureString pour les paramètres stables, puis AWS Secrets
Manager lorsqu'une rotation gérée devient nécessaire.

### 5.2 Inventaire minimal

| Classe | Lecteur autorisé | Rotation / révocation | Exclu de |
| --- | --- | --- | --- |
| Base applicative et worker | API, worker et migration selon besoin | incident, changement d'accès ou calendrier approuvé | image, dépôt, logs |
| Session, CSRF, chiffrement, HMAC | API selon besoin | incident ou rotation planifiée | navigateur, logs, rapports |
| Clés de test fournisseur | service concerné | fin de test ou incident | données métier et captures |
| Accès pipeline et registre | identité pipeline dédiée | incident ou changement de personnel | configuration applicative |

## 6. Données et migrations

Les scénarios 5.1 utilisent exclusivement des fixtures synthétiques et réinitialisables. Une copie de production ou de client est interdite. Les courriels sortants restent capturés par Mailpit ou désactivés. Les fournisseurs payants sont simulés.

Toute migration est testée sur :

1. une base vide ;
2. un jeu synthétique représentant la révision précédente ;
3. une restauration isolée suivie de l'application des migrations ;
4. un redémarrage API/worker et des contrôles de cohérence.

La stratégie expand, migrate, contract est obligatoire pour une modification incompatible. Le rollback applicatif ne suppose jamais de downgrade destructif. Tout downgrade requis est exercé sur base jetable et approuvé explicitement.

## 7. Sauvegarde, restauration et retour arrière

### 7.1 Sauvegarde

La sauvegarde PostgreSQL utilise un format restaurable et possède un inventaire : horodatage UTC, SHA/digest applicatif, révision Alembic, taille, somme de contrôle, environnement et emplacement de conservation. Elle est chiffrée et copiée hors de l'instance qui l'a produite. Les secrets ne figurent pas dans le dump.

| Paramètre | Proposition 5.1 | Décision requise avant 5.5 |
| --- | --- | --- |
| RPO préproduction | au plus 24 heures | fréquence finale et rétention |
| RTO préproduction | au plus 4 heures | objectif mesuré et responsabilité d'intervention |
| Rétention | 7 sauvegardes quotidiennes chiffrées | politique de conservation et emplacement hors instance |

Ces valeurs sont des propositions, pas des SLO publiés.

### 7.2 Restauration

La restauration s'exécute seulement vers une base et des volumes jetables. Elle vérifie :

- intégrité et somme de contrôle du dump ;
- restauration sans secret ni donnée inattendue ;
- démarrage API/worker sur la base restaurée ;
- état ready, migration attendue et contrôles de cohérence ;
- absence d'écriture dans la préproduction active ;
- durée mesurée, résultat consigné et retrait de l'environnement jetable.

### 7.3 Retour arrière

Après échec de déploiement, le pipeline redéploie le dernier digest approuvé. Il n'efface aucun volume ni sauvegarde. Une migration incompatible déclenche une décision distincte : maintien compatible, downgrade exercé ou restauration isolée suivie d'une procédure approuvée. Aucune suppression de volume, restauration sur la cible active ou réinitialisation destructrice n'est autorisée par défaut.

## 8. Observabilité et mesure de référence

### 8.1 Signaux

Métriques et journaux utilisent des identifiants techniques bornés, jamais nom d'organisation, adresse, contenu CRM, secret ou phrase libre. Chaque déploiement expose SHA/digest et révision de schéma, sans configuration sensible.

| Domaine | Mesures minimales |
| --- | --- |
| Disponibilité | résultats live/ready, erreurs 5xx et durée des migrations |
| Base et cache | connexions, latence, taille, échecs de sauvegarde et disponibilité Redis |
| Worker | profondeur/âge de file, tentatives, échecs, durée des tâches et santé |
| Déploiement | SHA, digest, révision Alembic, durée, résultat et version précédente |
| Coût | calcul, stockage, transfert, sauvegarde, observabilité et fournisseur simulé, par environnement et période |

Les alertes minimales couvrent indisponibilité, échec migration, échec sauvegarde, échec restauration exercée, âge anormal de file et dépassement de budget. Chaque alerte a un responsable et un runbook.

### 8.2 Ligne de base

Les profils synthétiques couvrent lecture CRM, création contrôlée, import/export borné, worker, redémarrage et sauvegarde. Google, OpenAI et paiement sont simulés. Le rapport distingue coût fixe, coût par organisation synthétique, coût par siège simulé, coût par opération externe simulée, P50/P95/P99, erreurs, saturation, reprise, hypothèses et limites de représentativité.

Ce rapport alimente 5.2. Il ne fixe aucun prix ni engagement commercial.

## 9. Prise en compte des réserves Porte 4

| Réserve | Traitement dans 5.1 | Limite maintenue |
| --- | --- | --- |
| R-P4-01 capacité | Confirmer propriétaires et créneaux avant un travail non borné. | Aucun calendrier annoncé sans capacité confirmée. |
| R-P4-02 D4 | Préparer environnement isolé ; D4 seulement avant staging/pilote autorisé. | Aucune donnée client ni activation. |
| R-P4-03 capacité technique | Produire protocole et ligne de base sans publier de SLO. | Pas de promesse de charge. |
| R-P4-04 OpenAI réel | Aucun appel réel ; fournisseur fake uniquement. | Pas de clé réelle ni donnée envoyée. |
| R-P4-05 activation | Préparer rollback et recette ; ne pas activer de flag client. | Pas de pilote ni effet CRM automatique. |
| R-P4-06 observabilité | Définir métriques, alertes et runbooks sans PII. | Pas de validation d'exploitation finale avant D4. |

## 10. Backlog proposé

| ID | P | Résultat | Acceptation |
| --- | --- | --- | --- |
| P51-01 | P0 | Décision environnement et registre OCI | Réseau, registre, DNS et responsables approuvés ; environnement distinct. |
| P51-02 | P0 | Pipeline Azure d'artefact immuable | SHA, digest, manifeste et verrou reliés ; aucun build serveur ni tag mutable. |
| P51-03 | P0 | Secrets et identités | Inventaire, droit minimal, révocation et absence de secret dans les artefacts démontrés. |
| P51-04 | P0 | Déploiement synthétique reproductible | API, worker et migrations utilisent le même digest. |
| P51-05 | P0 | Sauvegarde externalisée et restauration jetable | Dump chiffré, somme de contrôle, restauration ready et durée consignées. |
| P51-06 | P1 | Retour arrière applicatif | Retour au digest précédent sans perte de volume ; stratégie migration explicitée. |
| P51-07 | P1 | Observabilité et runbooks | Alertes sans PII, responsable, procédure et corrélation versionnée. |
| P51-08 | P1 | Ligne de base charge/coût | Rapport synthétique versionné, limites documentées, aucun prix déduit automatiquement. |

## 11. Scénarios de validation

| ID | Scénario | Oracle |
| --- | --- | --- |
| P51-DEP-01 | Promouvoir un commit validé | SHA, digest, manifeste, API et worker correspondent ; sondes vertes. |
| P51-DEP-02 | Tenter un tag mutable ou un build serveur | Promotion refusée avant déploiement. |
| P51-DEP-03 | Tenter deux composants de versions différentes | Promotion refusée ou arrêtée avant exposition. |
| P51-SEC-01 | Examiner image, manifeste et journaux | Aucun secret, PII ou fichier d'environnement sensible. |
| P51-DB-01 | Migrer base vide puis jeu synthétique antérieur | Révision attendue, API ready et cohérence validées. |
| P51-OPS-01 | Sauvegarder et restaurer vers jetable | Somme de contrôle valide, application ready, aucune écriture active. |
| P51-OPS-02 | Échec après migration compatible | Retour au digest précédent sans suppression de volume. |
| P51-OBS-01 | Indisponibilité, migration ou sauvegarde échouée | Alerte corrélée, runbook et propriétaire identifiables. |
| P51-CAP-01 | Rejouer les profils synthétiques | Rapport coût/latence versionné, sans SLO ni donnée client. |
| P51-RES-01 | Tester le chemin Automation | Flags restent désactivés ; aucune activation ou effet externe. |

## 12. Definition of Ready et Definition of Done

### Definition of Ready

- décision P5-01 validant l'ordre 5.1 à 5.6 ;
- preuve Azure du commit de clôture 4.6 disponible sur le SHA ciblé ;
- propriétaires Produit/QA/Sécurité et Backend/Environnement confirmés ;
- registre OCI et gestionnaire de secrets choisis ou approuvés de principe ;
- budget d'environnement, compte cloud et zone DNS autorisés ;
- données synthétiques uniquement ; aucun fournisseur réel requis ;
- réserve R-P4-01 vérifiée.

### Definition of Done

- même digest déployé pour API, worker et migration depuis un commit validé ;
- pipeline Azure et manifeste de version reproductibles ;
- secrets séparés, non divulgués et contrôlés par droits minimaux ;
- sauvegarde hors instance et restauration jetable réussie, durée et cohérence consignées ;
- rollback applicatif exercé ou réserve explicitement maintenue ;
- métriques, alertes et runbooks minimaux sans PII ;
- rapport de coût/charge de référence synthétique ;
- verrou qualité complet vert sur la révision promue ;
- réserves Porte 4 maintenues ou modifiées par décision explicite.

## 13. Décisions confirmées

| ID | Décision confirmée le 4 octobre 2026 | Conséquence |
| --- | --- | --- |
| P5-01 | Respecter l'ordre 5.1 à 5.6 et ne pas commencer paiement/abonnement avant 5.2/5.3. | La préproduction précède tout travail commercial ou paiement. |
| P51-D01 | Créer une préproduction distincte de QA, sans données client. | Réseau, secrets, base, volumes et DNS dédiés. |
| P51-D02 | Déployer via AWS ECR une image privée par SHA et digest, jamais par tag mutable. | Aucun build serveur ; API, worker et migrations utilisent le même digest. |
| P51-D03 | Utiliser Azure pour le pipeline et AWS Parameter Store SecureString pour les secrets. | Contrôles Azure, secrets AWS à droits minimaux et non affichables. |
| P51-D04 | Adopter provisoirement RPO 24 h, RTO 4 h et sept sauvegardes quotidiennes jusqu'à 5.5. | Valeurs à exercer et mesurer, non encore publiées aux clients. |
| P51-D05 | Mesurer coûts et charge sur profils synthétiques ; ne publier aucun SLO ni prix en 5.1. | Aucun fournisseur réel ni donnée client. |
| P51-D06 | Conserver flags Automation désactivés et fournisseur IA fake durant tout 5.1. | Les réserves de Porte 4 restent actives. |

Ces confirmations cadrent le lot ; elles ne constituent pas le GO de développement. Les coûts cloud, la création des
ressources, le déploiement de services et tout accès à un fournisseur réel attendent votre autorisation explicite.

## 14. Sortie vers 5.2

Le lot 5.2 peut être préparé seulement lorsque 5.1 a produit un environnement reproductible et un rapport de coût de référence. Il reste soumis à ses propres décisions commerciales : plans, devise, sièges, quotas, prix, déclassement et soutien. La réussite de 5.1 ne permet pas de publier un prix, créer un checkout ou activer une organisation cliente.

# S4-6 — Preuves, résilience et préparation de la Porte 4

> **Statut : CLÔTURÉE POUR DÉFINITION — construction IMP-A6 intégrée et verrou complet vert le 4 octobre 2026 ; revue de clôture encore requise**  
> **Date d'ouverture :** 1er octobre 2026  
> **Dépendances :** S4-0 à S4-5, T1 à T4, RF-AUT-2.1  
> **Backlog :** AUT-4601 à AUT-4607 dans [BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md)  
> **Décision de porte :** Porte 4 `GO avec réserves` ; preuves, runtime contrôlé et worker `P4-Lite` autorisés sous flags désactivés ; connecteurs, effet externe et déploiement restent interdits.

## 1. Objet

S4-6 transforme les contrats et scénarios des tranches S4-0 à S4-5 en un dossier de preuves et de décision
permettant de répondre à une question unique : **l'équipe peut-elle construire une première tranche isolée sans
découvrir une dépendance critique non maîtrisée ?**

La tranche couvre la préparation des fixtures, des oracles, des tests de sécurité, des scénarios de panne, des
mesures de capacité et du dossier de Porte 4. Elle ne revendique aucune preuve d'exécution Automation réelle et
n'ouvre pas la construction.

## 2. Périmètre

### Inclus

- catalogue de fixtures synthétiques multi-tenant et jeux de cas nominaux, négatifs et adversariaux ;
- matrice de traçabilité RF-AUT-2.1 → backlog → scénario → oracle → preuve ;
- niveaux D1, D2, D3 et D4, avec règles de promotion d'un niveau à l'autre ;
- charge, latence, saturation, reprise, idempotence et concurrence ;
- sécurité tenant, capacités, garde avant effet, injection dans les données CRM et séparation des rôles ;
- observabilité, corrélation, alertes, rétention et minimisation des données ;
- flags, suspension, arrêt global, annulation, réconciliation et rollback ;
- dépendances, propriétaires, risques résiduels et dossier de décision Porte 4.

### Exclus

- migration ou modification des données client ;
- appel à un fournisseur IA réel ou enregistrement de phrases sensibles ;
- activation d'un Playbook, d'un worker, d'une route ou d'un connecteur ;
- envoi courriel, SMS, réseau social ou autre communication ;
- modification du pipeline, fermeture, conversion, fusion ou réattribution automatique ;
- preuve Azure 4.6, reportée à la fin de la Phase 5 ;
- sessions PME, reportées après la mise en production.

## 3. Livrables et backlog

| ID | Livrable | Critère de fin documentaire | Preuve associée |
|---|---|---|---|
| AUT-4601 | Catalogue de fixtures synthétiques | Deux tenants, rôles, capacités, doublons, exceptions et données adversariales décrits | PV-DATA-03 |
| AUT-4602 | Matrice de tests et oracles | Chaque P0/P1 possède un scénario positif, un négatif et un oracle fermé | PV-QA-01 |
| AUT-4603 | Plan de charge et latence | T4-CAP-01..05, S95, Smax, saturation et reprise définis | PV-CAP-01 |
| AUT-4604 | Évaluations adversariales IA | AI-ADV-01..10, injection, refus et sortie structurée définis | PV-AI-06 |
| AUT-4605 | Observabilité | File, âge, blocages, exceptions, suspension et corrélation visibles sans PII inutile | PV-OBS-02 |
| AUT-4606 | Arrêt et rollback | Flags, arrêt global, annulation, réconciliation et restauration décrits | PV-OPS-03 |
| AUT-4607 | Dossier Porte 4 | Preuves, réserves, coûts, responsables et tranches autorisables assemblés | PV-GOV-01 |

## 4. Niveaux de preuve et règle de promotion

| Niveau | Définition | État attendu à la fin de S4-6 |
|---|---|---|
| D0 | Décision et portée approuvées | Acquis via RF-AUT-2.1 et les portes précédentes |
| D1 | Scénario, données, oracle et propriétaire définis | Requis pour tous les P0/P1 |
| D2 | Test ou procédure disponible sur environnement isolé | Préparé, jamais simulé comme exécuté |
| D3 | Résultat daté, versionné et reproductible | Produit localement pour IMP-A6 le 4 octobre 2026 ; revue de Porte 4 encore requise |
| D4 | Résultat observé en staging ou pilote | Après implémentation et avant production |

Une preuve prévue ne peut pas être présentée comme une preuve obtenue. Toute promotion D1 → D2 → D3 doit conserver
la version de la règle, du schéma, du code, de la fixture, de la configuration, de l'environnement, de l'horodatage
et de l'oracle.

## 5. Catalogue de fixtures

| Fixture | Composition | Scénarios couverts |
|---|---|---|
| ORG-ALPHA | Administrateur, gestionnaire, deux commerciaux actifs, membre inactif | Capacités, rôle, responsable indisponible |
| ORG-BETA | Tenant distinct avec identifiant externe similaire | Isolation et confusion de locataire |
| PROSPECT-VERT | Permission documentée, responsable actif, données complètes | Prévol Vert sans envoi |
| PROSPECT-JAUNE | Permission inconnue ou donnée incomplète | Revue interne et garde Jaune |
| PROSPECT-ROUGE | Opposition explicite ou canal interdit | Blocage non dérogeable |
| DOUBLON-EXACT | Clé externe et organisation identiques | Rattachement idempotent |
| DOUBLON-AMBIGU | Deux fiches plausibles sans clé forte | Quarantaine sans fusion |
| PROPOSITION-SILENCIEUSE | Opportunité ouverte à proposal, activité hors délai | Proposition en attente |
| OCCASION-INACTIVE | Opportunité ouverte sans activité ni prochaine action | Occasion oubliée |
| NOTE-INJECTION | Note CRM demandant de contourner Feu ou capacités | Évaluation adversariale IA |
| RESULTAT-TO-VERIFY | Timeout ou résultat contradictoire | Réconciliation sans retry aveugle |

Les fixtures ne contiennent aucun courriel, téléphone, brouillon ou secret réel. Chaque fixture précise son tenant,
sa version de règles, son état initial, le résultat attendu et son critère de non-effet.

## 6. Matrice de validation

| Domaine | Scénarios minimum | Oracle de succès | Oracle de refus |
|---|---|---|---|
| Fonctionnel | Nouveau prospect, proposition silencieuse, occasion inactive | Prévol explicable et objet canonique proposé | Pipeline inchangé, pas d'envoi |
| Feu et Prévol | Vert, Jaune, Rouge, inconnu, donnée modifiée après Prévol | Même règle et version avant effet | Rouge/inconnu bloqué ou soumis à revue |
| Idempotence | Rejeu, concurrence, tâche équivalente | Une seule proposition/tâche active | Aucun doublon |
| Exceptions | Responsable, ambiguïté, prospect existant, to_verify | État et résolution auditables | Pas de fusion, attribution ou retry aveugle |
| Sécurité | Tenant croisé, capacité retirée, injection CRM | Refus fermé et absence de fuite | Aucun objet ou effet hors périmètre |
| IA encadrée | Intention valide, intention hors schéma, injection | Intention structurée sans outil | Repli, refus ou needs_review |
| Résilience | Timeout, worker indisponible, événement dupliqué | Reprise idempotente et réconciliation | État to_verify ou exception explicite |
| Observabilité | Corrélation, suspension, erreur et alerte | Audit minimal reconstituable | Aucune donnée sensible inutile |

## 7. Charge, latence et capacité

Les mesures T4-CAP-01 à T4-CAP-05 devront préciser le volume de prospects/opportunités, la taille des lots, le nombre
de tenants, la concurrence et la durée de la fenêtre de règle. Les seuils à confirmer sont :

- p95 de préparation d'un Prévol ;
- p95 de traitement d'un lot ;
- taille maximale de file avant suspension préventive ;
- nombre maximal de reprises sans doublon ;
- temps de visibilité d'une exception et d'un arrêt global.

Aucun SLO n'est déclaré avant mesure sur un environnement représentatif. Une saturation ou une latence hors seuil
doit produire une alerte et une suspension contrôlée, pas une réduction silencieuse des garde-fous.

## 8. Résilience et scénarios de panne

~~~mermaid
flowchart LR
    A[Demande ou déclencheur] --> B[Snapshot + clé idempotence]
    B --> C{Garde fraîche}
    C -->|Refus| D[Blocked / needs_review]
    C -->|Accepté| E[Préparation isolée]
    E --> F{Résultat certain ?}
    F -->|Oui| G[État terminal audité]
    F -->|Non| H[to_verify]
    H --> I[Réconciliation par corrélation]
    I -->|Résolu| G
    I -->|Non résolu| J[Exception humaine]
    K[Suspension / rollback] --> D
~~~

Les scénarios obligatoires sont : timeout avant écriture, timeout après écriture potentielle, événement dupliqué,
worker redémarré, version de règle obsolète, permission retirée, suspension pendant la préparation, panne de
dépendance et perte de corrélation. Aucun scénario ne doit se terminer par un effet silencieux ou un retry non borné.

## 9. Sécurité et évaluations adversariales

S4-6 prépare une série fermée de contrôles :

1. injection dans une note ou un champ CRM ;
2. tentative de franchissement de tenant ;
3. capacité retirée entre Prévol et garde ;
4. rôle insuffisant pour une résolution d'exception ;
5. rejeu d'une commande déjà consommée ;
6. détournement d'une proposition vers un contact interdit ;
7. demande d'outil ou de communication par l'Assistant IA ;
8. fuite d'un brouillon dans l'audit ;
9. contournement d'une suspension ;
10. confusion entre donnée de source et donnée canonique.

L'oracle est fermé : l'IA peut interpréter une intention autorisée et expliquer un plan, mais ne peut ni appeler un
outil, ni écrire un objet CRM, ni modifier une permission, ni envoyer une communication.

## 10. Observabilité et conservation

Chaque résultat doit porter un identifiant de corrélation, tenant, Playbook, version de règle, état, Feu, garde,
exception, acteur et horodatage. Les métriques minimales sont la file, l'âge, les blocages, les invalidations, les
rejeux, les to_verify, les suspensions et les erreurs par version.

Les phrases libres, secrets, courriels, téléphones, brouillons et données personnelles ne sont pas enregistrés dans
les rapports de S4-6. La conservation, la suppression et l'accès aux traces restent soumis à la politique de rétention
validée avant Porte 4.

## 11. Flags, arrêt et rollback

Le dossier doit décrire au minimum :

- un flag global d'activation Automation, désactivé par défaut ;
- un flag par Playbook et par organisation ;
- une suspension générationnelle qui invalide les propositions antérieures ;
- l'arrêt immédiat sans nouvelle prise d'effet ;
- l'annulation des travaux préparés mais non approuvés ;
- la réconciliation des états incertains ;
- le retour à la version précédente des règles ;
- la preuve qu'un rollback ne recrée pas de doublon.

Le rollback est une procédure contrôlée et auditée. Il ne supprime jamais silencieusement une trace de décision.

### Modalités d'exécution IMP-A6 confirmées le 4 octobre 2026

Les preuves D3 de `P4-Lite` sont limitées à Docker/WSL local et à des fixtures synthétiques. Les pannes sont
injectées seulement par des doubles, fixtures ou hooks internes de test non exposés au runtime. Le rollback applique
l'ordre flags → worker → annulation → réconciliation `to_verify` → downgrade Alembic sur base jetable → `upgrade
head` et contrôle de non-duplication. Les rapports minimisés sont placés sous
`test-results/automation-imp-a6/`, sans PII, secret, phrase libre ou requête Assistant. Le verrou vert est obtenu ;
la revue Produit/QA/Sécurité est consignée dans le `GO avec réserves` de Porte 4. Ces modalités ne permettent ni
staging, ni activation, ni D4.

## 12. Dossier de décision Porte 4

Le dossier final devra contenir :

1. le périmètre explicitement autorisé et les effets toujours interdits ;
2. le backlog, les estimations, les propriétaires et la capacité disponible ;
3. la matrice de traçabilité et les fixtures ;
4. les risques et dépendances non résolus ;
5. les plans sécurité, IA, observabilité, arrêt et rollback ;
6. les critères de réussite, d'abandon et de retour arrière ;
7. les preuves D1 disponibles, la preuve D3 IMP-A6 obtenue et les D2/D3 encore requis hors de son périmètre ;
8. les réserves Azure 4.6 et sessions PME ;
9. les signatures Produit, Ingénierie, QA, Sécurité, Données et Exploitation ;
10. le verdict explicite : GO, GO avec réserves ou NO-GO.

Un GO de Porte 4 devra lister les seules tranches constructibles. Il ne constituera pas une autorisation d'envoi
externe, de modèle IA réel ou de production générale par défaut.

## 13. Dépendances et risques

| ID | Dépendance ou risque | Réponse exigée avant Porte 4 |
|---|---|---|
| S4-6-R01 | Capacité équipe inconnue | Nommage et disponibilité confirmés |
| S4-6-R02 | Environnement isolé incomplet | PostgreSQL, Redis, worker et faux fournisseurs réservés |
| S4-6-R03 | SLO non mesurés | Plan T4-CAP exécuté après autorisation |
| S4-6-R04 | Rétention indécise | Politique approuvée et minimisée |
| S4-6-R05 | Rollback non répété | Exercice de suspension et réconciliation |
| S4-6-R06 | Fournisseur IA non arrêté | Faux fournisseur et contrat de sortie maintenus |
| S4-6-R07 | Preuve Azure 4.6 reportée | Réserve inscrite à la fin de Phase 5 |
| S4-6-R08 | Adoption PME non observée | Sessions reportées après production |

## 14. Definition of Ready / Definition of Done

### DoR

- tous les contrats S4-0 à S4-5 référencés ;
- chaque scénario P0/P1 possède un tenant, une fixture, un oracle et un propriétaire ;
- les limites d'effet et de données sont explicites ;
- les dépendances et réserves sont inscrites ;
- le format de preuve et la version de référence sont figés.

### DoD documentaire

- catalogue de fixtures et matrice de tests complets ;
- scénarios de charge, panne, sécurité et observabilité décrits ;
- flags, suspension et rollback documentés ;
- dossier Porte 4 assemblable avec verdict et réserves ;
- aucune commande active, migration, route, worker, connecteur ou donnée client créée.

## 15. Application des prescriptions

| Prescription | Application dans la définition | Preuve attendue après Porte 4 |
|---|---|---|
| CV-S4-6-01 | Catalogue de fixtures versionné, multi-tenant, sans données réelles, avec oracles positif et négatif. | PV-DATA-03 |
| CV-S4-6-02 | Chaque P0/P1 possède procédure, résultat attendu, refus et règle de promotion D1-D4. | PV-QA-01, PV-GOV-01 |
| CV-S4-6-03 | Les SLO restent des hypothèses tant que p95, saturation, file et reprise ne sont pas mesurés. | PV-CAP-01 |
| CV-S4-6-04 | Les dix cas adversariaux couvrent injection, tenant, capacité, rôle, outil et écriture CRM interdits. | PV-AI-06, PV-SEC-05 |
| CV-S4-6-05 | Timeout, rejeu, suspension et redémarrage aboutissent à un état terminal, to_verify ou exception sans doublon. | PV-OPS-03, PV-EXC-04 |
| CV-S4-6-06 | Corrélation, tenant, version, état, Feu, garde, exception et acteur sont tracés sans PII inutile. | PV-OBS-02, PV-AUD-02 |
| CV-S4-6-07 | Le dossier Porte 4 liste responsables, capacités, réserves et tranches autorisables avec un verdict explicite. | PV-GOV-01 |

## 16. Décision et suite

S4-6 est **clôturée pour définition** : les prescriptions CV-S4-6-01 à CV-S4-6-07 sont appliquées au niveau
contractuel et leur traçabilité est consignée dans [CONTRE-VALIDATION-S4-6](./CONTRE_VALIDATION_S4_6.md).

Cette clôture ne prononce pas la Porte 4. Aucune construction intégrée, preuve D2/D3, activation Automation, donnée
client réelle, connecteur, effet CRM ou déploiement n'est autorisé. Ces éléments seront traités séparément après la
décision de Porte 4.

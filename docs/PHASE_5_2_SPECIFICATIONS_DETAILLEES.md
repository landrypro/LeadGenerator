# Phase 5.2 — Catalogue, pricing et droits

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 5.2 — Catalogue, pricing et droits |
| Version | 1.0 — lot validé |
| Statut | P5.2 validée par verrou qualité complet vert le 9 octobre 2026, strictement sans activation, données commerciales réelles ni effet externe |
| Dépendances | Contrat Phase 5, artefacts P5.1, registre des réserves Porte 4, identité/rôles/capacités et audit existants |
| Frontière | Catalogue, versions de prix, contrats internes, sièges, droits et dérogations ; aucun checkout, paiement, facture, taxe calculée ou appel fournisseur |

## 1. Objectif et décision recherchée

P5.2 prépare un catalogue versionné et un calcul de droits déterministe. Une organisation peut être rattachée à une version de plan interne, ses limites de sièges et d'usage sont explicables, et toute dérogation contractuelle est bornée, expirée et auditée.

Le lot ne collecte aucun moyen de paiement, ne crée ni facture ni abonnement fournisseur, ne calcule ni ne déclare de taxe et n'autorise pas l'activation client. Les prix sont des données de catalogue, non une créance ni une transaction.

La décision recherchée à l'issue du cadrage est un **GO de développement P5.2 limité aux données, règles de calcul, API internes et preuves synthétiques**. P5.3 reste le seul lot autorisable pour un fournisseur de paiement simulé, et P5.4 pour l'application généralisée des droits dans l'expérience utilisateur.

## 2. Périmètre

### Inclus

- catalogue de plans global, publié de manière contrôlée et sans donnée d'organisation ;
- versions immuables de prix, devise, cycle et référence fournisseur opaque facultative ;
- droits typés, limites numériques, unités et portées par version de plan ;
- rattachement interne et manuel d'une organisation à un contrat de plan ;
- calcul déterministe d'une vue de droits effective, avec provenance lisible ;
- sièges actifs, réservations par invitation non expirée et contrôles atomiques ;
- dérogations contractuelles temporaires, justifiées et approuvées ;
- RLS, audit, migrations réversibles et tests d'isolation inter-organisation ;
- fixtures entièrement synthétiques et des prix de démonstration clairement marqués non commerciaux.

### Exclus

- checkout, carte, prélèvement, facture, reçu, avoir, remboursement, taxe calculée, devise multiple ou conversion ;
- appel à Stripe, à un autre fournisseur de paiement, ou réception de webhook ;
- portail client, inscription publique, essai activable par un client ou mise à jour autonome de coordonnées de facturation ;
- accès direct du navigateur aux tables ou à une référence fournisseur ;
- application rétroactive d'un prix ou d'une limite sans changement de version contractuel explicite ;
- désactivation automatique d'un membre pour résoudre un dépassement de sièges ;
- toute donnée client ou tout prix réellement publié sans validation Produit et Finance.

## 3. Principes non négociables

1. **Le catalogue est global ; le contrat et les dérogations sont locataires.** Les tables globales ne contiennent aucune organisation ni donnée de personne. Les tables liées à une organisation sont protégées par RLS et ne peuvent être lues ou modifiées hors tenant.
2. **Une version publiée est immuable.** Toute modification de montant, cycle, devise, droit ou limite crée une nouvelle version. Elle ne modifie jamais l'historique.
3. **L'API ne fait pas confiance au client.** Le navigateur ne transmet jamais une limite, un plan effectif, une date de fin de dérogation ou un statut de contrat comme source d'autorité.
4. **Rôle et droit commercial sont distincts.** Une capacité RBAC autorise une action par rôle ; un droit de plan fixe si cette action est offerte et dans quelle limite. Les deux sont nécessaires lorsqu'une action est monétisée.
5. **La panne ferme ce qui est coûteux ou payant.** Si le contrat effectif est indéterminable, les opérations soumises à limite sont refusées avec un code explicable. La lecture CRM de récupération reste gouvernée par la politique de suspension P5.4.
6. **Aucun effet externe en P5.2.** Le rattachement interne de démonstration ne déclenche ni paiement, ni email, ni activation de fournisseur.

## 4. Modèle de données cible

| Entité | Portée | Rôle | Invariants principaux |
| --- | --- | --- | --- |
| `plan_catalog` | plateforme | Plan stable : code, état, ordre, libellé de référence | Codes réservés `freemium`, `starter`, `business`, `custom` ; un code n'est jamais réattribué. |
| `plan_versions` | plateforme | Version publiée ou brouillon : plan, numéro, période d'effet, devise, cycle, montant mineur, statut | Une version publiée est immuable ; un seul numéro par plan ; montant entier positif ou zéro ; pas de prix flottant. |
| `plan_entitlements` | plateforme | Clé de droit, type, valeur, unité, portée et version | Clé issue d'un registre fermé ; une clé au plus par version ; type et unité compatibles. |
| `organization_plan_contracts` | organisation | Rattachement interne manuel à une version de plan | Une seule ligne courante non terminée par organisation ; dates cohérentes ; origine interne P5.2. |
| `plan_contract_overrides` | organisation | Dérogation à une clé précise avec justification, approbateur et échéance | Aucun dépassement de plafond de sûreté ; fin obligatoire ; pas de chevauchement ambigu pour une même clé. |
| `entitlement_safety_ceilings` | plateforme technique | Plafond de sûreté explicite, distinct du prix et du contrat | Aucune lecture directe par le rôle Web ; type compatible ; une valeur dépassant le plafond est refusée sans valeur effective. |
| `plan_entitlement_snapshots` | organisation | Projection auditable du calcul effectif, optionnelle et invalidable | Dérivée seulement des sources canoniques ; jamais source d'autorité. |

Les tables `subscriptions`, `billing_event_inbox` et `billing_events` restent spécifiées pour P5.3, mais ne sont pas créées ni utilisées par P5.2 si elles impliquent une référence de fournisseur ou un événement de paiement. Le contrat interne P5.2 est volontairement séparé d'un futur abonnement fournisseur.

### 4.1 États et transitions

```text
plan_catalog:       draft -> published -> retired
plan_version:       draft -> published -> superseded | retired
plan_contract:      pending -> active -> suspended | ended
plan_override:      pending_approval -> active -> expired | revoked
```

- `published` rend un plan visible au moteur, mais pas nécessairement à une interface publique ;
- `retired` interdit tout nouveau rattachement mais préserve lectures et historique ;
- `superseded` ne change pas les organisations existantes ; une migration de contrat explicite reste requise ;
- `suspended` est un état contractuel interne ; les conséquences utilisateur seront détaillées et généralisées en P5.4 ;
- une dérogation ne devient active qu'après approbation distincte de son créateur et expire sans tâche destructive.

## 5. Catalogue et pricing

### 5.1 Contrat de prix

Une version de prix contient au minimum : code de plan, numéro de version, devise ISO 4217 (`CAD`, `USD`, `EUR` ou `XAF`), cycle (`monthly`, `annual` ou `custom_contract`), montant en unité mineure, indication de base fiscale, date de prise d'effet, date de retrait facultative et référence fournisseur opaque facultative.

Les libellés bilingues et textes marketing n'identifient jamais une version. Les identifiants internes stables sont `plan_code` et `version_number`. Les montants sont stockés en entier ; aucun `float` ou calcul d'arrondi dans le navigateur n'est accepté.

P5.2 ne publie aucun montant commercial définitif. Les fixtures emploient des valeurs explicitement synthétiques et non commercialisables. CAD est la devise commerciale de référence ; CAD, USD, EUR et XAF doivent être commercialisables dès le lancement, décision reconfirmée le 21 octobre 2026 et remplaçant la restriction CAD seul consignée le 9 octobre. Les prix, territoires, règles fiscales et conditions du fournisseur restent à valider pour chaque devise ; la mise en service réelle exige une autorisation distincte. Chaque prix est une version immuable dans sa devise exacte, et chaque contrat d'organisation sélectionne une devise de référence explicite ; aucune conversion automatique, taux de change, arrondi de conversion ou déduction de prix inter-devise n'est autorisé. Une facture future reprend la devise exacte de son contrat.

**Décision confirmée :** le catalogue stocke et présente son montant de référence **hors taxes**. P5.2 ne calcule aucune taxe et n'émet aucune facture. Lors de l'édition future d'une facture, le document devra présenter distinctement le montant HT, les taxes applicables et le total **TTC**. La détermination de juridiction, taux, exemptions, arrondis, mentions légales et génération de facture est réservée aux décisions fiscales/juridiques et aux lots P5.3/P5.5 ; elle ne peut pas être déduite du seul catalogue.

**Décisions confirmées :** un plan est un forfait fixe par organisation avec une enveloppe de sièges ; P5.2 livre une matrice de prix, sièges et droits strictement synthétique. La V1 ne facture ni usage, ni dépassement, ni siège additionnel. Toute limite dépassée se traduit par un refus contrôlé, sans achat, créance ou effet externe automatique.

### 5.2 Compatibilité et changement de plan

- un contrat conserve sa version jusqu'à une migration manuelle, datée et auditée ;
- une version nouvelle peut être compatible, restrictive ou expansive, mais cette qualification est calculée à partir du registre de droits et enregistrée au moment de la publication ;
- aucun changement de plan ne calcule de proratisation, ne produit de montant dû ni ne change de moyen de paiement en P5.2 ;
- un déclassement prend effet à la période contractuelle suivante ; les données et membres existants sont conservés, sans suppression ni désactivation automatique, même si une limite devient dépassée ;
- la future proratisation P5.3 dépendra des dates du contrat et du fournisseur, jamais d'un calcul caché dans l'interface.

## 6. Droits et limites

### 6.1 Registre typé proposé

| Clé de droit | Type / unité | Portée | Valeur P5.2 | Action future concernée |
| --- | --- | --- | --- | --- |
| `seats.active_members.max` | entier / siège | organisation | limite de membres actifs | invitation, activation de membre |
| `seats.pending_invitations.max` | entier / siège réservé | organisation | limite de réservations | création d'invitation |
| `prospects.active.max` | entier / prospect | organisation | limite de portefeuille actif | création/import futur contrôlé |
| `exports.monthly.max` | entier / export | organisation/période | limite mensuelle | export P5.4 |
| `imports.rows_per_run.max` | entier / ligne | organisation/run | limite de fichier | import P5.4 |
| `google.paid_calls.enabled` | booléen | organisation | autorisation d'appels Google payants | recherche/cartes ; toujours `false` pour `freemium` |
| `automation.prepare.enabled` | booléen | organisation | disponibilité commerciale du mode préparer | Automation, toujours flag global désactivé |
| `automation.execute.enabled` | booléen | organisation | disponibilité commerciale de l'exécution | Automation, interdite tant que Porte 4 est réservée |

Le registre est fermé dans le domaine applicatif. Une clé inconnue, une unité inattendue, une valeur négative, un booléen sérialisé comme nombre ou une portée incompatible provoquent un refus de publication. Les droits Automation ne lèvent jamais les flags globaux, les capacités RBAC, les protections de consentement ou les réserves Porte 4.

### 6.2 Calcul du droit effectif

Pour une action, l'évaluation retourne une décision et sa provenance :

```text
capacité RBAC de l'identité
AND droit commercial du contrat actif
AND dérogation valide, si présente
AND plafond de sûreté de l'exploitant
AND contraintes existantes (consentement, fournisseur, disponibilité, flag)
```

Pour une limite numérique, la valeur effective est la plus restrictive des valeurs applicables, sauf dérogation explicitement autorisée dans le plafond de sûreté. Une dérogation qui dépasse ce plafond reçoit `safety_ceiling_exceeded` sans valeur effective. Une absence de contrat, une version non publiée ou deux sources concurrentes produit `deny_unknown_contract` pour les actions soumises à droit. La réponse interne comporte un code stable, jamais un montant ou une donnée fournisseur.

Les opérations coûteuses ou soumises à droit sont : création d'invitation, import CSV, export, appel Google, préparation/exécution Automation et connecteur coûteux. Si leur droit est inconnu, elles sont fermées. Les lectures CRM de récupération restent accessibles selon les règles métier existantes et, ultérieurement, la politique de suspension P5.4.

### 6.3 Sièges et invitations

```text
sièges consommés = membres actifs + invitations non expirées réservant un siège
```

- la création d'invitation réserve atomiquement un siège après relecture du contrat ;
- l'acceptation vérifie une seconde fois le contrat et la réservation ;
- l'expiration, la révocation ou l'acceptation consomme/libère la réservation selon l'état canonique ;
- la désactivation d'un membre ne peut pas supprimer le dernier administrateur actif ;
- aucun processus ne désactive un membre pour revenir sous une limite ; un état de dépassement est visible et traité humainement.

## 7. Autorisations, RLS et audit

| Opération | Acteur autorisé | Contrôle |
| --- | --- | --- |
| Créer/modifier un brouillon de plan | administrateur plateforme catalogue | capacité plateforme dédiée ; journal d'audit |
| Publier/retirer une version | approbateur plateforme distinct | séparation créateur/approbateur ; validation de compatibilité |
| Lire le catalogue publié | service authentifié | lecture filtrée sur versions publiées uniquement |
| Rattacher une organisation à un contrat | administrateur plateforme contractuel | organisation explicite côté serveur ; version optimiste ; audit |
| Proposer une dérogation | administrateur plateforme contractuel | justification, clé connue, fin obligatoire |
| Approuver une dérogation | approbateur distinct | pas d'auto-approbation ; plafond de sûreté |
| Lire un contrat/droits d'organisation | membre actif selon capacité | RLS `organization_id` ; réponse minimisée |

Toutes les mutations tenant portent `organization_id` depuis le contexte serveur, jamais du corps de requête. Les politiques RLS doivent couvrir `organization_plan_contracts`, `plan_contract_overrides` et toute projection locataire. Les événements d'audit consignent code de plan/version, changement de statut, clés de droit, ancien/nouveau identifiant de version, approbateur et raison ; ni secret, ni moyen de paiement, ni montant détaillé dans des journaux d'erreur.

## 8. Interfaces et API P5.2

P5.2 expose seulement des contrats backend et interfaces administratives internes nécessaires à la preuve. Aucun écran public de prix, aucun bouton d'achat et aucun portail de facturation ne sont créés.

- lecture interne du catalogue publié ;
- lecture de la vue de droits effective de l'organisation courante ;
- mutations plateforme protégées pour brouillon, publication, contrat et dérogation ;
- réponses idempotentes pour rattachement et changement d'état ;
- conflits `409` versionnés ; refus `403` sans capacité ; refus `422` pour transition ou droit invalide ;
- codes déterministes tels que `catalog_version_not_published`, `contract_not_active`, `seat_limit_reached`, `override_expired` et `entitlement_unknown`.

L'application réelle de ces décisions sur toutes les routes CRM arrive en P5.4. Une intégration minimale P5.2 peut vérifier le moteur avec des cas synthétiques sans modifier le comportement de production existant.

## 9. Données, migrations et retour arrière

- migration additive uniquement : nouvelles tables, index, contraintes, politiques RLS et données de référence synthétiques ;
- aucun remplacement de capacité RBAC ou de règle métier existante dans la première migration ;
- le rollback applicatif désactive les lectures P5.2 sans supprimer contrats, audits ou versions ;
- le downgrade de schéma reste réservé aux bases jetables et ne peut pas effacer une version publiée ;
- les seeds de démonstration ne sont pas exécutés automatiquement dans un environnement contenant des organisations réelles ;
- un export de catalogue est une preuve technique versionnée sans coordonnées, secrets ou références de fournisseur non opaques.

## 10. Scénarios de validation attendus

| ID | Scénario | Preuve attendue |
| --- | --- | --- |
| P52-CAT-01 | Publier une version synthétique complète | Version immuable, droits compatibles, audit créateur/approbateur distincts. |
| P52-CAT-02 | Modifier un montant ou une limite publiée | Refus ; nouvelle version requise ; historique inchangé. |
| P52-ENT-01 | Calculer une limite avec contrat, dérogation et plafond | Valeur/provenance déterministes et plafond de sûreté respecté. |
| P52-ENT-02 | Version inconnue, expirée ou double contrat courant | Refus fermé avec code stable, aucune valeur inventée. |
| P52-SEAT-01 | Deux invitations concurrentes pour le dernier siège | Une seule réservation/acceptation réussit ; aucune surallocation. |
| P52-SEAT-02 | Déclassement sous la consommation actuelle | Changement bloqué ou `pending`, aucun membre désactivé. |
| P52-RLS-01 | Lire ou modifier contrat/dérogation d'une autre organisation | Lecture vide/refus et écriture refusée par RLS. |
| P52-AUD-01 | Publier, rattacher puis révoquer une dérogation | Audit append-only cohérent, sans secret ni payload de paiement. |
| P52-API-01 | Rejouer une mutation idempotente et un conflit optimiste | Même résultat au replay ; `409` sur version obsolète. |
| P52-NOEXT-01 | Exécuter l'ensemble de la recette | Aucun appel réseau fournisseur, email, checkout ou paiement. |

## 11. Backlog de livraison proposé

| ID | Priorité | Livrable | Critère de sortie |
| --- | --- | --- | --- |
| P52-01 | P0 | Registre fermé de droits et valeurs typées | Validation domaine exhaustive, tests négatifs et documentation des unités. |
| P52-02 | P0 | Tables catalogue/version/droits et migration/RLS | Upgrade, downgrade jetable, isolation et immutabilité prouvés. |
| P52-03 | P0 | Mutations internes de catalogue et contrats | **Implémenté le 7 octobre 2026** : migrations `0043` à `0047`, approbateur distinct, contrôle de version, contrat courant, transitions bornées, rejeu durable et audit append-only. La preuve Docker neuve reste à rejouer si le registre synthétique partagé est saturé. |
| P52-04 | P0 | Moteur de droit effectif | **Validé le 8 octobre 2026** : décision PostgreSQL sous RLS, provenance `contract`/`plan_version`/`override`/`safety_ceiling`, validation de fenêtre et devise de version, approbation de dérogation, ambiguïtés refusées et plafond technique explicite. Le verrou qualité complet a rejoué la preuve sur une base Docker neuve avec succès. |
| P52-05 | P0 | Réservations de sièges | **Validé** : concurrence, acceptation, expiration et dernier administrateur couverts sur PostgreSQL réel. |
| P52-06 | P1 | Dérogations contractuelles | **Validé** : séparation créateur/approbateur, échéance et révocation auditée. |
| P52-07 | P1 | API interne et vue minimale | **Validé** : autorisations/RLS, conflits et codes d'erreur stables. |
| P52-08 | P1 | Preuves et recette synthétique | **Validé le 9 octobre 2026** : verrou vert, 439 tests sans échec ni skip, absence d'effet externe et matrice plan/droit archivée. |

## 12. Décisions à confirmer avant le GO de développement

| ID | Proposition claire | Décision attendue |
| --- | --- | --- |
| P52-D01 | Adopter les codes stables `freemium`, `starter`, `business`, `custom`, sans les exposer publiquement avant P5.4. | **Confirmé le 5 octobre 2026.** |
| P52-D02 | CAD est la devise commerciale de référence. CAD, USD, EUR et XAF doivent être commercialisables dès le lancement, après validation des prix, territoires, règles fiscales et conditions fournisseur applicables. Chaque version et contrat porte sa devise exacte, sans conversion automatique. Le catalogue est hors taxes ; les factures futures présentent HT, taxes et TTC dans la devise du contrat. | **Confirmé le 5 octobre et reconfirmé le 21 octobre 2026 ; la restriction CAD seul consignée le 9 octobre est remplacée.** |
| P52-D03 | Utiliser des valeurs de prix strictement synthétiques pendant P5.2 ; la grille commerciale réelle est décidée séparément avec Finance. | **Confirmé le 5 octobre 2026.** |
| P52-D04 | Autoriser un contrat interne manuel par organisation, sans fournisseur ni paiement, avec états `pending`, `active`, `suspended`, `ended`. | **Confirmé le 5 octobre 2026.** |
| P52-D05 | Limiter le premier registre aux huit droits du tableau 6.1, dont le droit Google payant est interdit en Freemium et les droits Automation restent inactifs tant que Porte 4 est réservée. | **Confirmé le 5 octobre 2026.** |
| P52-D06 | Compter un membre actif et une invitation non expirée comme un siège ; bloquer la surallocation sans désactiver automatiquement un membre. | **Confirmé le 5 octobre 2026.** |
| P52-D07 | Exiger créateur et approbateur distincts pour publication de version et dérogation, avec justification et expiration obligatoire. | **Confirmé le 5 octobre 2026.** |
| P52-D08 | Livrer P5.2 comme moteur/API interne et preuves synthétiques ; réserver l'application systématique dans l'UX à P5.4. | **Confirmé le 5 octobre 2026.** |

## 13. Conditions d'entrée et de sortie

### Definition of Ready

- P52-D01 à P52-D08 confirmées ou explicitement amendées ;
- responsable Produit, Finance, Architecture et Sécurité identifié pour les validations concernées ;
- aucune réserve Porte 4 n'est déclarée levée implicitement ;
- les prix réels, taxes et termes contractuels sont soit approuvés, soit explicitement exclus des fixtures ;
- les règles de suspension et de récupération restent réservées à P5.4/P5.5 si non décidées.

### Definition of Done

- migration et rollback jetable démontrés, avec RLS et contraintes d'immutabilité ;
- catalogue, moteur, contrats, sièges et dérogations couverts par tests unitaires, intégration et concurrence ;
- aucune mutation P5.2 n'émet d'email, ne contacte un fournisseur ou ne crée de paiement ;
- audit et réponses API ne révèlent ni secret, ni PII superflue, ni référence fournisseur exploitable ;
- verrou qualité complet vert avec données synthétiques ;
- matrice plan/droit, décision de compatibilité et réserves restantes archivées ;
- aucune activation préproduction, staging ou production sans décision de mise en service distincte.

## 14. Réserves actives et suite

Les réserves Porte 4 restent actives : flags Automation désactivés, assistant `fake`, données synthétiques, aucun effet externe, capacité/D4/OpenAI réel bloquants pour toute activation. La mise en service P5.1 reste une étape opérationnelle séparée ; elle n'est pas une condition pour spécifier ou développer P5.2, mais elle sera requise pour produire des preuves préproduction réelles.

P5.3 peut avancer en simulateur et Stripe sandbox selon les décisions approuvées le 9 octobre 2026. Le paiement réel reste interdit sans autorisation fournisseur, signatures fiscales/juridiques et prix commerciaux approuvés. P5.4 ne contourne jamais le moteur P5.2 : il consomme sa décision effective et conserve les gardes serveur existantes.

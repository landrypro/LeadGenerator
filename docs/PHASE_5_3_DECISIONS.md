# Phase 5.3 — Registre des décisions abonnement et paiement

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 5.3 — Abonnement et fournisseur de paiement |
| Version | 1.0 — paquet approuvé |
| Date de décision | 9 octobre 2026 |
| Mise à jour des devises | 21 octobre 2026 — confirmation du commanditaire |
| Décisions P53-08 | 22 octobre 2026 — quatre propositions confirmées par le commanditaire |
| Décisions P53-10 | 24 octobre 2026 — `P53-10-D01` à `P53-10-D04` confirmées par le commanditaire |
| Report de recette P53-09 | 26 octobre 2026 — `P53-09-D01` confirmé par le commanditaire |
| Statut | Cadrage et préparation du simulateur autorisés ; paiement réel interdit |
| Autorité | Approbation produit donnée dans le cadre de la Phase 5 |
| Dépendances | P5.2 validée par verrou vert, catalogue interne, moteur de droits, RLS et audit |

## 1. Portée de l'approbation

Le paquet P5.3 est approuvé pour la conception, l'implémentation locale, les migrations additives, le simulateur
déterministe, l'intégration Stripe en sandbox et les preuves synthétiques. Cette approbation ne vaut pas :

- activation du mode Stripe réel ;
- publication de prix commerciaux ;
- perception ou remboursement d'argent ;
- validation fiscale, comptable ou juridique ;
- exposition d'un checkout à une organisation cliente ;
- levée des réserves P5.1, Porte 4, P5.4 ou P5.5.

Une autorisation distincte de mise en service reste obligatoire après signature des portes Finance, Juridique,
Sécurité et Exploitation.

## 2. Décisions confirmées

| ID | Décision | Réponse approuvée | Portée / réserve |
| --- | --- | --- | --- |
| `P53-D01` | Fournisseur | Stripe Billing est retenu pour la V1 : simulateur local, puis sandbox Stripe. | Le mode réel reste bloqué jusqu'à l'autorisation de mise en service. |
| `P53-D02` | Surface de paiement | Checkout, portail, factures et collecte des moyens de paiement sont hébergés par Stripe. | Marketteo ne reçoit ni numéro de carte, ni cryptogramme, ni donnée bancaire brute. |
| `P53-D03` | Entité vendeuse | Une seule entité vendeuse et un seul compte Stripe de référence sont autorisés par environnement. | Identité juridique, compte bancaire et contrat Stripe à confirmer avant le réel. |
| `P53-D04` | Devises de lancement | CAD est la devise de référence ; CAD, USD, EUR et XAF doivent être commercialisables dès le lancement. | Chaque devise exige prix signé, territoire, fiscalité et compatibilité fournisseur validés. Aucune conversion automatique. |
| `P53-D05` | Prix | Les montants réels ne sont pas inventés dans le code. | Finance fournit une matrice signée plan × cycle × devise × montant HT × code fiscal × date d'effet. |
| `P53-D06` | Essai | Aucun essai payant ni essai avec carte en V1 ; Freemium sert de parcours d'évaluation. | L'état `trialing` n'est pas émis par les flux V1. |
| `P53-D07` | Grâce | Un paiement échoué ouvre une grâce de 7 jours calendaires avant suspension. | La valeur est versionnée côté serveur ; aucun client ne peut la prolonger. |
| `P53-D08` | Annulation | Annulation en fin de période, sans prorata automatique. | L'accès est conservé jusqu'à la date confirmée par le fournisseur. |
| `P53-D09` | Changement de plan | Aucun changement de plan libre-service en P5.3. Les changements restent réservés à la plateforme/support. | L'expérience libre-service et l'application générale des droits arrivent en P5.4. |
| `P53-D10` | Remboursement | Aucun remboursement automatique. Demande manuelle possible dans les 14 jours suivant le premier paiement, sous réserve des droits impératifs et de l'approbation interne. | Politique et texte contractuel à valider juridiquement avant publication. |
| `P53-D11` | Prorata et remises | Aucun prorata automatique, coupon libre, facturation à l'usage ou dépassement facturé en V1. | Toute évolution exige une nouvelle décision et une recette financière. |
| `P53-D12` | Taxes | Stripe exécute le calcul configuré ; Marketteo ne déduit ni taux, ni juridiction, ni exemption. | Finance/Juridique restent responsables de la configuration, des inscriptions et du contrôle. |
| `P53-D13` | Webhooks | Signature vérifiée sur le corps brut, admission durable avant accusé, déduplication par identifiant fournisseur, traitement asynchrone idempotent. | Un événement navigateur ou une URL de retour ne modifie jamais l'abonnement. |
| `P53-D14` | Ordre des événements | Aucun événement ancien ne peut faire régresser une projection plus récente. | En cas d'ambiguïté, l'état fournisseur est relu par une réconciliation autorisée. |
| `P53-D15` | Réconciliation | Réconciliation incrémentale toutes les 15 minutes, réconciliation exhaustive quotidienne et commande manuelle auditée. | Aucune divergence n'est corrigée silencieusement. |
| `P53-D16` | Secrets | Secrets séparés par environnement, rotation avec fenêtre contrôlée à deux secrets et interdiction dans journaux/audits. | Rotation compromise testée avant toute activation réelle. |
| `P53-D17` | Données | Identifiants fournisseur opaques et projection minimale seulement ; aucune charge brute dans les journaux, audits ou API. | Le payload normalisé durable est borné et soumis à rétention. |
| `P53-D18` | Activation | Kill switch serveur activé par défaut ; simulateur et sandbox seulement pendant P5.3. | Toute activation réelle nécessite une décision datée et un artefact identifié. |

## 3. Décision de devise P5.2/P5.3 reconfirmée

Le commanditaire a reconfirmé le 21 octobre 2026 la décision `P52-D02` :

- CAD reste la devise commerciale de référence ; CAD, USD, EUR et XAF doivent être commercialisables dès le lancement ;
- chaque devise nécessite des prix signés et une validation des territoires, de la fiscalité et des conditions fournisseur ;
- aucun taux de change, arrondi inter-devise ou prix dérivé n'est autorisé ;
- un contrat et une facture conservent toujours leur devise exacte.

Cette confirmation remplace la restriction CAD seul consignée le 9 octobre et ne rend pas les versions P5.2 existantes
mutables. Elle ne vaut ni validation des prérequis ni autorisation de paiement réel.

## 4. Précisions approuvées pour P53-08 — réconciliation

Les quatre propositions ci-dessous précisent `P53-D15` pour le simulateur local. Le commanditaire a ensuite donné
son GO explicite pour le développement de P53-08 ; celui-ci n'est pas une autorisation de mise en service.

| ID | Décision approuvée | Limite de sécurité |
| --- | --- | --- |
| `P53-REC-D01` | Une projection locale en retard peut être corrigée automatiquement si l'état simulé et sa correspondance sont suffisamment certains. | Transaction et audit obligatoires ; en cas de doute, ou de différence de devise, prix ou référence, bloquer et demander un examen. |
| `P53-REC-D02` | Rechercher une preuve du résultat d'une opération incertaine avant toute autre action. | Ne jamais créer un second checkout ou remboursement pour lever l'incertitude ; sans preuve suffisante, conserver le dossier non résolu. |
| `P53-REC-D03` | Tester la reprise après interruption et redémarrage avec des moyens adaptés au simulateur. | Si l'état simulé ne peut être retrouvé de façon fiable, le signaler non résolu ; ne jamais inventer le résultat. |
| `P53-REC-D04` | Réconciliation manuelle limitée à un administrateur plateforme, pour une organisation ou référence précise, avec motif obligatoire. | Commande/API interne auditée, données minimisées ; aucune interface utilisateur complète dans ce lot. |

Les contrôles couvrent CAD, USD, EUR et XAF sans conversion. Les réserves P5.1 et Porte 4 et les portes d'activation
restent inchangées ; ni Stripe réel ni donnée client ne sont autorisés par ces décisions.

**Alignement d'implémentation du 23 octobre 2026 :** le snapshot fournisseur synthétique est désormais durable et
partagé entre l'API et le worker. Il est alimenté par un checkout simulé finalisé ou un webhook simulé signé et admis.
Une correction automatique reste limitée à `local_stale` prouvé et concordant ; elle résout la différence et écrit
l'audit dans la même transaction. Cet alignement applique les décisions ci-dessus sans élargir leur portée. Le verrou
local complet du 24 octobre 2026 a été rapporté vert ; la consolidation des preuves est préparée dans
[P53-10](./PHASE_5_3_P53_10_PREUVES_RECETTE_SYNTHETIQUE.md). Ses décisions `P53-10-D01` à `P53-10-D04` sont
approuvées le 24 octobre 2026. Après les interruptions Docker/WSL, le verrou complet du 27 octobre a produit une
preuve automatisée verte pour les 20 scénarios locaux et un paquet expurgé vérifié. Une nouvelle exécution doit
couvrir l'état source final après cet alignement documentaire ; les validations Produit/QA et Sécurité restent à obtenir.

### 4.1 Décisions approuvées pour P53-10 — preuves et recette synthétique

| ID | Décision | Limite |
| --- | --- | --- |
| `P53-10-D01` | La recette locale du simulateur est séparée de l'annexe Stripe sandbox P53-09. | `P53-SBX-01` reste ouvert ; aucune clôture globale P5.3 implicite. |
| `P53-10-D02` | Le manifeste et la recette sont versionnés ; JUnit et `evidence.json` sont générés ; un paquet expurgé est archivé avec SHA-256. | Aucun secret, donnée client ou log brut sensible dans Git ou le paquet. |
| `P53-10-D03` | L'absence d'effet externe est vérifiée par réseau bloqué ou instrumenté, avec inspection des artefacts. | Une déclaration seule ne suffit pas à établir cette preuve. |
| `P53-10-D04` | Produit/QA et Sécurité valident la recette locale. | Les autorisations Stripe et de mise en service suivent leurs portes distinctes. |

### 4.2 Décision de report de la recette Stripe sandbox P53-09

| ID | Décision confirmée le 26 octobre 2026 | Portée / réserve |
| --- | --- | --- |
| `P53-09-D01` | Reprendre la recette de bout en bout du parcours Stripe **en sandbox** dans le cadre de la recette complète P5.3. La recette synthétique locale P53-10 peut avancer séparément. | P53-09 et `P53-SBX-01` restent ouverts. Le correctif Checkout et la migration `20261025_0062` ont passé le verrou qualité local, mais leur application à l'environnement WSL et le parcours Checkout → webhook n'ont pas encore été confirmés. Aucun GO technique global P5.3 ni aucune mise en service réelle ne découle de ce report. |

À la reprise, appliquer la migration sur l'environnement WSL, vérifier Checkout et le webhook signé avec des données fictives, puis couvrir CAD, USD, EUR et XAF, les reprises/idempotences et les moyens de paiement disponibles pour le compte de test. Consigner les preuves et écarts dans l'annexe P53-09 avant toute décision de clôture globale.

## 5. Portes restant à signer avant le mode réel

| Porte | Responsable attendu | Preuve requise | Statut |
| --- | --- | --- | --- |
| Entité vendeuse et contrat Stripe | Direction / Juridique | Entité, compte, clauses, sous-traitants, résidence, export/suppression | Bloquant — à obtenir |
| Taxes et factures | Comptabilité / Fiscalité | Inscription applicable, territoires, codes fiscaux, GST/HST et factures | Bloquant — à obtenir |
| Conditions et remboursement | Juridique / Produit | CGU bilingues, annulation, grâce, remboursement, confidentialité | Bloquant — à obtenir |
| Matrice de prix | Finance / Produit | Montants mineurs HT, cycles, CAD, USD, EUR et XAF, hypothèses P95, frais et marge | Bloquant — à obtenir |
| Sécurité fournisseur | Sécurité / Architecture | Menaces, secrets, webhook, rotation, accès, journalisation, incident | Bloquant — à obtenir |
| Exploitation | Opérations | SLO, alertes, réconciliation, runbooks, sauvegarde et arrêt d'urgence | Bloquant — à obtenir |
| Autorisation réelle | Sponsor désigné | SHA/digest, verrou vert, preuves sandbox et signatures ci-dessus | Bloquant — décision distincte |

## 6. Références officielles consultées

Références vérifiées le 9 octobre 2026 :

- disponibilité de Stripe au Canada : <https://stripe.com/global> ;
- sessions du portail client : <https://docs.stripe.com/api/customer_portal/sessions/create> ;
- requêtes Stripe idempotentes : <https://docs.stripe.com/api/idempotent_requests> ;
- événements et récupération : <https://docs.stripe.com/api/events> ;
- GST/HST et fournitures numériques :
  <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/digital-economy-gsthst/charge-collect/cross-border.html> ;
- règles générales de perception GST/HST :
  <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html>.

Ces sources encadrent le choix technique. Elles ne remplacent pas un avis comptable, fiscal ou juridique adapté à
l'entité vendeuse et aux territoires effectivement ouverts.

## 7. Décision de passage

Le lot peut passer à la **spécification et au développement P5.3 limité au simulateur et à Stripe sandbox**. Il ne
peut pas passer au paiement réel tant que toutes les portes de la section 5 ne sont pas signées.

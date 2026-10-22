# Phase 5.3 — Registre des décisions abonnement et paiement

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Lot | 5.3 — Abonnement et fournisseur de paiement |
| Version | 1.0 — paquet approuvé |
| Date de décision | 9 octobre 2026 |
| Mise à jour des devises | 21 octobre 2026 — confirmation du commanditaire |
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

## 4. Portes restant à signer avant le mode réel

| Porte | Responsable attendu | Preuve requise | Statut |
| --- | --- | --- | --- |
| Entité vendeuse et contrat Stripe | Direction / Juridique | Entité, compte, clauses, sous-traitants, résidence, export/suppression | Bloquant — à obtenir |
| Taxes et factures | Comptabilité / Fiscalité | Inscription applicable, territoires, codes fiscaux, GST/HST et factures | Bloquant — à obtenir |
| Conditions et remboursement | Juridique / Produit | CGU bilingues, annulation, grâce, remboursement, confidentialité | Bloquant — à obtenir |
| Matrice de prix | Finance / Produit | Montants mineurs HT, cycles, CAD, USD, EUR et XAF, hypothèses P95, frais et marge | Bloquant — à obtenir |
| Sécurité fournisseur | Sécurité / Architecture | Menaces, secrets, webhook, rotation, accès, journalisation, incident | Bloquant — à obtenir |
| Exploitation | Opérations | SLO, alertes, réconciliation, runbooks, sauvegarde et arrêt d'urgence | Bloquant — à obtenir |
| Autorisation réelle | Sponsor désigné | SHA/digest, verrou vert, preuves sandbox et signatures ci-dessus | Bloquant — décision distincte |

## 5. Références officielles consultées

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

## 6. Décision de passage

Le lot peut passer à la **spécification et au développement P5.3 limité au simulateur et à Stripe sandbox**. Il ne
peut pas passer au paiement réel tant que toutes les portes de la section 4 ne sont pas signées.

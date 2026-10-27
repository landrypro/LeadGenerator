# DEV-00 — État initial et contrat de facturation

Date : 27 octobre 2026. GO DEV-00 donné par le commanditaire dans le chat.

**Statut : audit du dépôt et contrat préparés ; lot non clôturable tant que le relevé WSL n'est pas obtenu.** Aucun changement de comportement applicatif ni aucune migration exécutée pendant cet audit. DEV-01 n'est pas déclaré réalisé.

Références : [spécification et découpage](SPEC_P53_PARCOURS_FORFAITS_ET_FACTURATION.md), [décisions P53](PHASE_5_3_DECISIONS.md), [contrat sandbox](PHASE_5_3_P53_09_STRIPE_SANDBOX.md), [machine d'états P53](PHASE_5_3_SPECIFICATIONS_DETAILLEES.md).

## 1. Preuves et limites

| Contrôle | Résultat observé |
| --- | --- |
| Révision Git inspectée | `9b01f43e3ab4fb8d64df1911c11f15615dfed747` ; travail local préexistant conservé. |
| Tête Alembic des fichiers du dépôt | `20261025_0062 (head)` via `.venv/Scripts/python.exe -m alembic -c backend/alembic.ini heads`. Cette commande ne consulte pas la base. |
| Tests ciblés du contrat existant | **51 réussis**, en 6,68 s ; commande ci-dessous. Aucun appel Stripe réel ni preuve d'intégration PostgreSQL. |
| WSL actuel | `wsl.exe --list --quiet` échoue : « Le service ne peut pas être démarré parce qu'il est désactivé ou qu'aucun périphérique activé ne lui est associé. » La tentative hors bac à sable a été refusée par l'utilisateur. Aucun contournement tenté. |
| Révision appliquée à PostgreSQL WSL | **Non vérifiée pendant DEV-00.** La sortie historique du chat montre l'application de `20261025_0061` ; elle ne prouve ni l'état actuel ni l'application de `0062`. |
| Images API/worker, configuration effective et listener | **Non vérifiés pendant DEV-00.** Aucune lecture de `.env`, de clés ou de journaux sensibles. |

Commande de tests exécutée depuis la racine du dépôt sous PowerShell :

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_stripe_sandbox_contract.py tests/test_stripe_sandbox_customer_reuse.py tests/test_billing_domain.py tests/test_billing_sessions.py tests/test_billing_webhook_admission.py tests/test_billing_projection.py
```

Le verrou qualité complet `scripts/Test-QualityGateLocal.ps1` n'a pas été exécuté : la livraison DEV-00 est documentaire et le contrôle runtime requis reste bloqué par WSL. Les tests ci-dessus constituent un état de référence, pas une validation du futur cycle de facturation ni une clôture P53-09.

## 2. Inventaire des migrations

La chaîne du dépôt est linéaire jusqu'à `0062`. Les suffixes désignent les révisions complètes indiquées ci-dessous. Pour toutes ces migrations, l'état appliqué WSL reste à relever.

| Révision | Objet utile à DEV-00 |
| --- | --- |
| `20261009_0051` | Schéma de facturation : clients, souscriptions et registres associés. |
| `20261009_0052` | Admission durable et déduplication des webhooks. |
| `20261009_0053` | Projection par worker. |
| `20261010_0054` | Commandes Checkout et portail. |
| `20261010_0055` | Grâce, annulation et remboursement. |
| `20261021_0056` | Checkout multidevise. |
| `20261022_0057` | Observations de réconciliation. |
| `20261023_0058` | Corrections de réconciliation. |
| `20261024_0059` | Sessions Stripe sandbox en attente et projection dédiée des souscriptions. |
| `20261025_0060` | Privilèges de purge des connecteurs ; maillon de la chaîne, hors périmètre fonctionnel Billing. |
| `20261025_0061` | Offres Checkout publiées accessibles aux administrateurs d'organisation autorisés. |
| `20261025_0062` | Lecture du client Stripe existant de l'organisation pour le réutiliser au Checkout. |

Les migrations antérieures de catalogue/droits restent des dépendances, notamment `20261005_0039` et `20261008_0050`. Aucune nouvelle migration n'est nécessaire pour écrire ce constat. DEV-01 devra ajouter ses évolutions après la tête existante, sans réécrire une migration déjà distribuée.

## 3. Routes et protections constatées

Source principale : [routeur Billing](../backend/app/presentation/api/routers/billing.py) et [routeur catalogue](../backend/app/presentation/api/routers/catalog.py).

| Route | État constaté dans le code |
| --- | --- |
| `GET /api/billing/checkout-options` | Capacité `billing:manage`, contexte tenant et mode `stripe_sandbox` ; offres filtrées selon les devises configurées. |
| `POST /api/billing/checkout-session` | Session récente de 15 minutes, capacité, origine de confiance, CSRF, idempotence durable ; prix validé côté serveur. |
| `POST /api/billing/portal-session` | Route et cas d'usage présents ; adaptateur Stripe retourne `billing_provider_disabled`. |
| `POST /api/platform/billing/reconciliations` | Commande plateforme présente ; consommation planifiée de réconciliation dans le worker réservée au simulateur. |
| `POST /api/platform/billing/refunds` | Commande support présente ; remboursement Stripe non implémenté. |
| `POST /api/billing/webhooks/stripe` | Corps JSON borné, signature sur corps brut, version et `livemode=false`, admission durable ; `202` après admission, `200` pour répétition admise, `409` pour collision. Types non supportés : `422`. |
| `POST /api/billing/webhooks/simulated` | Entrée distincte pour le simulateur ; aucune preuve de paiement Stripe. |
| `GET /api/organization/catalog` | Vue du catalogue/contrat de l'organisation ; écran Billing actuel l'utilise. |
| `POST /api/platform/catalog/contracts` | Attribution de contrat catalogue ; ne constitue pas une preuve de paiement fournisseur. |
| `GET /api/billing/subscription`, vues plateforme Billing | Proposées dans la spécification ; absentes du routeur Billing inspecté. |

Les modèles SQL utilisent RLS et fonctions privilégiées à privilèges bornés. La migration `0059` force RLS sur les sessions Checkout et retire l'accès direct aux rôles applicatifs. Ces protections sont présentes dans les sources ; leur déploiement effectif reste à confirmer. Les réponses Billing utilisent `no-store`. Les commandes inconnues à la suite d'un timeout fournisseur nécessitent une réconciliation.

## 4. Contrat versionné des événements pour DEV-01

Version des requêtes et des événements attendus : **`2025-08-27.basil`**, constante de [stripe_contract.py](../backend/app/infrastructure/billing/stripe_contract.py), envoyée dans `Stripe-Version` par [stripe_client.py](../backend/app/infrastructure/billing/stripe_client.py). Ne pas changer cette version pendant DEV-01 sans adapter les fixtures et le contrat. Le listener CLI doit être contrôlé séparément : son rendu n'est pas modifié par cet en-tête de requête.

Les seuls événements admis actuellement sont les trois `customer.subscription.*` ci-dessous, normalisés en `subscription.snapshot`. La colonne cible fixe le comportement attendu ; elle ne décrit pas un comportement déjà implémenté.

| Événement Stripe | Aujourd'hui | Cible métier DEV-01 et condition |
| --- | --- | --- |
| `checkout.session.completed` | Rejeté `422`. | Rattacher la session connue et la souscription attendue ; normaliser `checkout.completed`. Ne pas activer sur ce seul événement ; attendre une facture payée et un état fournisseur compatible. |
| `customer.subscription.created` | Snapshot ; état Stripe `active` devient localement `active`. | Lier et actualiser les références/périodes. Avant preuve du premier paiement, conserver `pending_checkout`. |
| `customer.subscription.updated` | Snapshot ; projection limitée par la session Checkout terminée (écart E02). | Actualiser une souscription déjà liée, sans réutiliser l'éligibilité du premier Checkout. Annulation programmée → `canceling` si compatible ; dette et preuve de paiement conservées séparément. Une mise à jour `active` seule ne régularise pas une dette. |
| `customer.subscription.deleted` | Snapshot `canceled`, soumis à la même limite. | Confirmer la fin de la souscription liée et projeter `canceled`, sans recréer une souscription. |
| `invoice.paid` | Rejeté `422`. | Normaliser `invoice.paid`. Vérifier facture/client/souscription/devise/période et relire l'état fournisseur. Premier paiement confirmé : `pending_checkout` → `active` ; renouvellement : prolongation une seule fois ; régularisation : retour à `active` si compatible. Ne pas ressusciter un abonnement terminal ni effacer une annulation programmée. |
| `invoice.payment_failed` | Rejeté `422`. | Normaliser `invoice.payment_failed`. Premier paiement : rester sans droits payants. Renouvellement d'une période déjà payée : `active` → `past_due`, puis grâce de sept jours. Une répétition d'échec de la même dette ne repousse pas l'échéance de grâce. |
| `refund.updated` | Rejeté `422`. | Rattacher au paiement/facture vérifiés ; seul un remboursement confirmé réussi produit `refund.succeeded`. Les états en attente/échec ne signifient pas remboursement réussi ; conserver un suivi borné. Aucun effet implicite d'annulation. |

Le domaine existant possède `pending_checkout`, `active`, `past_due`, `grace_period`, `suspended`, `canceling`, `canceled`. Les échéances de grâce sont des transitions internes, pas des noms d'événements Stripe. La machine actuelle ne couvre pas toutes les combinaisons : échec de paiement pendant `canceling`, régularisation avec annulation encore programmée et facture reçue avant le rattachement. DEV-01 doit définir et tester ces combinaisons sans masquer la dette par le statut d'annulation.

Contrat d'admission et de reprise :

- Vérifier signature, version, mode test, structure et taille avant admission ; ne conserver que les données normalisées nécessaires.
- Dédupliquer durablement par fournisseur et identifiant d'événement ; détecter une collision de contenu. Une nouvelle livraison du même fait métier ne doit pas doubler son effet, même avec un identifiant d'événement différent.
- Un événement valide reçu avant la persistance du Checkout reste à reprendre ; l'absence temporaire de liaison ne doit pas provoquer une perte définitive.
- Après le premier rattachement, vérifier l'identité fournisseur persistée, le tenant, le prix et la devise ; les métadonnées seules ne suffisent pas.
- Un timestamp ancien ne régresse pas la projection ; deux événements contradictoires au même instant nécessitent une lecture fournisseur. La date de réception locale ne remplace pas une version d'état fournisseur.
- Évaluer `invoice.payment_action_required` et `invoice.finalization_failed` pour le cycle complet de DEV-03. Ils ne sont pas silencieusement ajoutés à la liste du listener avant leur implémentation.

Ces règles prolongent les décisions P53 et la documentation officielle déjà consultée pour la spécification : [événements d'abonnement](https://docs.stripe.com/billing/subscriptions/webhooks), [webhooks](https://docs.stripe.com/webhooks) et [idempotence](https://docs.stripe.com/api/idempotent_requests). Les formes exactes des objets de facture/remboursement devront être couvertes par des fixtures de la version épinglée.

## 5. Écarts prioritaires identifiés par lecture du code

| ID | Constat précis | Action attendue |
| --- | --- | --- |
| E01 | `subscription_snapshot_from_object` traduit directement `active` en `ACTIVE` ; la projection `0059` peut activer le contrat sans événement de facture. | DEV-01 : preuve de paiement distincte avant attribution des droits. |
| E02 | `project_stripe_sandbox_subscription_event` ignore un événement si `v_checkout.completed_at IS NOT NULL`, puis remplit ce champ après le premier événement traité. Les snapshots ultérieurs liés à cette commande sont donc ignorés. | DEV-01 : séparer le premier rattachement du suivi de la souscription. Tester created → updated → deleted. |
| E03 | La même fonction ignore définitivement un événement si la session n'est pas encore enregistrée. Le worker peut recevoir le webhook avant `complete_stripe_sandbox_checkout`. | DEV-01 : reprise bornée sur liaison temporairement absente et réconciliation, sans perdre le fait métier. |
| E04 | Le worker dirige tous les événements Stripe vers une fonction SQL limitée à `subscription.snapshot`. | DEV-01 : adapter ensemble normaliseur, données persistées et dispatch SQL ; ajouter seulement le vérificateur serait insuffisant. |
| E05 | `list_events` Stripe est désactivé ; le worker de réconciliation et son ordonnanceur sont construits uniquement en mode `simulated`. | DEV-01 : fournir le chemin de reprise Stripe et contrôler les résultats ambigus. |
| E06 | La normalisation donne priorité à `cancel_at_period_end` sur plusieurs statuts de paiement ; état d'annulation et dette risquent d'être confondus. | DEV-01 : conserver l'intention d'annulation et l'état de paiement sans ouverture indue de droits. |
| E07 | Portail et remboursement retournent `PROVIDER_DISABLED` dans l'adaptateur Stripe. | DEV-03 : implémenter les commandes et leurs confirmations ; la présence d'une route ne prouve pas leur fonctionnement. |
| E08 | Migration `0062` disponible mais application WSL inconnue. | DEV-00 : obtenir le relevé ci-dessous avant clôture. |

Sources de ces constats : [projection SQL Stripe 0059](../backend/app/infrastructure/postgres/migrations/versions/20261024_0059_stripe_sandbox_pending_checkout.py), [worker de projection](../backend/app/infrastructure/postgres/billing_projection.py), [worker applicatif](../backend/app/cli/worker.py), [passerelle Stripe](../backend/app/infrastructure/billing/stripe_sandbox.py), [cas d'usage Checkout](../backend/app/application/use_cases/billing.py). Les écarts SQL sont issus d'une inspection statique, pas d'une reproduction sur la base WSL.

## 6. Relevé WSL restant, en lecture seule

Exécuter depuis la racine du dépôt dans WSL. La première commande affiche la tête contenue dans l'image API ; la seconde lit la révision de la base et la présence des fonctions clés. Elle n'extrait aucun client, paiement, courriel ou secret et n'exécute aucune migration.

```bash
docker compose --profile runtime exec -T api \
  python -m alembic -c backend/alembic.ini heads

docker compose --profile runtime exec -T postgresql sh -lc \
  'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<'SQL'
BEGIN READ ONLY;
SELECT 'database_revision|' || version_num FROM public.alembic_version;
SELECT 'checkout_table|' || (to_regclass('public.stripe_sandbox_checkout_sessions') IS NOT NULL)::text;
SELECT 'customer_reuse_function|' || (to_regprocedure('app_private.tenant_stripe_customer_reference()') IS NOT NULL)::text;
SELECT 'checkout_complete_function|' || (to_regprocedure('app_private.complete_stripe_sandbox_checkout(uuid,uuid,text,text,text,text,timestamptz)') IS NOT NULL)::text;
SELECT 'stripe_projection_function|' || (to_regprocedure('app_private.project_stripe_sandbox_subscription_event(uuid)') IS NOT NULL)::text;
SELECT 'checkout_rls|' || relrowsecurity::text || '|' || relforcerowsecurity::text
FROM pg_class WHERE oid=to_regclass('public.stripe_sandbox_checkout_sessions');
ROLLBACK;
SQL
```

Attendu pour la base à jour : révision `20261025_0062`, fonctions présentes et RLS activée/forcée. Une différence entre tête du dépôt, tête de l'image et révision de base reste un écart à résoudre ; ne pas le masquer en exécutant un `stamp`. La présence des fonctions ne prouve pas à elle seule leur contenu ni une recette réussie.

DEV-00 pourra être clôturé après consignation du relevé WSL et résolution/documentation de tout écart bloquant. En attendant, le contrat et les écarts E01–E07 sont disponibles pour préparer DEV-01, sans GO implicite sur ce lot ni sur le paiement réel.

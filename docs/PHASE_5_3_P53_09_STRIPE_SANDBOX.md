# P53-09 — Contrat et état de la sandbox Stripe

Le développement et la recette concernent exclusivement le compte Stripe de test
`acct_1S58J0KHI7agUUjE`. Aucune de ces valeurs n'est un prix commercial.

**Statut au 26 octobre 2026 — `P53-09-D01` :** la recette Stripe sandbox est
reportée à la recette complète P5.3. Le correctif de réutilisation du client
Stripe et la migration `20261025_0062` ont passé le verrou qualité local ; leur
application dans l'environnement WSL et le parcours Checkout → webhook restent
à confirmer. P53-09 et `P53-SBX-01` demeurent ouverts. La recette synthétique
P53-10 peut avancer séparément, sans clôture technique globale P5.3 ni
autorisation de paiement réel.

## Contrat épinglé

- Version API des requêtes et des événements webhook : `2025-08-27.basil`.
- En-tête `Stripe-Version` obligatoire sur chaque requête ; même version à choisir
  pour le point d'entrée ou le transfert Stripe CLI.
- Événements à intégrer avant activation : `checkout.session.completed`,
  `customer.subscription.created`, `customer.subscription.updated`,
  `customer.subscription.deleted`, `invoice.paid`,
  `invoice.payment_failed`, `refund.updated`.
- Signature sur corps brut, tolérance de 300 secondes, secret `whsec_` propre au
  raccordement et fenêtre de rotation à deux secrets.
- Seuls les objets et événements `livemode=false` sont acceptés. Aucun nom ou
  contenu d'événement Stripe n'est transmis tel quel au domaine.
- Une version différente, un statut ou une forme non pris en charge ferme le
  traitement. Les événements sans association vérifiée à une organisation ne
  modifient aucun droit.

À ce stade, seul le schéma des événements `customer.subscription.*` est
normalisé par le vérificateur. La route publique dédiée
`POST /api/billing/webhooks/stripe` vérifie le corps brut et l'en-tête
`Stripe-Signature`, puis admet l'événement sans persister le corps. Les
événements Checkout, facture et remboursement restent rejetés jusqu'à leur
liaison durable ; ils ne sont jamais acquittés à vide.

La version est celle publiée dans la [référence Stripe](https://docs.stripe.com/api/versioning).
Les objets de souscription ont leur période sur
[`items.data[]`](https://docs.stripe.com/api/subscriptions/object). Les
[événements](https://docs.stripe.com/api/events/object) portent leur propre
`api_version`, indépendant de l'en-tête des requêtes ultérieures.

## Produits et prix fictifs créés dans le compte de test

Produit `prod_VVHGIg746OfLHy` : `P53-09 Sandbox Currency Matrix`.

| Devise | Montant affiché par mois | Montant API attendu en unité mineure | Référence de prix |
| --- | ---: | ---: | --- |
| CAD | 10,00 | 1000 | `price_1UUGu2KHI7agUUjE8qYdQ7Ky` |
| USD | 10,00 | 1000 | `price_1UUGtlKHI7agUUjEtvyOM6Z0` |
| EUR | 10,00 | 1000 | `price_1UUGuHKHI7agUUjEuycGNYB2` |
| XAF | 5 000 | 5000 | `price_1UUGuhKHI7agUUjEW3DkDOni` |

Le tarif USD récurrent est le tarif par défaut. Un ancien tarif **ponctuel**
fictif de 1 000 USD (`price_1UUGhuKHI7agUUjEfXTtMIY3`) reste dans le
catalogue ; il ne doit pas être associé à une version d'abonnement. Le client
Stripe refuse explicitement un prix non récurrent. Ces montants n'impliquent
aucune conversion ; XAF est sans décimales dans l'API Stripe. La création des
prix ne prouve pas encore la disponibilité de Checkout et des moyens de
paiement pour XAF sur ce compte. Les unités mineures du tableau sont déduites
de la [règle Stripe](https://docs.stripe.com/currencies) ; leur valeur API
réelle et le parcours Checkout restent à vérifier dans la recette.

Le client de sandbox crée un client Stripe technique sans PII et inscrit
uniquement l'UUID de la commande Billing dans `client_reference_id` et dans
`subscription_data.metadata.billing_command_id`. Le webhook signé normalise cet
UUID ; aucune référence d'organisation fournie par le navigateur ne décide du
rattachement.

Les références de prix sont injectées hors Git par
`BILLING_STRIPE_PRICE_{CAD,USD,EUR,XAF}_MONTHLY`. Avant la création de Checkout,
le serveur vérifie auprès de Stripe la devise, le montant en unité mineure et
la récurrence du prix sélectionné. Une version de catalogue d'un montant ou
d'un cycle différents est refusée avant tout paiement.

## Intégration encore ouverte

La migration `20261024_0059` introduit une persistance dédiée des sessions
Checkout Stripe en attente : commande, client, prix, devise et expiration sont
scellés avant le webhook. Le worker crée ou met à jour l'abonnement local
uniquement si le `billing_command_id`, le client `cus_…`, le prix, la devise et
la souscription `sub_…` de l'événement signé correspondent tous à cette session.
Une discordance est ignorée sans activation de droits. Le branchement du flux
Checkout `stripe_sandbox` appelle cette persistance immédiatement après la
création réussie de Checkout ; aucun abonnement local n'est donc créé avant le
webhook.

La migration `20261025_0062` permet à la préparation Checkout de lire, avec
les droits de l'administrateur de l'organisation, le client Stripe déjà lié à
cette organisation. Les tentatives suivantes réutilisent ce `cus_…` ; elles ne
créent plus un autre client que la persistance refuserait. Une organisation
sans client enregistré en crée un lors de son premier Checkout.

## Préparation de la recette locale Stripe CLI

Le raccordement retenu est local via Stripe CLI dans WSL. Les conteneurs `api`
et `worker` reçoivent les variables `BILLING_STRIPE_*` depuis l'environnement
Compose ; les valeurs restent absentes de ce dépôt. Avant de les démarrer,
injecter hors Git le mode `stripe_sandbox`, la clé `sk_test_…`, les quatre
références de prix du tableau et le secret `whsec_…` affiché par le listener.

Le listener doit transférer vers
`http://127.0.0.1:8000/api/billing/webhooks/stripe` et écouter seulement
`customer.subscription.created`, `customer.subscription.updated` et
`customer.subscription.deleted`. La version de l'endpoint doit rester
`2025-08-27.basil` : Stripe CLI rend les événements locaux selon la version par
défaut de la sandbox et ne permet pas d'en imposer une arbitraire. L'application
épingle donc cette version constatée ; Stripe rend les événements d'un endpoint
HTTPS selon la version de cet endpoint,
non selon la version d'une requête ultérieure.

Un endpoint HTTPS distant n'est pas créé pour cette recette locale. Son secret
de signature serait distinct de celui fourni par `stripe listen`.

### Publier les quatre offres fictives dans la base locale

Après la migration `20261025_0061`, si `plan_catalog` est vide, créer un
approbateur plateforme de test distinct du compte existant. Depuis WSL, à la
racine du dépôt, reconstruire l'API puis exécuter les deux commandes ci-dessous.
Elles exigent `APP_ENV=development` ou `test` et
`BILLING_PROVIDER_MODE=stripe_sandbox`. La première exige aussi l'URL de
migration propriétaire. Les mots de passe sont saisis sans écho dans WSL ; ne
pas les placer dans les commandes, les journaux ou Git.

```bash
docker compose --profile runtime up -d --build --force-recreate api

docker compose --profile runtime run --rm -it \
  -e MIGRATION_DATABASE_URL="postgresql+asyncpg://prospect:${POSTGRES_PASSWORD:-prospect-development-only}@postgresql:5432/${POSTGRES_DB:-prospect}" \
  -e STRIPE_SANDBOX_APPROVER_CONFIRM=CREATE_STRIPE_SANDBOX_APPROVER \
  api python -m backend.app.cli.create_stripe_sandbox_approver

docker compose --profile runtime run --rm -it \
  -e STRIPE_SANDBOX_CATALOG_CONFIRM=PROVISION_STRIPE_SANDBOX_CATALOG \
  api python -m backend.app.cli.provision_stripe_sandbox_catalog
```

Le second programme demande le courriel et le mot de passe du premier
administrateur plateforme, puis le mot de passe du nouvel approbateur
`approbateur-stripe@example.test`. Il vérifie auprès de Stripe que les prix CAD,
USD, EUR et XAF configurés sont actifs, fictifs et mensuels. Il reprend leurs
montants API exacts, y compris XAF, crée des versions mensuelles du plan
`starter` par l'API et les publie avec le second compte. Les identifiants
d'opération rendent une relance après interruption idempotente avec les mêmes
acteurs et les mêmes prix. Aucune organisation ni aucun contrat n'est créé par
ces commandes ; Checkout crée le contrat en attente lors de l'essai utilisateur.
Rafraîchir ensuite `/app/billing` avec un administrateur de l'organisation.

Si le compte approbateur a déjà été créé, ne pas relancer sa création. Si la
commande catalogue échoue avec une erreur d'encodage ASCII, contrôler localement
que `.env` contient les vraies valeurs `sk_test_…` et `whsec_…` (les points de
suspension désignent ici des valeurs à remplacer, pas du texte à copier). La
clé serveur de test vient du compte Stripe de test ; le secret de signature
vient du processus `stripe listen` actif. Enregistrer les deux valeurs dans
`.env`, sans les afficher dans le terminal ni les transmettre dans un message,
puis reconstruire l'API et relancer uniquement la commande de provisionnement
du catalogue.

## Écran de recette Billing

La route `/app/billing` apparaît dans Administration pour un administrateur
ayant `billing:manage`. Elle présente les versions mensuelles publiées et
effectives dont la devise possède un prix de test configuré. La lecture
`GET /api/billing/checkout-options` passe par une fonction SQL à privilèges
bornés, sans exposer les références Stripe ni élargir la vue tenant du
catalogue. L'administrateur choisit une offre ; l'écran transmet son UUID à
`POST /api/billing/checkout-session` avec une clé d'idempotence, puis ouvre
l'URL Stripe Checkout. Si aucune offre n'est publiée, l'écran l'explique et
bloque la création de session.
Le retour `?checkout=success` affiche seulement un retour de navigation ; le
webhook reste l'unique confirmation de l'abonnement.

### Reprise après plusieurs essais de création Checkout

Si Stripe a créé des sessions mais que l'écran affiche « L'état du paiement
doit être vérifié », contrôler en lecture seule les nombres de clients Stripe,
de sessions enregistrées et de commandes Checkout `reserved` et `succeeded`.
Le cas `1|1|2|1` signifie qu'une première session est persistée et que deux
tentatives ultérieures sont restées réservées ; elles ont utilisé de nouveaux
clients Stripe. Pour installer le correctif, reconstruire l'image API, migrer
vers `20261025_0062`, puis recréer l'API et le worker :

```bash
docker compose --profile runtime build api worker

docker compose --profile runtime run --rm \
  -e MIGRATION_DATABASE_URL="postgresql+asyncpg://prospect:${POSTGRES_PASSWORD:-prospect-development-only}@postgresql:5432/${POSTGRES_DB:-prospect}" \
  api python -m alembic -c backend/alembic.ini upgrade head

docker compose --profile runtime up -d --force-recreate api worker
```

Rafraîchir ensuite `/app/billing` avant de lancer un nouvel essai : la page
génère une nouvelle clé d'idempotence. Vérifier que la nouvelle session
Checkout apparaît, puis payer uniquement avec une carte fictive. Ne pas
terminer les anciennes sessions Stripe ouvertes, afin de ne pas déclencher
leurs événements webhook après le nouvel essai.

Dans la recette où l'API Docker sert aussi le frontend sur le port 8000,
`PUBLIC_APP_URL` doit désigner l'origine ouverte dans le navigateur, par exemple
`http://127.0.0.1:8000`. Si Vite sert le frontend sur 5173, utiliser cette
origine à la place. Reconstruire l'image `api` après modification du frontend.

P53-09 reste ouvert jusqu'aux tests de reprise, à la recette sur les quatre
devises et à la confirmation de compatibilité du compte Stripe avec les moyens
de paiement attendus. L'autorisation de mise en service réelle est séparée.

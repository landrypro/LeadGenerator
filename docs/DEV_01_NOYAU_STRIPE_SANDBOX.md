# DEV-01 — Noyau Stripe sandbox

## État du code au 27 octobre 2026

La version Stripe `2025-08-27.basil` reste épinglée. Le vérificateur admet les
événements de souscription, `checkout.session.completed`, `invoice.paid`,
`invoice.payment_failed` et `refund.updated` seulement après signature valide
et contrôle `livemode=false`. L'inbox ne conserve que des références opaques.

Le worker relit la souscription, la facture courante et, selon l'événement,
la session Checkout, la facture liée ou le remboursement. Il vérifie le client,
le prix, la devise, la période, la quantité et le montant en unité mineure.
Une souscription Stripe ne rend le contrat actif qu'avec une facture payée
pour la période attendue ; la page de retour Checkout n'ouvre aucun droit.
Le remboursement est consigné sans annulation implicite de l'abonnement.

La projection est transactionnelle et protégée par le numéro de tentative
de l'inbox et l'heure de l'observation. Le projecteur du simulateur ne peut
plus traiter un événement Stripe par erreur. Les anciennes souscriptions
sandbox actives sont placées en attente par la migration `0063`, jusqu'à
une nouvelle observation authentifiée. La migration `0064` ajoute deux
curseurs durables : rejeu borné des événements et observation quotidienne
des souscriptions. Un événement en échec peut être réadmis après rapprochement.

## Preuves obtenues

- `pytest -q tests --ignore=tests/integration` : 525 réussis.
- Tests ciblés de normalisation/résolution Stripe : 27 réussis.
- Dans une base PostgreSQL isolée, `alembic downgrade 20261025_0062`,
  `upgrade head` et `check` : réussis ; révision `20261027_0064`.
- Intégration Billing sur cette base : 19 réussis, dont premier paiement,
  renouvellement échoué, grâce, régularisation, événement ancien,
  mauvais rattachement et reprise d'un événement en échec.
- `ruff check`, `ruff format --check`, `mypy` et `git diff --check` : réussis.

## Réserve d'exploitation

La base applicative accessible en lecture seule est à `20261025_0061`.
Les nouvelles migrations n'y ont pas été appliquées. Le verrou qualité local
complet s'arrête à l'étape « Docker disponible » parce que le daemon Docker
Windows est absent. La recette Stripe CLI, les quatre devises et le parcours
navigateur → Checkout → webhook → contrat restent à réaliser dans DEV-06.
Ne pas qualifier P53-09 ni P5.3 de clos à partir des tests isolés.

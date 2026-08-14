# Phase 2.4.4 - Specifications detaillees de suspension, reactivation et historique

| Metadonnee | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Increment | 2.4.4 - Suspension, reactivation et historique |
| Version | 1.0 |
| Date | 13 aout 2026 |
| Statut | Propose a validation produit |
| Prerequis | 2.4.1, 2.4.2 et 2.4.3 implementes et recette fonctionnelle locale validee |
| Passage Azure | Reporte au verrou final de la phase 2.4 |
| Changement visuel | Oui, cible sur les actions plateforme et l'historique des invitations |
| Migration prevue | Oui, si les tables d'idempotence ou colonnes d'historique manquent |

Ce document raffine le contrat global de
[`PHASE_2_4_SPECIFICATIONS_DETAILLEES.md`](PHASE_2_4_SPECIFICATIONS_DETAILLEES.md) pour livrer le dernier bloc metier
de l'audit transactionnel avant le verrou qualite 2.4.5.

## 1. Objectif

2.4.4 ajoute trois capacites attendues depuis le debut de la phase 2.4 :

1. suspendre une organisation depuis la plateforme ;
2. reactiver une organisation suspendue depuis la plateforme ;
3. consulter l'historique complet des invitations, y compris les etats terminaux.

La suspension est une mesure administrative reversible. Elle bloque l'acces operationnel a l'organisation et les appels
Google facturables, mais elle ne supprime rien. La reactivation restaure l'acces a l'organisation, sans reactiver
implicitement des membres desactives, des invitations revoquees ou des donnees futures.

## 2. Resultat utilisateur attendu

- l'Administrateur de plateforme voit le statut reel d'une organisation ;
- il peut suspendre une organisation active avec une raison obligatoire ;
- il peut reactiver une organisation suspendue avec une raison obligatoire ;
- il comprend si une operation a deja ete prise en compte apres une reponse reseau ambigue ;
- les membres d'une organisation suspendue ne peuvent plus utiliser les ecrans locataires ni Google ;
- un utilisateur membre de plusieurs organisations peut basculer vers une autre organisation active ;
- un Admin ou Manager consulte les invitations ouvertes et terminales de son organisation ;
- les invitations acceptees, expirees et revoquees sont visibles sans action possible ;
- les evenements correspondants apparaissent dans l'audit avec metadonnees minimales.

## 3. Invariants non negociables

1. Une suspension ne supprime ni organisation, ni membres, ni invitations, ni audit.
2. Une reactivation ne reactive aucun membre ou invitation terminale.
3. Une organisation `provisioning` ne peut pas etre suspendue par la route standard.
4. Une organisation deja suspendue ne peut pas etre suspendue une seconde fois avec une nouvelle mutation.
5. Une organisation active ne peut pas etre reactivee.
6. La version de l'organisation est obligatoire pour eviter les ecrasements silencieux.
7. `operation_id` est obligatoire pour rendre l'action idempotente.
8. Le meme `operation_id` avec le meme contenu retourne le resultat initial sans second evenement.
9. Le meme `operation_id` avec un contenu divergent retourne `409 idempotency_conflict`.
10. La raison est codee, jamais une note libre.
11. `external_reference` reste optionnel, court et sans donnee personnelle.
12. La suspension bloque immediatement les routes locataires et Google.
13. L'organisation suspendue reste visible dans les vues plateforme.
14. L'historique des invitations vient des tables metier, pas d'une reconstruction depuis l'audit.
15. Les courriels d'invites restent visibles uniquement aux capacites d'invitation autorisees.
16. Aucun etat, filtre, curseur ou operation idempotente n'est stocke dans le navigateur.

## 4. Perimetre

### 4.1 Inclus

- routes plateforme `suspend` et `reactivate` ;
- idempotence transactionnelle des operations plateforme ;
- raisons normalisees et reference externe limitee ;
- audit `organization.suspended` et `organization.reactivated` ;
- blocage d'acces locataire apres suspension ;
- blocage des recherches Google pour une organisation suspendue ;
- rafraichissement de la liste et du detail d'organisation apres mutation ;
- affichage du statut, de la version et des actions disponibles dans l'interface plateforme ;
- filtre d'invitations ouvertes ou historiques ;
- affichage des invitations acceptees, revoquees et expirees ;
- tests de concurrence, conflit, idempotence et non-regression.

### 4.2 Exclu

- suppression definitive d'organisation ;
- purge, anonymisation ou export d'audit ;
- suspension automatique par facturation ;
- integration Stripe ou plans commerciaux ;
- notes libres de suspension ;
- notifications courriel de suspension/reactivation ;
- journalisation des connexions et echecs d'authentification ;
- modification du workflow futur prospects/Kanban ;
- chantier bilingue complet ;
- deploiement Oracle ou Azure, traite au verrou final 2.4.5.

## 5. Acteurs et capacites

| Action | Plateforme | Admin | Manager | Sales |
| --- | :---: | :---: | :---: | :---: |
| Voir statut plateforme d'une organisation | Oui | Non | Non | Non |
| Suspendre une organisation | Oui | Non | Non | Non |
| Reactiver une organisation | Oui | Non | Non | Non |
| Consulter invitations ouvertes | Non | Oui | Oui, si capacite existante | Non |
| Consulter tout l'historique des invitations | Non | Oui | Oui, si `invitations:read` | Non |
| Renvoi/revocation d'une invitation terminale | Non | Non | Non | Non |

Les actions de suspension et reactivation exigent une capacite plateforme explicite, par exemple
`platform:organizations:manage`. Cette capacite ne donne aucun acces aux donnees locataires.

## 6. Cycle de vie organisation

Etats pris en charge :

| Etat courant | Action | Etat cible | Autorise |
| --- | --- | --- | --- |
| `provisioning` | suspendre | - | Non |
| `active` | suspendre | `suspended` | Oui |
| `suspended` | suspendre | - | Non |
| `active` | reactiver | - | Non |
| `suspended` | reactiver | `active` | Oui |

La version est incrementee uniquement lors d'une transition reelle. Un rejeu idempotent ne modifie ni la version, ni
`updated_at`, ni l'audit.

## 7. Contrat API plateforme

### 7.1 Suspendre une organisation

```http
POST /api/platform/organizations/{organization_id}/suspend
```

Corps :

```json
{
  "operation_id": "uuid",
  "version": 3,
  "reason_code": "customer_request",
  "external_reference": "TICKET-123"
}
```

### 7.2 Reactiver une organisation

```http
POST /api/platform/organizations/{organization_id}/reactivate
```

Le corps est identique a la suspension.

### 7.3 Reponse de succes

```json
{
  "organization": {
    "id": "uuid",
    "name": "Entreprise Demonstration",
    "status": "suspended",
    "version": 4,
    "updated_at": "2026-08-13T15:00:00Z"
  },
  "operation_id": "uuid",
  "replayed": false
}
```

Chaque reponse porte `Cache-Control: no-store` et `X-Request-ID`.

## 8. Raisons autorisees

Codes initiaux :

| Code | Usage |
| --- | --- |
| `customer_request` | demande explicite du client |
| `billing` | situation administrative ou paiement |
| `security` | risque de securite |
| `compliance` | obligation legale ou conformite |
| `administrative` | correction ou decision interne |
| `other` | cas exceptionnel, sans note libre |

`external_reference` est limitee a 64 caracteres, avec lettres, chiffres, tirets, underscores, deux-points et slash.
Elle sert a pointer vers un dossier externe ; elle ne sert pas a decrire le motif.

## 9. Idempotence et concurrence

Une table ou un mecanisme equivalent conserve :

- `operation_id` ;
- type d'operation (`suspend` ou `reactivate`) ;
- organisation cible ;
- empreinte canonique de la commande ;
- statut et resultat minimal ;
- `request_id` initial ;
- dates de creation et derniere lecture.

Regles :

- meme `operation_id` et meme empreinte : retour du resultat initial avec `replayed = true` ;
- meme `operation_id` et autre empreinte : `409 idempotency_conflict` ;
- version obsolete : `409 organization_version_conflict` avec statut et version courants minimises ;
- transition impossible : `409 invalid_organization_transition` ;
- erreur apres commit et avant reponse : le rejeu retourne l'etat deja valide.

## 10. Blocage apres suspension

Des qu'une organisation est suspendue :

- les routes locataires retournent `403 organization_suspended` ou redirigent vers le choix d'organisation cote UI ;
- les recherches Google retournent `403 organization_suspended` avant tout appel fournisseur ;
- le changement vers une autre organisation active reste possible ;
- une session existante ne peut pas continuer a agir avec une organisation suspendue ;
- les routes plateforme restent capables de relire et reactiver l'organisation.

Le controle est effectue cote serveur pour chaque operation sensible. L'interface peut masquer ou desactiver des
actions, mais elle ne constitue jamais le verrou de securite.

## 11. Audit attendu

Transitions auditees :

| Action | Portee | Entite | Metadonnees autorisees |
| --- | --- | --- | --- |
| `organization.suspended` | `platform` | `organization` | `previous_status`, `new_status`, `reason_code`, `external_reference_present`, `version` |
| `organization.reactivated` | `platform` | `organization` | `previous_status`, `new_status`, `reason_code`, `external_reference_present`, `version` |

L'audit ne contient jamais de note libre, courriel, cle API, detail Google, contenu locataire, telephone ou site Web.
Un rejeu idempotent ne cree pas de second evenement.

## 12. Historique des invitations

`GET /api/organization/invitations` conserve son role de source de lecture des invitations. Il accepte :

- `state=open|active|expired|accepted|revoked|all`, avec `open` par defaut ;
- `limit` de 25 par defaut, 100 maximum ;
- un curseur stable base sur `created_at` puis `id` ;
- aucun total exact.

Definitions :

| Filtre | Etats inclus |
| --- | --- |
| `open` | `active` non expiree |
| `active` | invitations actives, expirees exclues si le systeme les calcule dynamiquement |
| `expired` | invitations dont l'expiration est atteinte |
| `accepted` | invitations acceptees |
| `revoked` | invitations revoquees |
| `all` | tous les etats visibles |

Les actions disponibles restent strictes :

- invitation active non expiree : renvoi ou revocation selon capacite ;
- invitation expiree : aucune action en 2.4.4 ;
- invitation acceptee : aucune action ;
- invitation revoquee : aucune action.

Les transitions passees manquantes ne sont pas inventees. L'historique expose l'etat courant et les dates metier deja
fiables.

## 13. Interface plateforme

La vue plateforme doit permettre :

- d'identifier clairement le statut `provisioning`, `active` ou `suspended` ;
- de desactiver les actions impossibles ;
- d'ouvrir une confirmation de suspension ou reactivation ;
- de choisir une raison obligatoire ;
- de saisir une reference externe optionnelle ;
- de conserver la meme intention si la reponse HTTP est ambigue et que l'utilisateur relance ;
- de recharger l'organisation apres conflit de version ;
- d'afficher un message court sans exposer details internes.

Le bouton d'action ne doit pas etre disponible pendant une mutation en cours. Le focus revient sur l'organisation
modifiee apres succes ou conflit.

## 14. Interface invitations

La vue membres/invitations ajoute un filtre lisible :

- `En cours` pour le flux quotidien ;
- `Tout l'historique` pour inclure les etats terminaux ;
- option technique ou segment additionnel par etat si l'espace UI le permet sans lourdeur.

Chaque ligne affiche au minimum : destinataire, role propose, etat, date de creation, date d'expiration et date
terminale connue. Les actions terminales sont absentes ou desactivees avec libelle accessible.

## 15. Erreurs publiques

| Situation | Code HTTP | Code applicatif |
| --- | --- | --- |
| Session absente | `401` | `authentication_required` |
| Capacite absente | `403` | `capability_required` |
| Organisation inconnue | `404` | `organization_not_found` |
| Organisation suspendue cote locataire | `403` | `organization_suspended` |
| Transition impossible | `409` | `invalid_organization_transition` |
| Version obsolete | `409` | `organization_version_conflict` |
| Rejeu divergent | `409` | `idempotency_conflict` |
| Raison invalide | `422` | `validation_failed` |
| Audit ou PostgreSQL indisponible | `503` | `service_unavailable` |

Les erreurs ne revelent jamais l'existence d'une organisation hors droits, une politique RLS, une trace SQL ou une
metadonnee refusee.

## 16. Tests backend obligatoires

- migration depuis l'etat 2.4.3 et reconstruction base vide ;
- suspension `active -> suspended` avec version incrementee ;
- reactivation `suspended -> active` avec version incrementee ;
- refus de suspension `provisioning` ;
- refus de suspension deja suspendue et reactivation deja active ;
- conflit de version ;
- idempotence stricte avec `operation_id` ;
- conflit d'idempotence avec contenu divergent ;
- un seul evenement d'audit sur rejeu ;
- rollback si l'audit ne peut pas etre ecrit ;
- blocage des routes locataires apres suspension ;
- blocage Google avant fournisseur apres suspension ;
- changement vers une autre organisation active autorise ;
- historique invitations par etat, curseur et limite ;
- absence de contacts, secrets et donnees Google dans l'audit ;
- `Cache-Control: no-store` sur succes et erreurs pertinentes.

## 17. Tests frontend obligatoires

- affichage des statuts plateforme ;
- action suspendre visible uniquement quand autorisee ;
- action reactiver visible uniquement quand autorisee ;
- confirmation avec raison obligatoire ;
- reference externe validee ;
- gestion conflit de version avec rafraichissement ;
- gestion rejeu ou reponse ambigue sans double intention ;
- organisation suspendue bloquee cote ecrans locataires ;
- filtre invitations `En cours` et `Tout l'historique` ;
- absence d'action sur invitations acceptees, expirees ou revoquees ;
- etats chargement, vide, erreur et succes ;
- navigation clavier, focus restaure, region live ;
- responsive 320 px et zoom 200 % ;
- axe sans violation critique ;
- aucun `operation_id`, curseur ou filtre en stockage Web.

## 18. Recette utilisateur cible

1. Se connecter comme Administrateur de plateforme.
2. Creer ou identifier une organisation active de test.
3. Verifier que l'organisation est utilisable par son administrateur locataire.
4. Suspendre l'organisation avec une raison et une reference de test.
5. Verifier que le statut passe a `suspended`.
6. Tenter une recherche Google avec un membre de cette organisation.
7. Constater le blocage avant tout resultat.
8. Verifier que les ecrans locataires sensibles sont inaccessibles.
9. Reactiver l'organisation depuis la plateforme.
10. Verifier que l'administrateur locataire retrouve l'acces.
11. Verifier que les membres desactives ou invitations terminales n'ont pas change d'etat.
12. Ouvrir l'audit plateforme et constater les deux evenements attendus.
13. Ouvrir la vue invitations et afficher `Tout l'historique`.
14. Confirmer que les invitations terminales sont visibles sans action disponible.

## 19. Critique experte prealable

### 19.1 Risque produit

La suspension peut vite devenir une fonction de facturation implicite. Pour 2.4.4, elle reste administrative et
manuelle. Les plans Freemium, Starter, Business et la suspension automatique doivent attendre le volet facturation.

### 19.2 Risque securite

Le vrai verrou n'est pas le bouton desactive, mais la verification serveur a chaque operation sensible. Les tests
doivent prouver qu'une session ancienne ou un appel direct HTTP ne contourne pas la suspension.

### 19.3 Risque donnees

L'historique des invitations peut donner envie de reconstruire le passe. C'est dangereux et trompeur. Le systeme expose
les etats fiables, et l'audit ne commence qu'a partir de son activation.

## 20. Definition de termine

2.4.4 est termine uniquement si :

- les routes plateforme sont versionnees, idempotentes et auditees ;
- la suspension bloque immediatement locataire et Google ;
- la reactivation ne produit aucune reactivation implicite ;
- l'historique des invitations inclut les etats terminaux sans action dangereuse ;
- l'interface reste accessible et coherente ;
- les tests PostgreSQL reels, API, React et regressions Google sont verts ;
- Ruff, mypy, pytest, ESLint, Vitest, audit npm et build sont verts ;
- une double critique et une revue de code confirment l'absence de rupture avant 2.4.5.

## 21. Decisions proposees a validation

1. Suspension et reactivation reservees au role Administrateur de plateforme.
2. Transitions autorisees uniquement `active -> suspended` et `suspended -> active`.
3. Organisation `provisioning` exclue des routes standard de suspension/reactivation.
4. `version` obligatoire pour chaque mutation plateforme.
5. `operation_id` obligatoire et conserve pour l'idempotence.
6. Rejeu identique sans nouvelle mutation, sans nouvelle version et sans nouvel audit.
7. Rejeu divergent bloque par `409 idempotency_conflict`.
8. Raison obligatoire parmi `customer_request`, `billing`, `security`, `compliance`, `administrative`, `other`.
9. Reference externe optionnelle limitee a 64 caracteres et sans note libre.
10. Suspension bloquant immediatement routes locataires et Google cote serveur.
11. Reactivation sans modification des membres desactives ni invitations terminales.
12. Audit plateforme minimal pour suspension et reactivation, sans donnee sensible.
13. Historique des invitations lu depuis les tables metier, jamais reconstruit depuis l'audit.
14. Filtre invitations `open` par defaut et `all` pour l'historique complet.
15. Interface sans stockage navigateur des filtres, curseurs ou `operation_id`.
16. Passage Azure et deploiement de recette conserves pour le verrou final 2.4.5.

Ces decisions doivent etre validees avant toute modification du code source pour 2.4.4.

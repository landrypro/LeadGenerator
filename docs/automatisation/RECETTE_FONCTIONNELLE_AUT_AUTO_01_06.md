# Recette fonctionnelle — AUT-AUTO-01 à AUT-AUTO-06

## Objet et périmètre

Cette recette vérifie le parcours **Automatisation > Aujourd’hui** : catalogue
fermé, autocomplétion, lecture CRM bornée, états UX, disponibilité effective et
rollout pilote. Toutes les préparations de plan sont en lecture seule : elles ne
créent ni prospect, ni tâche, ni opportunité, ni communication externe.

| Métadonnée | Valeur à renseigner |
| --- | --- |
| Environnement / URL | Recette locale — `http://localhost:5173` |
| Révision Git | `df7163b` (arbre de travail avec modifications non commitées) |
| Date et heure | 7 octobre 2026 — heure non relevée dans les preuves |
| Testeur | Utilisateur `demo2` ; compte Admin de recette utilisé pour les écrans d’administration |
| Organisation pilote | Entreprise Démonstration A ; variante `Entreprise 2 Recette33` en `en-CA` |
| Compte Admin | Admin de recette (identifiant exact non consigné) |
| Compte Sales | `demo2` |
| Navigateur / résolution | Chrome — desktop et mobile 390 × 844 CSS px |
| Verrou qualité | PASS — recette navigateur 4.6 : 44 parcours, axe PASS ; verrou Vite conforme ; verrou qualité local VERT |

## Compte rendu d’exécution — 7 octobre 2026

La recette a été exécutée sur l’environnement local `http://localhost:5173`.
Les captures fournies couvrent les comptes `demo2`/Admin de recette, les vues
française et anglaise, les parcours desktop et mobile, ainsi que les états
Automatisation activée, suspendue et réactivée.

Synthèse au moment de la rédaction : **13 cas PASS confirmés, 1 cas à
confirmer, 1 cas non exécuté**. Aucun effet CRM inattendu, aucune écriture,
aucune tâche et aucune communication externe n’a été observé. Le verrou qualité
est **VERT** ; le rapport navigateur est
`test-results/phase-4-6/browser-axe.json` (44 parcours, axe PASS).

Deux réserves restent tracées :

- l’interface ne permet pas encore d’attribuer un prospect ; les scénarios
  « mes prospects attribués » nécessitent donc une préparation technique de
  `prospects.owner_id` (voir la précondition dédiée) ;
- AUTO-11 a confirmé la disparition de la suggestion Sales, mais le résultat
  complet de la demande forcée doit encore être joint pour le déclarer PASS ;
  AUTO-15 (hors pilote) n’a pas encore été exécuté.

## Préconditions

1. L’API et le client sont démarrés ; `GET /api/health/ready` répond `200`.
2. Utiliser une organisation de recette dont Automatisation est activée depuis
   **Administration > Automatisation**.
3. Pour le parcours Assistant, utiliser un environnement `development` ou
   `test`, avec `AUTOMATION_ENABLED=true`, `AUTOMATION_ASSISTANT_ENABLED=true`,
   `AUTOMATION_ASSISTANT_PROVIDER=fake` et un rollout incluant l’organisation.
4. Préparer deux comptes actifs de cette organisation : un `ADMIN` et un
   `SALES`. Ne jamais noter de mot de passe, cookie ou jeton dans la preuve.
5. Relever avant le premier plan le nombre de prospects, tâches et opportunités
   affichés dans le CRM ou l’audit. Ils serviront à constater l’absence d’effet.

> **Précondition d’attribution :** l’interface actuelle ne propose pas encore de
> formulaire « Attribuer un prospect ». Les cas portant sur « mes prospects
> attribués » (`AUTO-03` et les variantes similaires) nécessitent donc une
> attribution préparée techniquement par pré-seed ou PATCH contrôlé du champ
> `prospects.owner_id`. Sans cette préparation, un résultat `0` est attendu même
> si le total organisationnel des prospects ouverts est supérieur à zéro. Cette
> réserve est suivie séparément et ne doit pas être contournée pendant la recette.

> Si l’assistant est volontairement fermé en staging/production, exécuter
> `AUTO-09` et `AUTO-10`, puis consigner les autres cas Assistant comme **N/A —
> assistant fermé par politique IMP-A5**. Ne pas contourner cette politique.

## Cas de recette

| ID | Priorité | Étapes | Résultat attendu | Preuve minimale | Statut |
| --- | --- | --- | --- | --- | --- |
| AUTO-01 | P0 | Se connecter avec l’Admin pilote ; ouvrir **Automatisation > Aujourd’hui**. | Le titre, le champ « Votre demande », les suggestions guidées et les données CRM sont visibles. | Capture sans secret. | PASS |
| AUTO-02 | P0 | Saisir la seule lettre `p` ; naviguer dans les propositions avec ↓, ↑, Entrée ; ne pas cliquer Préparer. | Les propositions correspondantes apparaissent dès cette lettre ; la sélection est insérée dans le champ, sans plan ni écriture avant soumission explicite. | Capture avant/après. | PASS |
| AUTO-03 | P0 | Saisir ou sélectionner « Montre-moi les prospects ouverts », puis **Préparer un plan**. | Un plan en lecture seule affiche explicitement le périmètre « prospects ouverts qui vous sont attribués », son compteur, les garde-fous et au plus cinq éléments CRM. Un résultat à zéro est valide si le membre actif n’a aucun prospect ouvert attribué ; le total organisationnel visible dans les données CRM ne doit pas être confondu avec ce périmètre. | Capture du plan et de son périmètre. | PASS |
| AUTO-04 | P1 | Choisir une demande dont le périmètre autorisé ne contient aucun prospect, par exemple avec un compte Sales sans prospect nouveau ; préparer le plan. | État « Aucun élément CRM trouvé » explicite, sans écran vide ni erreur technique. | Capture de l’état vide. | PASS |
| AUTO-05 | P1 | Saisir une demande ambiguë, par exemple `aide`; préparer. | Une clarification explique quoi saisir et propose une suite guidée ; aucun effet métier. | Capture. | PASS |
| AUTO-06 | P0 | Saisir `supprime mes prospects` ; préparer. | Refus explicite, sans suppression ni création. | Capture et contrôle CRM inchangé. | PASS |
| AUTO-07 | P1 | Saisir `statut automatisation`, choisir l’autocomplétion puis préparer. | Un bloc « État actuel de l’automatisation » indique que l’automatisation est active pour l’organisation active, que l’assistant prépare des plans en lecture seule et qu’aucune écriture CRM, tâche ou communication externe n’est effectuée ; aucune liste CRM n’est requise. | Capture du bloc d’état. | PASS |
| AUTO-08 | P0 | Relever de nouveau les compteurs CRM/audit préparés en précondition après AUTO-03 à AUTO-07. | Prospects, tâches, opportunités et communications sont inchangés ; aucune création cachée. | Captures ou entrée audit. | PASS |
| AUTO-09 | P0 | Depuis **Administration > Automatisation**, désactiver Automatisation pour l’organisation de recette ; recharger Aujourd’hui puis essayer l’URL directe. | Le menu **Automatisation** disparaît de la navigation ; l’URL directe `/app/automation/today` renvoie **403 — Accès non autorisé** ; l’espace Administration reste accessible pour réactiver. Aucune donnée CRM n’est modifiée. | Capture du menu masqué et de la page 403. | PASS |
| AUTO-10 | P0 | Réactiver Automatisation dans Administration, actualiser puis retourner sur Aujourd’hui. | Le menu **Automatisation** réapparaît et la commande Assistant ainsi que les suggestions reviennent pour l’organisation pilote. | Capture avant/après et lien Administration. | PASS |
| AUTO-11 | P1 | Avec le compte Sales, ouvrir Aujourd’hui et rechercher `rééquilibrage`. Puis saisir librement la demande et cliquer **Préparer un plan**. | Le rééquilibrage organisationnel n’est pas proposé au Sales. Une demande forcée reçoit le résultat applicatif `intent_not_supported` avec un refus explicite, sans plan ni écriture CRM. Une HTTP 403 n’est attendue que pour une route ou une capacité non autorisée, pas pour cette intention refusée dans le plan Assistant. | Capture de l’absence du bouton et du refus. | À CONFIRMER — suggestion masquée ; refus forcé non joint |
| AUTO-12 | P1 | Avec l’Admin, rechercher `rééquilibrage` et préparer la demande. | La proposition est visible et son plan est limité à une revue, sans réattribution réelle. | Capture. | PASS |
| AUTO-13 | P1 | À 390 × 844 CSS px, rejouer AUTO-02 et AUTO-06 au clavier et au toucher. | Pas de défilement horizontal ; suggestions et messages restent lisibles ; Échap ferme la liste. | Capture mobile. | PASS |
| AUTO-14 | P1 | Rejouer AUTO-01, AUTO-03, AUTO-06 et AUTO-09 en `en-CA`. | Libellés et états explicites sont traduits ; les garde-fous restent identiques. | Capture en anglais. | PASS |

## Contrôle du rollout pilote

Exécuter uniquement sur un environnement de développement/test contrôlé.

1. Configurer `AUTOMATION_ROLLOUT_MODE=pilot` et placer uniquement l’UUID de
   l’organisation de recette dans `AUTOMATION_PILOT_ORGANIZATION_IDS`.
2. Redémarrer/recharger l’API, se reconnecter, puis exécuter AUTO-01 à AUTO-03
   dans l’organisation pilote : ils doivent réussir.
3. Basculer vers une organisation active hors pilote : la surface de préparation
   n’est pas disponible et `GET /api/automation/suggestions` doit retourner
   `409 automation_assistant_disabled`.
4. Revenir en pilote, puis restaurer la configuration de rollout prévue pour
   l’environnement.

| ID | Résultat pilote | Résultat hors pilote | Preuve | Statut |
| --- | --- | --- | --- | --- |
| AUTO-15 | Assistant utilisable | Préparation et suggestions refusées proprement | configuration assainie + captures/réponses | À EXÉCUTER |

## Règles de décision

- **PASS** : tous les résultats attendus sont observés et la preuve est jointe.
- **FAIL** : un effet métier apparaît, une donnée d’une autre organisation est
  visible, une capacité est contournable ou l’état reste ambigu.
- **BLOCKED** : prérequis technique indisponible ; inclure le message et la
  cause, sans marquer PASS.
- **N/A** : uniquement si l’assistant est fermé par politique d’environnement,
  avec cette justification explicite.

Tout effet CRM inattendu, franchissement d’organisation ou contournement de rôle
est une anomalie bloquante et impose un **NO-GO**.

## Registre d’exécution

| ID | PASS / FAIL / BLOCKED / N/A | Date/heure | Testeur | Preuve | Anomalie / commentaire |
| --- | --- | --- | --- | --- | --- |
| AUTO-01 à AUTO-10 | PASS | 2026-10-07 | demo2 / Admin recette | Captures navigateur fournies | Parcours confirmés ; aucun effet CRM observé. |
| AUTO-11 | À CONFIRMER | 2026-10-07 | demo2 / Sales recette | Capture de la suggestion masquée | Ajouter la réponse du clic forcé (`intent_not_supported`) avant clôture. |
| AUTO-12 à AUTO-14 | PASS | 2026-10-07 | demo2 / Admin recette | Captures navigateur desktop, mobile et `en-CA` | Responsive, traduction et garde-fous conformes. |
| AUTO-15 | À EXÉCUTER | — | — | — | Contrôle du rollout pilote hors organisation à réaliser. |

## Décision

| Élément | Valeur |
| --- | --- |
| Cas P0 PASS | 7 / 7 |
| Cas P1 PASS | 6 / 8 (AUTO-11 à confirmer, AUTO-15 à exécuter) |
| Défauts bloquants / majeurs ouverts | 0 observé ; 2 actions de clôture restantes |
| Verrou qualité local | VERT — navigateur 4.6 axe PASS (44 parcours), artefact Vite conforme |
| Décision | GO avec réserves — clôture finale après AUTO-11 forcé et AUTO-15 |

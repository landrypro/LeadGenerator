# AUT-AUTO-06 — Rapport de recette et activation progressive

## Objet

Ce document clôt la recette de l’autocomplétion Automation et de ses résultats
CRM bornés. Le périmètre reste en lecture seule : aucun plan ne crée une tâche,
ne modifie le pipeline et ne déclenche une communication externe.

La recette manuelle exécutable, avec les statuts à renseigner, est disponible
dans [RECETTE_FONCTIONNELLE_AUT_AUTO_01_06.md](RECETTE_FONCTIONNELLE_AUT_AUTO_01_06.md).

## Résultat de la recette locale

| Axe | Contrôle | Résultat |
|---|---|---|
| Backend | `pytest -q tests/test_settings.py tests/test_automation_api.py tests/test_automation_assistant.py tests/test_automation_read_api.py` | **PASS — 55 tests** |
| Frontend ciblé | `vitest run src/features/automation/AutomationTodayPage.test.jsx src/features/automation/AutomationTodayPageAccessibility.test.jsx` | **PASS — 14 tests** |
| Frontend complet | `npm run test:ci` | **PASS — 242 tests / 52 fichiers** |
| Lint ciblé | ESLint sur la page, ses tests et le test axe | **PASS** |
| Artefact | `npm run build` | **PASS — Vite** |
| Axe/jsdom | CRM chargé, plan avec éléments, clarification en anglais | **PASS — aucune violation** |
| Navigateur desktop/mobile | `scripts/automation_auto06_browser.mjs` | **Prêt à exécuter ; dépend du chemin Playwright fourni par l’hôte** |
| Verrou qualité complet | `scripts\Test-QualityGateLocal.ps1` | **Non exécuté : démon Docker Windows indisponible, et le service WSL est désactivé** |

Le test d’accessibilité a détecté puis corrigé un défaut réel : le champ
multiligne déclarait à tort le rôle ARIA `combobox`. Il reste une zone de texte
redimensionnable, avec une relation `aria-controls` uniquement lorsque la liste
de suggestions existe.

## Parcours navigateur AUT-AUTO-06

Le script `scripts/automation_auto06_browser.mjs` intercepte les routes API avec
des données déterministes et refuse toute écriture non prévue. Il contrôle :

1. bureau fr-CA : CRM en direct, plan avec élément CRM et absence d’écriture ;
2. bureau fr-CA : clarification et prochaine suggestion guidée ;
3. mobile 390×844 : autocomplétion clavier, absence de débordement horizontal ;
4. mobile fr-CA : demande non supportée et message explicite ;
5. mobile en-CA : même refus avec libellés anglais ;
6. axe WCAG 2A/2AA sur chaque état.

Exécution depuis la racine du dépôt, après `npm run build` et `npm run preview`
dans `client` :

```powershell
node scripts\automation_auto06_browser.mjs <chemin-vers-playwright> http://127.0.0.1:4178
```

Le rapport JSON est écrit dans
`test-results/aut-auto-06/browser-report.json` (ou dans le chemin indiqué par
`AUT_AUTO06_BROWSER_REPORT`). Dans l’environnement de développement actuel,
Playwright n’est pas installé localement ; le contrôle navigateur doit donc être
lancé sur le poste de recette qui fournit ce binaire. Cette absence ne masque pas
un succès : le script sort explicitement `PASS` ou `FAIL` et conserve la preuve.

Le verrou qualité complet a été tenté le 7 octobre 2026. Il s’est arrêté avant
les tests, car `docker.exe` visait le pipe Docker Desktop absent et `wsl.exe
--list --quiet` indiquait que le service WSL ne pouvait pas démarrer. Une fois
Docker/WSL rétabli, relancer le verrou sans modifier le code :

```powershell
.\scripts\Test-QualityGateLocal.ps1
```

## Activation progressive

### 1. Valeur sûre — arrêt

```dotenv
AUTOMATION_ENABLED=false
AUTOMATION_ROLLOUT_MODE=off
AUTOMATION_PILOT_ORGANIZATION_IDS=
AUTOMATION_ASSISTANT_ENABLED=false
AUTOMATION_ASSISTANT_PROVIDER=fake
```

Après modification de l’environnement, redémarrer/recharger l’API puis vérifier
`GET /api/health/ready` et `GET /api/automation/availability`.

### 2. Pilote unique

Choisir une organisation de recette et utiliser son UUID, sans ouvrir le mode
global :

```dotenv
AUTOMATION_ENABLED=true
AUTOMATION_ROLLOUT_MODE=pilot
AUTOMATION_PILOT_ORGANIZATION_IDS=<uuid-pilote>
AUTOMATION_ASSISTANT_ENABLED=true       # développement/test uniquement
AUTOMATION_ASSISTANT_PROVIDER=fake
```

L’organisation doit aussi avoir son verrou de données activé dans Administration.
Le serveur recalcule l’accès à chaque requête : l’organisation hors liste reçoit
`effective_enabled=false`, les suggestions sont refusées et les plans retournent
`automation_assistant_disabled`. Le navigateur ne peut pas contourner cette
sélection.

Checklist pilote :

- `/api/automation/availability` expose `global_enabled`, `rollout_enabled` et
  `effective_enabled` cohérents ;
- Aujourd’hui affiche les compteurs et priorités de l’organisation active ;
- une phrase canonique produit un plan borné ;
- une demande inconnue ou interdite reste explicite et sans écriture ;
- Prévol/activation/suspension sont refusés hors pilote et autorisés uniquement
  avec les capacités et garde-fous attendus dans le pilote ;
- `GET /api/automation/availability` retourne `assistant_available=false` lorsque
  l’assistant, le rollout ou l’interrupteur organisationnel est désactivé ; dans
  ce cas, l’écran Aujourd’hui n’affiche pas de commande de préparation et
  `GET /api/automation/suggestions` retourne `automation_assistant_disabled` ;
- chaque code retourné par `GET /api/automation/suggestions` est accepté par
  `POST /api/automation/intent-plans` en mode `guided`.
- logs, métriques et audit ne contiennent pas le texte de demande ni de PII.

### 3. Élargissement contrôlé

Ajouter les UUID un par un à `AUTOMATION_PILOT_ORGANIZATION_IDS`, redémarrer ou
recharger l’API, puis rejouer la checklist. Passer à
`AUTOMATION_ROLLOUT_MODE=all` seulement après validation Produit, QA, sécurité et
données. En staging/production, l’assistant reste fermé par la validation de
configuration (`AUTOMATION_ASSISTANT_ENABLED=false`) et le fournisseur autorisé
reste `fake` pour cette version.

## Rollback

Le rollback ne demande aucune migration destructive et conserve les audits.

1. positionner `AUTOMATION_ENABLED=false` et `AUTOMATION_ROLLOUT_MODE=off` ;
2. vider `AUTOMATION_PILOT_ORGANIZATION_IDS` et redémarrer/recharger l’API ;
3. vérifier `effective_enabled=false`, l’absence de suggestions et le refus des
   nouveaux plans, Prévols et transitions de Playbook ;
4. suspendre les Playbooks actifs avec le motif versionné `rollback` si une
   remédiation est nécessaire ;
5. contrôler les métriques et l’audit avec le `request_id` de l’opération ;
6. conserver Prévols, exceptions, transitions et audits pour analyse d’incident.

Le garde-serveur de rollout est appliqué aux suggestions, à la préparation de
plan, au Prévol et aux transitions de cycle de vie. Un mode `all` ne peut donc
pas réactiver ces commandes lorsque le coupe-circuit global est à `false`.

## Décision

**AUT-AUTO-06 est prêt pour une activation pilote après exécution du parcours
navigateur sur un hôte équipé de Playwright.** L’élargissement n’est pas implicite
et le retour à l’arrêt global est réversible et vérifiable.

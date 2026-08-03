# Phase 2.3.5-E — Rapport d’implémentation du verrou qualité final

| Métadonnée | Valeur |
| --- | --- |
| Produit | Prospect CRM |
| Date | 3 août 2026 |
| État du code | Implémenté et vérifié hors infrastructure |
| Référence Git de départ | `511129a93f140368eeedf6512d5d19fbc20db211` |
| Révision finale | À renseigner après commit des changements 2.3.5-D/E |
| Décision actuelle | **No-Go temporaire pour 2.4** |
| Motif du No-Go | Docker, passage Azure et matrice manuelle restent à exécuter sur la révision finale |

## 1. Résultat livré

Le lot E ajoute un verrou reproductible sans modifier les API métier, les migrations ou les limites Google :

- `axe-core` intégré directement à la suite Vitest ;
- vingt états représentatifs contrôlés par axe, avec le contraste réservé au contrôle visuel réel ;
- libellés de formulaires, onglets clavier, annonces d’erreur et piège de focus renforcés sans changement visuel intentionnel ;
- contrôle déterministe des rapports JUnit pour refuser tout test ignoré ;
- détection statique des stockages Web, journaux de débogage et tests focalisés/ignorés ;
- contrôle de `dist` et de l’artefact Azure final contre secrets, caches, bases et fichiers temporaires ;
- script PowerShell unique démarrant une composition de test isolée et la supprimant systématiquement ;
- pipeline Azure aligné sur Ruff, mypy, migrations, pytest réel, zéro `skip`, audit npm, ESLint, Vitest/axe, build et contrôle d’artefact ;
- `undici` verrouillé à `7.29.0` afin de fermer l’alerte de sécurité transitive remontée par `npm audit`.

## 2. Preuves automatisées collectées

Environnement de cette exécution : Python 3.14.6, Node.js 22.18.0. La CI reste fixée à Python 3.12 et Node.js 22.x.
Les images prévues sont PostgreSQL 17.10 Alpine, Redis 7.4.9 Alpine et Mailpit 1.30.5.

| Barrière | Résultat |
| --- | --- |
| Ruff | Vert |
| Format Ruff | 144 fichiers conformes |
| mypy | 110 fichiers, aucune erreur |
| pytest sans infrastructure | 153 collectés, 136 réussis, 17 ignorés car services réels absents |
| Tests du harnais qualité | 3 réussis |
| ESLint | Vert, zéro avertissement |
| Vitest | 29 fichiers, 126 tests réussis, zéro ignoré |
| axe | 20 états intégrés à Vitest, zéro violation détectée hors contraste |
| `npm audit --audit-level=high` | 0 vulnérabilité |
| `npm ci` isolé depuis le lockfile | 216 paquets installés, audit de 217 paquets, zéro vulnérabilité |
| Build Vite | Vert, 70 modules transformés |
| Rapport JUnit frontend | Zéro test ignoré |
| Sources navigateur | Conforme |
| Artefact `client/dist` | Conforme, aucune clé Google détectée |
| `git diff --check` | Vert ; seuls les avertissements de conversion LF/CRLF Windows subsistent |

Le passage pytest ci-dessus ne constitue pas la preuve d’infrastructure exigée : les 17 scénarios ont été ignorés
par conception parce que `REQUIRE_INFRASTRUCTURE_TESTS` n’était pas activé sans Docker. Le verrou final devra les
exécuter avec ce drapeau et refuser tout `skip`.

## 3. Écarts corrigés pendant E

1. Les libellés du type d’entreprise, du rayon et du filtre de résultats n’étaient pas tous reliés à leur contrôle.
2. Les onglets Membres/Invitations ne possédaient ni roving tabindex ni navigation Flèches/Home/End.
3. Les erreurs étaient annoncées, mais ne recevaient pas systématiquement le focus lors de leur apparition.
4. Le dialogue pouvait perdre son piège de focus lorsque ses deux actions devenaient désactivées pendant une requête.
5. Les tests axe manquaient aux parcours d’administration et d’invitation.
6. La pipeline ne refusait pas explicitement un rapport JUnit contenant des tests ignorés.
7. L’artefact Azure final pouvait inclure des caches Python produits pendant les tests.
8. L’audit npm a détecté `undici 7.28.0`; le lockfile impose désormais la version corrigée 7.29.0.
9. La suite axe complète devenait sensible à la contention; Vitest utilise deux workers et un délai asynchrone de
   trois secondes, sans retrait d’assertion ni relance automatique.

## 4. Trois critiques — deux passages chacune

### Critique 1 — Sécurité et isolation locataire

**Premier passage.** Aucun changement E ne touche l’autorité serveur, les capacités, RLS, CSRF ou la session. Le
contrôle initial de l’artefact portait néanmoins uniquement sur `client/dist`, ce qui laissait l’assemblage final
Azure insuffisamment contrôlé.

**Correction et second passage.** La pipeline exclut explicitement caches, bytecode, dépendances et résultats de test,
puis analyse le dossier final avant publication. Les contrôles statiques navigateur et `dist` sont verts. Aucun défaut
bloquant n’est constaté dans le code E. La preuve RLS réelle reste toutefois non acquise tant que les 17 tests Docker
n’ont pas tourné : le lot conserve donc un No-Go temporaire.

### Critique 2 — Fiabilité et reproductibilité

**Premier passage.** L’ajout d’axe a exposé deux dépassements du délai Testing Library historique sous forte
concurrence. L’installation propre `npm ci` ne peut pas remplacer le binaire Rolldown pendant qu’un serveur Vite local
l’utilise. Docker Desktop n’expose actuellement aucun moteur au client.

**Correction et second passage.** Le parallélisme est borné à deux workers et la campagne complète est verte en une
seule exécution de 126 tests. Le script local utilise un projet Compose isolé, nettoie ses volumes dans `finally` et
rejoue migrations et contrôles dans l’ordre de la CI. Le lockfile, l’installation incrémentale et l’audit sont verts.
Pour la preuve finale, il faudra arrêter les serveurs Vite avant `npm ci`, rendre Docker disponible et exécuter le
script complet puis Azure. Aucun retry caché ou test affaibli n’a été introduit.

### Critique 3 — Accessibilité et usage réel

**Premier passage.** Les formulaires de recherche, les onglets et les erreurs présentaient des lacunes de relation ou
de focus. Un dialogue occupé constituait un cas limite de sortie du focus. La couverture axe ne représentait pas les
lectures seules ni la révocation plateforme.

**Correction et second passage.** Les contrôles natifs sont nommés, les onglets suivent le modèle clavier, les erreurs
sont annoncées et focalisées, et le dialogue conserve le focus même occupé. Vingt états axe passent sans violation.
La règle de contraste est désactivée uniquement dans jsdom, qui ne calcule pas les couleurs peintes. Le contraste,
320 × 568, le zoom 200 % et la lecture réelle au clavier restent donc des barrières manuelles obligatoires. Aucun
défaut bloquant automatisé n’est constaté, mais la validation d’usage n’est pas encore signée.

Un contrôle navigateur préliminaire de la page Connexion à 320 × 568 confirme une largeur rendue de 320 px pour une
largeur de document de 320 px, sans défilement horizontal ni erreur console. Cette preuve ciblée ne signe pas la
matrice responsive de toutes les routes.

## 5. Deux revues de code

### Revue A — Architecture et maintenabilité

Le moteur axe est isolé dans un adaptateur de test. `ErrorBanner` centralise une responsabilité d’interface précise,
sans déplacer de règle métier dans React. Le harnais Python ne dépend pas de FastAPI et le script PowerShell orchestre
les outils sans connaître les secrets de développement. Les limites de workers augmentent le temps de la suite mais
la rendent déterministe. Conclusion : **aucun défaut bloquant d’architecture ou de maintenabilité dans E**.

### Revue B — Sécurité, exploitation et conformité

La CI n’injecte aucune clé Google et garde les fournisseurs simulés. Les limites Google existantes, l’absence de
stockage navigateur, l’export inaccessible et les réponses `no-store` restent couverts par les suites existantes. Le
contrôle final d’artefact précède désormais sa publication. L’audit npm est vert. Conclusion code : **aucun défaut
bloquant identifié**. Conclusion exploitation : **No-Go temporaire** jusqu’aux preuves Docker, Azure et manuelles.

## 6. Validation locale restante

Fermer d’abord les serveurs Vite afin que `npm ci` puisse remplacer les binaires natifs, puis exécuter depuis la racine :

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test-QualityGateLocal.ps1
```

Le résultat attendu est : migrations jusqu’à `20260802_0005 (head)`, 153 tests pytest réussis avec zéro `skip`, 126
tests Vitest réussis avec zéro `skip`, puis `Verrou qualité local 2.3.5-E : VERT`.

## 7. Matrice manuelle à signer

| Contrôle | Résultat | Validé par/date |
| --- | --- | --- |
| Clavier complet et lien d’évitement | À faire | — |
| 320 × 568 à 100 % | À faire | — |
| 1280 × 720 à 200 % | À faire | — |
| Contraste WCAG 2.2 AA, états compris | À faire | — |
| Sans organisation/Sales/Manager/Admin | À faire | — |
| Plateforme sans/avec appartenance | À faire | — |
| Changement multi-organisation et purge | À faire | — |
| Un Text Search et une Maps Static réels maximum | À faire | — |
| Attribution Google Maps visible | À faire | — |

## 8. Conditions de levée du No-Go

1. Exécuter le verrou local complet avec Docker et obtenir zéro test ignoré.
2. Arrêter les serveurs Vite avant le passage afin de prouver `npm ci` depuis le lockfile.
3. Exécuter Azure Pipelines sur la même révision finale et conserver son identifiant de passage vert.
4. Compléter et signer la matrice manuelle ci-dessus.
5. Renseigner la révision Git finale et donner explicitement le Go produit pour 2.4.

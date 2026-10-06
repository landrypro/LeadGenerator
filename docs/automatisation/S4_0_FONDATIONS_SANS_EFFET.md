# S4-0 — Fondations sans effet

> **Statut : CLÔTURÉE pour préparation — preuves statiques validées ; intégration `P4-Lite` autorisée sous flags désactivés**  
> **Date d’ouverture :** 1er octobre 2026  
> **Parent :** [Étape 4 — Plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md)  
> **Référence :** items `AUT-4001` à `AUT-4007` du [backlog `BL-AUT-4.1`](./BACKLOG_DETAILLE_ETAPE_4.md)

La décision de revue est consignée dans la [contre-validation S4-0](./CONTRE_VALIDATION_S4_0.md).
Les artefacts produits sont regroupés dans [S4-0 — Livrables réalisés](./S4_0_LIVRABLES_FONDATIONS.md).

## 1. Décision d’ouverture

Le GO utilisateur ouvre S4-0 pour préparer les fondations de l’Automatisation sans produire d’effet sur le CRM.

Cette décision autorise :

- la clarification des constantes V2.1 et des versions ;
- la conception des flags, capacités, événements, métriques et migrations ;
- la préparation de fixtures synthétiques et de tests hors production ;
- la rédaction des procédures d’arrêt, de rollback et de réconciliation ;
- la production de spécifications D1 et, lorsqu’un environnement isolé sera disponible, de premiers artefacts D2.

Cette décision n’autorise pas :

- le branchement du worker Automation au worker actif ;
- une migration appliquée aux données client ;
- une écriture dans les objets CRM ;
- un appel à un fournisseur IA avec des données réelles ;
- un envoi externe ou une communication automatique ;
- un déploiement de production.

## 2. Résultats attendus

À la fin de S4-0, l’équipe doit pouvoir répondre sans ambiguïté à sept questions :

1. Quelle version fonctionnelle et quelles règles sont évaluées ?
2. Comment désactiver l’Automatisation au niveau global, organisation et Playbook ?
3. Quel rôle peut demander, préparer, approuver ou résoudre une action ?
4. Dans quelles conditions le principal technique `automation-system` peut-il exister ?
5. Quelles tables isolées et quelles politiques RLS seront créées, et comment revenir en arrière ?
6. Quel événement permet de reconstruire chaque décision sans conserver la phrase libre ?
7. Quelles métriques sont utiles sans créer de cardinalité excessive ni exposer de PII ?

## 3. Périmètre de travail

| ID | Chantier | Livrable de préparation | Critère de sortie S4-0 | Preuve cible |
|---|---|---|---|---|
| `AUT-4001` | Constantes et versions V2.1 | Table comportement → règle → version → owner | Toute règle du noyau Lite est identifiée et versionnable | `PV-DES-01` |
| `AUT-4002` | Flags global, organisation, Playbook | Matrice de priorité, valeurs sûres et motifs d’arrêt | Une désactivation côté serveur est définie et non contournable par l’UI | `PV-OPS-01` |
| `AUT-4003` | Capabilities par rôle | Matrice rôle × commande × objet × résultat attendu | Aucun droit implicite ; révocation documentée | `PV-SEC-01` |
| `AUT-4004` | Principal `automation-system` | Origines autorisées, portée, TTL, audit et refus | Aucun `system_origin` générique ou illimité n’est accepté | `PV-SEC-02` |
| `AUT-4005` | Migrations et rollback | Schéma isolé, ordre, garde RLS, script de retour et réconciliation | Le retour arrière est testable sans toucher aux objets CRM | `PV-DATA-01` |
| `AUT-4006` | Corrélation, événements, audit | Catalogue des commandes, identifiants et événements terminaux | Chaque commande possède une décision et une fin traçable | `PV-AUD-01` |
| `AUT-4007` | Métriques et cardinalité | Nomenclature métrique, labels autorisés, rétention et seuils | Aucune phrase libre ou PII dans les labels | `PV-OBS-01` |

## 4. Garde-fous d’exécution

Toute activité S4-0 doit respecter les règles suivantes :

- **branche et environnement isolés** pour toute commande, migration ou test ;
- **données synthétiques uniquement**, avec au moins deux organisations et des cas ambigus ;
- **mode Préparer** maintenu ; aucune commande ne doit produire un effet CRM ;
- **flags désactivés par défaut** au niveau global et organisation ;
- **aucun secret ou identifiant de fournisseur IA réel** dans les fixtures ;
- **audit minimal et non sensible** : identifiant de décision, version, acteur, résultat et raison structurée ;
- **arrêt immédiat** si une tâche modifie le périmètre V2.1 ou fait apparaître une dépendance non documentée ;
- toute modification matérielle doit suivre une fiche de changement et, si nécessaire, une nouvelle version de `RF-AUT`.

## 5. Critères de préparation (DoR)

S4-0 est considérée prête à être exécutée lorsque :

- un responsable Produit, un responsable Ingénierie, un responsable QA et un responsable Sécurité sont nommés ;
- l’environnement isolé et la branche de travail sont identifiés ;
- les fixtures synthétiques sont décrites et leur absence de PII confirmée ;
- les ADR T2/T3 et la référence `RF-AUT-2.1` sont accessibles ;
- les procédures d’arrêt et de retour arrière ont un propriétaire ;
- aucune dépendance bloquante n’est masquée dans le backlog.

## 6. Critères de finition (DoD)

S4-0 pourra être soumise à revue lorsque :

- les sept items `AUT-4001` à `AUT-4007` ont un livrable versionné ;
- chaque livrable est relié à une preuve `PV-*` et à un oracle ;
- les flags et la suspension ont été vérifiés dans l’environnement isolé ;
- le schéma de migration est réversible sur une base de test ;
- la matrice de capabilities inclut les refus fermés et la révocation ;
- la nomenclature d’audit et de métriques ne contient ni phrase libre ni PII ;
- les écarts sont inscrits dans le registre des risques ;
- le dossier de [Porte 4](./PORTE_4_PRET_A_CONSTRUIRE.md) est mis à jour sans transformer D1 en D2/D3/D4.

## 7. État initial et prochaine décision

| Élément | État au démarrage |
|---|---|
| Autorisation S4-0 | Accordée par le commanditaire |
| Items de backlog | Définis (`AUT-4001` à `AUT-4007`) |
| Preuves | D1 spécifiées ; D2 à produire seulement en environnement isolé |
| Code Automation actif | Interdit |
| Effets CRM / envois | Interdits |
| Porte 4 | `GO avec réserves` ; intégration `P4-Lite` sous flags désactivés |
| Réalisation statique | Effectuée ; preuve D2 artefact PASS |
| Contre-validation S4-0 | Clôturée pour préparation ; preuves runtime restantes avant Porte 4 |
| Prochaine revue | Contre-validation S4-7 puis nouvelle revue de Porte 4 |

Le GO utilisateur du 1er octobre 2026 autorise désormais la définition de [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md), sans autoriser son exécution runtime.

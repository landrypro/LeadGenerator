# Recette — Correction Automatisation V2.1

> **Statut : AUT-COR-01 à AUT-COR-08 à exécuter**  
> **Référence de cadrage :** [Correction d’écart Automatisation](./CORRECTION_ECART_AUTOMATISATION_PROTOTYPE_V2_1.md)  
> **Jeu de données :** organisation synthétique isolée, comptes Sales, Gestionnaire, Administrateur et Plateforme.

Le verrou qualité local est **VERT** (44 parcours navigateur, axe conforme,
artefact Vite et sources conformes). La feuille d’exécution, les gabarits de
preuves et le sign-off sont dans
[RECETTE_EXECUTION_AUT_COR_01_07.md](./RECETTE_EXECUTION_AUT_COR_01_07.md).

## Préconditions

- les flags d’interface, lecture, Prévol et commandes sont documentés et observables ;
- un Playbook de test possède une version et une configuration synthétique ;
- les preuves d’audit et de télémétrie sont accessibles aux testeurs autorisés ;
- aucun connecteur de communication externe n’est actif.

| ID | Parcours | Résultat attendu |
|---|---|---|
| `AUT-COR-R01` | Ouvrir `/app/automation/today` | Aujourd’hui est actif ; assistant et limite V1 sont explicites ; aucune seconde zone de saisie libre ailleurs. |
| `AUT-COR-R02` | Parcourir les trois entrées desktop | Aujourd’hui, Playbooks et Entrées et exceptions affichent titre, fil d’Ariane et état actif cohérents. |
| `AUT-COR-R03` | Ouvrir le tiroir Automatisation au mobile | Fond inerte, focus piégé, fermeture Échap/hors panneau/route et retour focus corrects. |
| `AUT-COR-R04` | Ouvrir Playbooks sans configuration | Les trois cartes sont présentes, disent ce qui est indisponible et ne montrent ni interrupteur ni compteur fictif. |
| `AUT-COR-R05` | Ouvrir Exceptions sans donnée | État vide honnête ; il ne ressemble pas à une erreur de chargement. |
| `AUT-COR-R06` | Simuler une indisponibilité du service de lecture | Message récupérable visible ; aucun faux « aucune exception ». |
| `AUT-COR-R07` | Se connecter comme Sales | Pas de commande de configuration/activation/suspension ; lecture limitée au périmètre autorisé. |
| `AUT-COR-R08` | Se connecter comme Gestionnaire ou Administrateur | Les commandes deviennent visibles uniquement si la capacité et le flag sont effectivement accordés. |
| `AUT-COR-R09` | Appeler une route d’une autre organisation ou forger `organization_id` | `403`/`404` sans fuite de données ; organisation résolue côté serveur. |
| `AUT-COR-R09a` | Appeler les lectures avec `limit`, `cursor`, `state` ou un paramètre inconnu invalide | Réponse `422` explicable et `Cache-Control: no-store`; aucun repli en état vide côté interface. |
| `AUT-COR-R09b` | Ouvrir Playbooks comme Sales puis comme Gestionnaire | Sales voit le catalogue sans état/version/Prévol de l’organisation ; Gestionnaire voit les projections d’organisation autorisées. |
| `AUT-COR-R09c` | Gestionnaire : lancer un Prévol sur une configuration synthétique valide, puis rejouer la même clé | Prévol de configuration persisté, expirant et rejoué de façon idempotente ; `0` sujet / aucune décision CRM ; audit présent ; zéro prospect, tâche, job, brouillon, message ou transition créé. |
| `AUT-COR-R10` | Lancer un Prévol sur fixture admissible | Prévol versionné et expirant créé ; zéro tâche, prospect, modification pipeline ou communication externe. |
| `AUT-COR-R11` | Modifier règle, snapshot, capacité ou suspension après Prévol | Prévol marqué obsolète ; activation refusée ; nouvelle évaluation imposée. |
| `AUT-COR-R12` | Tenter d’activer avec le Prévol AUT-COR-04 actuel (`0` sujet) ; puis, lorsqu’un fixture complet existe, activer avec Prévol frais | Le premier appel est refusé (`409`) sans effet. Le second seulement peut atteindre `actif — préparer`, avec audit et zéro effet CRM/externe pendant la commande. |
| `AUT-COR-R13` | Suspendre un Playbook actif avec `If-Match`, motif fermé et clé d’idempotence ; rejouer la même commande | Suspension prioritaire, `prepare_enabled=false`, génération augmentée, audit et rejeu idempotent ; aucun travail ultérieur ne passe la garde fraîche. |
| `AUT-COR-R14` | Reprendre un Playbook suspendu avec `If-Match` | Retour à `prévol requis`, sans reprise implicite ni activation ; nouveau Prévol complet imposé. |
| `AUT-COR-R15` | Prendre en charge une exception ouverte `owner_unavailable`, puis la résoudre avec un code fermé | Passage à `en traitement`, puis `résolue`, version et audit présents ; aucune réattribution automatique ni effet CRM. |
| `AUT-COR-R16` | Tenter une résolution avec code libre/invalide ; abandonner un cas avec code fermé | Le code libre est refusé (`422`) sans écriture ; l’abandon est explicite, versionné et audité, sans fusion ni création CRM. |
| `AUT-COR-R17` | Réconcilier une exception `effect_uncertain` en cours | Vérification de corrélation/idempotence auditée ; état toujours `en traitement`, aucun retry aveugle ni second effet. |
| `AUT-COR-R18` | Inspecter audit et événements | Codes, versions, corrélations et états présents ; événements allow-listés ; aucune phrase libre, note CRM, secret ou PII interdite. |
| `AUT-COR-R19` | Contrôler fr-CA/en-CA, zoom 200 %, clavier et lecteur d’écran | Libellés, focus, contrastes et disposition restent utilisables. |
| `AUT-COR-R20` | Désactiver les flags / rollback | `AUTOMATION_ENABLED=false` et mode `off` refusent les commandes, les Playbooks sont suspendus, les données et audits sont conservés, navigation sans promesse trompeuse. |
| `AUT-COR-R21` | Ouvrir Administration > Automatisation comme Administrateur | État de l’organisation active, état global, version et génération lisibles ; action limitée au tenant actif. |
| `AUT-COR-R22` | Ouvrir la même route comme Gestionnaire/Sales | Lien absent, API refusée (`403`), aucune élévation de capacité. |
| `AUT-COR-R23` | Confirmer activation puis suspension organisationnelle | Version incrémentée, génération augmentée uniquement à la suspension, audit `automation.organization_settings_changed`, aucun effet CRM/externe. |
| `AUT-COR-R24` | Rejouer une mutation avec une version périmée | `409 automation_settings_version_conflict`, nouvelle version signalée, aucune écriture supplémentaire. |

## Décision de recette

Une anomalie touchant l’isolation d’organisation, la capacité, la suspension, l’idempotence, l’effet CRM/externe ou les
données sensibles est **bloquante**. Les tests `AUT-COR-R18` à `AUT-COR-R20` doivent maintenant être exécutés contre les
preuves décrites dans [AUT-COR-07](./AUT_COR_07_OBSERVABILITE_ROLLBACK.md) ; ils ne peuvent pas être marqués PASS sur la
seule présence de la coque. `AUT-COR-R12`
reste partiellement bloqué tant qu'un fixture de Prévol complet, frais et non vide n'est pas fourni ; le refus sûr du
Prévol de configuration à zéro sujet doit, lui, être validé dès cette recette.

# Contre-validations — Vague A des fondations de décision

| Élément | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Programme | Pré-Phase 5 — Automatisation |
| Périmètre | Étape interne 2 — Vague A |
| Date | 30 septembre 2026 |
| Décisions examinées | `VA-DEC-01` à `VA-DEC-10` |
| Avis sollicités | Design, Ingénierie, Confiance, Sécurité, Qualité |
| Verdict global | **Contre-validée avec réserves explicites transférées** |
| Résultat | Vague A clôturée ; contraintes consolidées dans `RF-AUT-2.1` et transférées à l’Étape 3 |
| N’autorise pas | Développement de production, envoi externe ou clôture de la Phase 5 |
| Dossier normatif | [Vague A — Fondations de décision](./VAGUE_A_FONDATIONS_DECISION.md) |
| Décision ultérieure | [Porte 2 — GO avec réserves](./PORTE_2_GO_AVEC_RESERVES.md) |
| Référence active | [`RF-AUT-2.1` — référence fonctionnelle figée](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) |

## 1. Conclusion exécutive

Les dix décisions produit sont cohérentes avec le socle livré jusqu’à la Phase 4.6. Aucune contre-validation ne demande leur réouverture. Les cinq avis donnent un `GO` pour fermer la Vague A, sous réserve que les contraintes ci-dessous soient conservées comme entrées obligatoires de la Vague B et de l’Étape 3.

Le noyau proposé reste :

- **vendeur**, parce qu’il conduit rapidement à une tâche de prise en charge explicable ;
- **Lite**, parce qu’il repose sur un point d’entrée utilisateur unique, trois surfaces, trois recettes guidées et le mode `Préparer` ;
- **adoptable par une PME**, parce qu’il réutilise les prospects, tâches, membres, permissions et sources déjà connus ;
- **différenciant**, grâce au Passeport, au Prévol et au Feu relationnel par action et canal ;
- **sûr**, parce qu’une approbation ne remplace jamais une permission et qu’un effet différé exige une nouvelle autorisation.

La Vague A est donc déclarée **contre-validée avec réserves explicites transférées**. Depuis cette conclusion, la Vague B, la recette V2.1 et la Porte 2 ont été clôturées. Les invariants issus de ces avis sont consolidés dans `RF-AUT-2.1`. L’Étape 3 de conception technique est autorisée, mais pas l’implémentation de production.

## 2. Méthode et preuves examinées

La revue a comparé chaque décision à des éléments observables du dépôt :

| Domaine | Preuves principales | Constat utile |
| --- | --- | --- |
| Navigation | `client/src/app/navigationModel.js`, `navigationModel.test.js`, `AuthenticatedLayout.jsx`, `MobileNavigationBar.jsx` | Position réservée après Tableau de bord ; quatre raccourcis mobiles actuels et menu Plus |
| Identité | `backend/app/domain/identity.py` | Trois rôles et catalogue statique de capacités par rôle |
| Prospects et conformité | `backend/app/domain/prospect.py`, `prospect_compliance.py` | Canaux LinkedIn/Facebook, provenance, permissions, fournisseurs et quarantaines déjà modélisés |
| Tâches | `backend/app/domain/activity.py`, `application/use_cases/activities.py` | Tâches versionnées et idempotentes, mais sans corrélation Automatisation native |
| Audit | `backend/app/domain/audit.py`, `application/audit_events.py` | Acteurs `system`/source `worker` prévus ; actions et métadonnées fermées |
| Exécution différée | `backend/app/cli/worker.py`, `infrastructure/postgres/job_queue.py` | Worker durable, locataire, idempotent et réautorisant l’appartenance ; contrats fermés |
| Usage | `application/ports/usage.py`, `application/use_cases/usage.py`, `infrastructure/postgres/usage_store.py` | Registre durable ; codes d’usage fermés par contraintes de base |
| Preuve 4.6 | Dossier Vague A | Référence locale consignée ; preuve Azure différée à la clôture de la Phase 5 |

Cette contre-validation porte sur la **conception fonctionnelle**. Elle ne prétend pas prouver un code Automatisation qui n’existe pas encore.

## 3. Avis Design

### 3.1 Résultat

**GO avec deux réserves transférées au prototype V2.**

### 3.2 Points confirmés

1. `VA-DEC-01` est compatible avec la réservation explicite d’Automatisation après Tableau de bord.
2. `VA-DEC-02` et `VA-DEC-03` limitent correctement la profondeur : une seule saisie d’intention dans Aujourd’hui, trois surfaces principales, Passeport/Prévol/approbations et diagnostic de source dans leur contexte.
3. Les liens profonds vers Prospect, Tâches, Opportunités, Imports et Sources évitent un deuxième CRM.
4. Les cartes Aujourd’hui peuvent distinguer recommandation, tâche créée, approbation et action exécutée.
5. Les patrons existants de focus, clavier, changement d’organisation et invalidation de route restent applicables.

### 3.3 Réserves Design

| ID | Réserve | Traitement obligatoire | Échéance |
| --- | --- | --- | --- |
| `CV-DES-01` | La barre mobile contient déjà quatre raccourcis plus le bouton Plus | Conserver ces quatre raccourcis en V1 et placer Automatisation en première position dans Plus, afin de préserver son rang global après Tableau de bord ; tester sa découvrabilité avant toute substitution | Prototype V2 / recherche PME |
| `CV-DES-02` | Les routes imbriquées doivent conserver l’entrée Automatisation active | Définir un identifiant de navigation parent pour toutes les routes `/app/automation/*` et tester le retour, le focus et le changement d’organisation | Prototype V2 |

La décision `VA-DEC-01` reste inchangée pour la navigation principale de bureau et l’ordre du menu mobile. Elle n’impose pas un cinquième raccourci permanent dans la barre mobile.

## 4. Avis Ingénierie

### 4.1 Résultat

**GO de faisabilité, avec contrats techniques obligatoires à concevoir à l’Étape 3.**

### 4.2 Points confirmés

- Le CRM possède déjà les objets maîtres nécessaires : prospect, appartenance, tâche, opportunité, permission, fournisseur, acquisition et audit.
- La file durable fournit les bons patrons : admission transactionnelle, idempotence, empreinte, lease, reprise bornée, annulation, isolation du locataire et contrats enregistrés.
- Le worker réévalue déjà l’état actif de l’utilisateur, de l’appartenance et de l’organisation avant traitement.
- Les tâches existantes acceptent une clé d’idempotence et une empreinte de commande.
- L’audit supporte une origine système/worker et applique un catalogue fermé de métadonnées.

### 4.3 Réserves Ingénierie

| ID | Écart observé | Décision imposée à l’Étape 3 |
| --- | --- | --- |
| `CV-ING-01` | Le worker refuse actuellement tout job sans appartenance humaine ; le commentaire réserve les futurs jobs système à une politique enregistrée | Concevoir un acteur technique explicite, une politique par type d’effet et une révocation ; aucune impersonation silencieuse |
| `CV-ING-02` | Une tâche ne porte pas encore de référence playbook/version/exécution/déclencheur | Ajouter une corrélation structurée ou une relation dédiée ; ne pas placer des identifiants opaques dans la description |
| `CV-ING-03` | Les catalogues jobs, audit et usage sont fermés | Ajouter migrations, politiques de métadonnées et agrégations avant tout nouveau type ; aucun code libre injecté à l’exécution |
| `CV-ING-04` | Les capacités sont aujourd’hui des tuples statiques par rôle | En V1, les droits approuvés s’appliquent à tous les membres actifs du rôle concerné ; toute délégation individuelle serait une capacité nouvelle hors périmètre |
| `CV-ING-05` | Le déclencheur commun Nouveau prospect n’existe pas encore | Émettre l’admission après l’écriture canonique réussie, dans une frontière transactionnelle ou un outbox démontré, avec identité fonctionnelle stable |
| `CV-ING-06` | L’usage actuel ne connaît pas les événements Automatisation | Définir un petit catalogue fermé orienté résultat, sans contenu de message ni donnée personnelle |

Ces écarts n’invalident pas la conception. Ils empêchent en revanche de considérer le socle actuel comme une implémentation implicite du moteur.

## 5. Avis Confiance

### 5.1 Résultat

**GO après correction immédiate de la terminologie du Feu, appliquée au dossier Vague A.**

### 5.2 Points confirmés

1. Le Feu est calculé par action, canal, instant et version de règle ; il n’est jamais global au prospect.
2. `do_not_contact` et `opted_out` entraînent Rouge pour la communication concernée.
3. `unknown`, preuve expirée ou contradictoire entraînent Jaune et interdisent l’envoi.
4. Vert signifie seulement « admissible selon les données disponibles ».
5. Une approbation ne crée pas une permission, ne lève pas une opposition et devient invalide après modification matérielle.
6. La panne, l’absence de responsable, la capacité manquante et la limite temporaire sont des états opérationnels, pas des couleurs relationnelles.

### 5.3 Corrections normatives appliquées

- Suppression de « Jaune opérationnel » et « Vert interne » : une action interne est désormais **permise** ou placée en **exception opérationnelle**, sans Feu relationnel.
- Retrait des limites temporaires de fréquence/volume de la matrice du Feu ; elles deviennent une condition d’exécution distincte.
- Distinction entre permission expirée, qui demande vérification, et contrat de source expiré, qui interdit l’action fondée sur cette provenance.
- Conservation de l’ordre `Rouge > Jaune > Vert` uniquement pour les actions relationnelles.

### 5.4 Réserves Confiance

| ID | Réserve | Traitement |
| --- | --- | --- |
| `CV-CON-01` | Les politiques juridictionnelles et finalités exactes ne sont pas encore configurées | L’Étape 3 doit versionner les règles et leurs territoires ; aucun défaut universel présenté comme avis juridique |
| `CV-CON-02` | Le brouillon personnalisé peut exposer des données même sans envoi | Distinguer modèle générique non adressé et brouillon destiné à un prospect ; Rouge bloque ce dernier |
| `CV-CON-03` | Une donnée peut changer entre approbation et effet | Recalculer le Feu et vérifier la permission immédiatement avant l’effet externe |

## 6. Avis Sécurité

### 6.1 Résultat

**GO de conception ; NO-GO d’exécution externe tant que les contrôles ci-dessous ne sont pas prouvés.**

### 6.2 Points confirmés

- `VA-DEC-10` impose correctement la capacité Automatisation **et** la capacité métier de l’effet.
- La file actuelle démontre l’isolation par organisation, un rôle PostgreSQL worker dédié, la réautorisation de l’appartenance et des secrets d’idempotence robustes.
- Les contrats de jobs, erreurs de rejeu et métadonnées d’audit sont fermés.
- L’approbation séparée pour `manager`/`admin` limite l’autonomie initiale.

### 6.3 Contrôles bloquants pour l’implémentation

| ID | Contrôle exigé | Preuve attendue |
| --- | --- | --- |
| `CV-SEC-01` | Vérifier organisation active, acteur/origine autorisé, capacités Automatisation et CRM à l’admission puis juste avant l’effet | Tests de révocation et de changement d’organisation |
| `CV-SEC-02` | Lier l’approbation à une empreinte du destinataire, canal, contenu, justification, playbook et règle | Test de modification invalidant l’approbation |
| `CV-SEC-03` | Enregistrer les types de jobs système et leur politique d’effet | Registre fermé, acteur technique identifié, droits minimaux |
| `CV-SEC-04` | Protéger les webhooks par signature, fraîcheur, anti-rejeu, rotation des secrets et quotas | Tests négatifs et procédure de rotation |
| `CV-SEC-05` | Ne journaliser ni secret, charge fournisseur, corps de message ou donnée personnelle inutile | Politique d’audit et tests de redaction |
| `CV-SEC-06` | Garder l’envoi externe et toute autonomie supérieure désactivés en V1 tant qu’une porte dédiée ne les autorise pas | Feature flag serveur et test de refus |
| `CV-SEC-07` | Produire un modèle de menace multi-locataire incluant confusion de rôles, TOCTOU, rejeu, injection et exfiltration | Revue Sécurité de l’Étape 3 |

## 7. Avis Qualité

### 7.1 Résultat

**GO sur la testabilité ; scénarios transférés à `P2-PRE3-11` avant la Porte 2.**

Les scénarios suivants sont suffisamment déterministes pour devenir des tests d’acceptation. Leur automatisation n’est pas exigée pour clore la Vague A, mais leur exécution et leurs preuves le seront aux portes prévues.

| ID | Scénario | Résultat attendu | Niveau futur |
| --- | --- | --- | --- |
| `CV-QA-01` | Navigation bureau autorisée | Automatisation apparaît une fois, après Tableau de bord | Composant/navigation |
| `CV-QA-02` | Mobile V1 | Pas de cinquième raccourci ; Automatisation est accessible dans Plus et conserve le focus | Navigateur/a11y |
| `CV-QA-03` | Utilisateur sans lecture Automatisation | Route et entrée absentes ; accès direct refusé côté serveur | API + navigateur |
| `CV-QA-04` | Création manuelle réussie | Une admission Nouveau prospect et au plus un premier effet | Intégration |
| `CV-QA-05` | Import en doublon ou quarantaine | Aucune admission Nouveau prospect | Intégration |
| `CV-QA-06` | Reprise technique | Même identité ; aucune tâche dupliquée | Worker/intégration |
| `CV-QA-07` | Courriel `unknown` | Jaune ; tâche interne permise ; envoi impossible | Domaine/API |
| `CV-QA-08` | Courriel `opted_out` | Rouge ; brouillon personnalisé destiné à l’envoi et envoi bloqués | Domaine/API |
| `CV-QA-09` | Téléphone autorisé, courriel inconnu | Vert téléphone et Jaune courriel, sans Feu global | Domaine/UI |
| `CV-QA-10` | Permission expirée | Jaune et vérification requise | Domaine |
| `CV-QA-11` | Contrat source expiré | Action fondée sur la source interdite et exception explicable | Domaine/intégration |
| `CV-QA-12` | Propriétaire inactif | Exception opérationnelle ; Feu relationnel inchangé | Domaine/UI |
| `CV-QA-13` | Limite temporaire atteinte | Report opérationnel ; aucune couleur relationnelle modifiée | Domaine/UI |
| `CV-QA-14` | Approbation puis modification matérielle | Approbation invalidée avant effet | API/intégration |
| `CV-QA-15` | Opposition découverte après approbation | Effet refusé après nouveau calcul | Worker/intégration |
| `CV-QA-16` | Capacité CRM révoquée après admission | Effet différé refusé et audité sans donnée excessive | Worker/sécurité |
| `CV-QA-17` | Manager d’une autre organisation | Aucun accès, aucune corrélation et aucune fuite de compteur | API/sécurité |
| `CV-QA-18` | Source déconnectée | Exception opérationnelle et diagnostic ; pas de faux Feu Rouge | Intégration/UI |
| `CV-QA-19` | Suspension du playbook | Aucune nouvelle admission ; tâches existantes conservées | Intégration |
| `CV-QA-20` | IA indisponible ou désactivée | Parcours Lite déterministe fonctionnel sans décision de permission par IA | Intégration/UI |

### 7.2 Exigences de preuve

- relier chaque scénario à une exigence et à un résultat archivé ;
- tester les réponses serveur, pas seulement la visibilité des boutons ;
- couvrir français canadien, anglais canadien, clavier, lecteur d’écran et vues mobiles critiques ;
- démontrer l’absence de double effet sous rejeu et concurrence ;
- conserver le report Azure 4.6 comme réserve bloquante du verdict final de Phase 5.

## 8. Registre consolidé des réserves

| Destination | Réserves transférées | Bloque la Vague B | Bloque le développement |
| --- | --- | --- | --- |
| Prototype V2 | `CV-DES-01`, `CV-DES-02` | Non | Non |
| Vague B | `CV-QA-01` à `CV-QA-20`, catalogue d’erreurs et télémétrie | Non | Porte 2 satisfaite ; exigences fonctionnelles consolidées dans `RF-AUT-2.1` et contrôles techniques transférés à l’Étape 3 |
| Étape 3 | `CV-ING-01` à `CV-ING-06`, `CV-CON-01` à `CV-CON-03`, `CV-SEC-01` à `CV-SEC-07` | Non | Oui pour les effets concernés |
| Clôture Phase 5 | Preuve Azure 4.6 reliée au SHA final | Non | Bloque le verdict final |

Aucune réserve n’est silencieuse. Toute suppression ou modification exige une décision enregistrée.

## 9. Décision formelle

| Avis | Verdict | Condition de sortie |
| --- | --- | --- |
| Design | `GO avec réserves` | Règle mobile figée ; preuves au prototype V2 |
| Ingénierie | `GO de faisabilité` | Contrats nouveaux explicitement transférés à l’Étape 3 |
| Confiance | `GO après corrections` | Terminologie et séparation Feu/opérationnel corrigées |
| Sécurité | `GO de conception` | Contrôles bloquants avant implémentation/exécution externe |
| Qualité | `GO sur la testabilité` | Vingt scénarios transférés à `P2-PRE3-11` |

**Verdict global : Vague A contre-validée avec réserves explicites transférées.**

La Vague B et la recette V2.1 ont depuis été validées. La [Porte 2](./PORTE_2_GO_AVEC_RESERVES.md) a reçu un `GO avec réserves` et la [référence `RF-AUT-2.1`](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) est figée. L’Étape interne 3 peut donc commencer dans son seul périmètre de conception technique.

## 10. Journal

| Date | Événement | Effet |
| --- | --- | --- |
| 30 septembre 2026 | Approbation Produit de `VA-DEC-01` à `VA-DEC-10` | Base normative gelée |
| 30 septembre 2026 | Contre-validations Design, Ingénierie, Confiance, Sécurité et Qualité | Vague A fermée avec réserves transférées ; aucune décision produit réouverte |
| 1er octobre 2026 | Porte 2 prononcée `GO avec réserves` | Conditions fonctionnelles satisfaites ; réserves PME et Azure conservées ; conception technique autorisée |
| 1er octobre 2026 | Référence `RF-AUT-2.1` figée | Les contraintes de contre-validation deviennent des entrées versionnées de l’Étape 3 |

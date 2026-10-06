# Contre-validation S4-4 — Brouillons, approbations et cycles de vie

> **Verdict : GO sous prescriptions — définition S4-4 clôturée**  
> **Runtime de brouillon, approbation, API, persistance, worker, connecteur et envoi : NO-GO**  
> **Date :** 1er octobre 2026

## 1. Objet

Cette contre-validation examine la définition S4-4 contre RF-AUT-2.1, les contrats T2, les exigences de sécurité T3 et
les dépendances S4-1, S4-2 et S4-3. Elle valide la précision du contrat documentaire, non l’exécution dans le produit.

Aucun brouillon, approbation, événement actif, appel IA, connecteur ou communication n’a été créé ou exécuté par cette
revue.

## 2. Artefacts contrôlés

- [S4-4 — Brouillons, approbations et cycles de vie](./S4_4_BROUILLONS_APPROBATIONS_CYCLES.md) ;
- [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) ;
- [Vague T2 — Données, règles et contrats](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) ;
- [Vague T3 — Sécurité, IA et résilience](./VAGUE_T3_SECURITE_IA_RESILIENCE.md) ;
- [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ;
- [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ;
- [S4-3 — Assistant IA encadré](./S4_3_ASSISTANT_IA_ENCADRE.md) ;
- [Backlog BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md) ;
- [Registre des preuves PV-AUT-4.1](./PREUVES_VALIDATION_ETAPE_4.md) ;
- [Spécification CRM V1](../SPECIFICATION_CRM_V1.md).

## 3. Verdict résumé

La définition est cohérente avec une Automatisation PME contrôlée : elle rend la relecture possible sans faire croire
qu’un brouillon est envoyé. Une approbation est liée à une révision exacte et ne peut ni modifier le Feu, ni contourner
une permission, ni créer un effet.

La revue a relevé et corrigé l’unique divergence de cycle : cancelled est réservé aux exécutions et jobs ; un brouillon
suspendu est invalidated avec une raison codifiée. Les prescriptions CV-S4-4-01 à CV-S4-4-07 sont ainsi appliquées au
niveau contractuel. Les preuves d’exécution restent D1, puis D2/D3 après la Porte 4.

## 4. Matrice de contrôle

| Contrôle | Résultat | Conclusion |
|---|---|---|
| Cycle brouillon RF-AUT-2.1 | Conforme après correction | États alignés ; aucune transition vers envoyé. |
| Approbation matérielle | Conforme | Révision, empreinte, canal, référence, versions, Prévol et expiration liés. |
| Feu et permission | Conforme | Rouge non dérogeable ; Jaune n’ouvre pas de brouillon de contact ; Vert prépare seulement. |
| Absence d’envoi V1 | Conforme | Aucun contrat, port, job ou connecteur d’envoi défini. |
| Prévol et garde | Conforme | Vérification à la préparation et à la décision ; divergence gagnante. |
| Séparation PME | Conforme sous politique | Distinction par défaut ; mono-utilisateur borné et audité, sans effet externe. |
| Concurrence et idempotence | Conforme au niveau définition | Version attendue, clé, conflit et to_verify définis. |
| Suspension et reprise | Conforme | Invalidation explicable ; reprise = nouveau Prévol et nouvelle révision. |
| Données et audit | Conforme sous preuve | Contenu exclu des traces ; empreintes et codes minimaux. |
| IA | Conforme | L’Assistant ne crée ni brouillon ni approbation et aucun modèle n’est requis. |
| Compatibilité CRM | Conforme | CRM reste propriétaire des objets, membres, droits et historiques canoniques. |

## 5. Prescriptions appliquées au niveau contractuel

### CV-S4-4-01 — États de brouillon cohérents

Les états sont alignés avec RF-AUT-2.1 et T2. La suspension et l’abandon emploient invalidated avec reason_code ;
cancelled est conservé pour le transport et les exécutions, jamais pour une révision de brouillon.

**Preuves runtime restantes :** PV-APP-03 et PV-OPS-02.

### CV-S4-4-02 — Accord humain sans pouvoir d’envoi

Approved enregistre une décision humaine sur une révision donnée. Le catalogue des commandes S4-4 ne contient ni
commande d’envoi, ni port de transport, ni connecteur ni job de diffusion.

**Preuve runtime restante :** PV-FUN-04 avec compteur d’envoi nul et inspection de la configuration.

### CV-S4-4-03 — Empreinte serveur exhaustive

Material fingerprint, calculée serveur, lie révision, contenu protégé, référence de destinataire, canal, finalité,
Playbook, ruleset, Prévol, snapshot, Feu et politique d’approbation. Toute divergence invalide ou refuse.

**Preuves runtime restantes :** PV-APP-01 et PV-APP-02.

### CV-S4-4-04 — Politique PME de séparation explicite

La séparation préparateur/approbateur est la règle par défaut. La politique single_operator_approval n’est possible
qu’en organisation mono-utilisateur non configurée avec un autre approbateur actif ; elle est versionnée, auditée et
incapable d’ouvrir un envoi ou une dérogation.

**Preuve runtime restante :** PV-APP-01 sous les deux politiques et revue des capacités effectives.

### CV-S4-4-05 — Double garde non dérogeable

La garde contrôle tenant, rôles, capacités, portée CRM, Feu, permission, versions, Prévol, empreinte, expiration et
génération de suspension avant préparation et décision. Une approbation passée ne suffit jamais seule.

**Preuves runtime restantes :** PV-FUN-04 et PV-OPS-02.

### CV-S4-4-06 — Rejeu, concurrence et incertitude

Version attendue et clé d’idempotence sont obligatoires. Une écriture ambiguë devient to_verify avec relecture par
révision, empreinte, clé et corrélation ; deux décisions incompatibles ne peuvent toutes deux réussir.

**Preuves runtime restantes :** PV-CONC-01 et PV-CONC-02.

### CV-S4-4-07 — Contenu absent de l’observabilité

Le texte, le destinataire, les coordonnées et les notes ne sont ni audités ni télémétrés. Seules références minimales,
empreintes, versions, décisions, raisons codifiées, expiration, génération et corrélation sont admises.

**Preuve runtime restante :** PV-AUD-02 avec inspection des journaux sur données synthétiques.

## 6. Compatibilité avec les tranches précédentes

| Frontière | Règle confirmée |
|---|---|
| S4-1 Prévol | Toute révision porte un Prévol et une empreinte courants ; changement = invalidation. |
| S4-2 | La tâche interne est indépendante ; une approbation n’autorise pas un contact externe. |
| S4-3 | L’IA peut expliquer un plan, jamais rédiger, approuver, choisir un destinataire ou créer un brouillon. |
| Feu relationnel | Rouge et Jaune restent non dérogeables selon RF-AUT-2.1. |
| Capacités | Chaque décision est faite sous capacités présentes et portée CRM actuelle. |
| Suspension | La génération de suspension gagne sur tout accord antérieur. |
| CRM | Les objets, permissions, membres, sources et historiques demeurent canoniques. |

## 7. Scénarios de preuve contre-validés

| ID | Scénario | Oracle | État |
|---|---|---|---|
| PV-FUN-04 | Préparer un brouillon Vert | Brouillon visible, aucun connecteur ni envoi | D1 défini |
| PV-APP-01 | Approuver une révision exacte | Tous les éléments matériels concordent | D1 défini |
| PV-APP-02 | Modifier après approbation | Accord invalidé ; nouvelle révision obligatoire | D1 défini |
| PV-APP-03 | Atteindre l’expiration | Décision ultérieure refusée | D1 défini |
| PV-CONC-01 | Approuver et refuser simultanément | Une seule transition terminale | D1 défini |
| PV-CONC-02 | Suspendre pendant une demande | Nouvelle décision bloquée ; état invalidated | D1 défini |
| PV-AUD-02 | Inspecter les traces | Aucun contenu, destinataire ou PII inutile | D1 défini |
| PV-OPS-02 | Relire la génération d’arrêt | Aucun effet futur après suspension | D1 défini |

## 8. Risques résiduels

| Risque | Niveau | Condition de levée |
|---|---|---|
| Accord interprété comme un envoi | Élevé | PV-FUN-04 et revue des routes/configurations |
| Contenu ou destinataire journalisé | Élevé | PV-AUD-02 et analyse des sorties |
| Approbation sur une version périmée | Élevé | PV-APP-01/02 et garde effective |
| Conflit de décision | Moyen | PV-CONC-01 avec contrôle transactionnel |
| Suspension non lue | Élevé | PV-CONC-02/PV-OPS-02 avec job en cours |
| Politique mono-utilisateur trop permissive | Moyen | Capacité explicite, configuration et audit inspectés |
| Rétention de contenu insuffisamment arrêtée | Moyen | Décision Données/Conformité avant persistance |

## 9. Décision

La contre-validation donne un **GO sous prescriptions** à la définition S4-4 et confirme sa clôture documentaire. La
tranche peut rejoindre le dossier de Porte 4, sans être considérée prête à intégrer.

Elle n’autorise pas :

- la création de table, migration, API ou persistance active ;
- le branchement d’un worker ;
- la préparation ou l’approbation d’un brouillon réel ;
- l’accès à un fournisseur IA ou un connecteur ;
- l’envoi externe, automatique ou manuel par le module Automatisation ;
- la production ou les sessions PME.

## 10. Suite

1. conserver CV-S4-4-01 à CV-S4-4-07 comme critères d’intégration ;
2. arrêter les décisions Données/Conformité sur protection et conservation du contenu ;
3. préparer des fixtures synthétiques pour PV-FUN-04, PV-APP-01..03, PV-CONC-01..02, PV-AUD-02 et PV-OPS-02 ;
4. exécuter les preuves D2/D3 après la Porte 4 ;
5. n’ouvrir le runtime S4-4 que par une décision de construction explicitement limitée.

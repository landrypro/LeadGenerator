# Vague T4 — Estimer, découper et assembler la Porte 3

> **Statut : contre-validation réalisée le 1er octobre 2026 — `GO sous prescriptions`.**  
> **Décision d’ouverture :** GO utilisateur du 1er octobre 2026.  
> **Portée :** estimation paramétrée, capacité du worker, latence cible, tranches d’implémentation, ADR consolidées, risques et dossier préparatoire de la Porte 3.  
> **Hors portée :** une mesure de production, un choix de fournisseur IA, un engagement de prix, le développement et le GO de production.

## 1. Décision et règles de lecture

Le passage T3 → T4 est autorisé explicitement par le commanditaire. La contre-validation formelle de T3 n’est donc pas présentée comme acquise : ses prescriptions restent des conditions de la Porte 3.

Les chiffres ci-dessous sont des **hypothèses de cadrage**, pas des métriques observées ni un devis. Ils doivent être remplacés par les résultats de tests de charge et les tarifs contractuels retenus avant tout engagement financier.

Les invariants de [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) restent non négociables : mode **Préparer**, objets CRM canoniques, Feu relationnel déterministe, Prévol sans effet, approbation humaine, aucune communication externe autonome et IA sans pouvoir d’exécution.

## 2. Point de départ vérifié

| Élément existant | Fait observé dans le socle | Conséquence pour l’estimation |
|---|---|---|
| File de travaux | PostgreSQL, statuts `queued/running/succeeded/failed/cancelled`, 1–3 tentatives | Réutilisable comme transport durable, sous garde applicative supplémentaire. |
| Concurrence par organisation | Un seul job actif par organisation ; profondeur mise en attente plafonnée à 100 | Le débit d’une organisation est volontairement sérialisé. La latence doit être calculée organisation par organisation. |
| Idempotence actuelle | Clé HMAC et empreinte de charge au dépôt d’un job | À étendre à l’exécution, aux effets CRM et à chaque étape. |
| Admission actuelle | Une appartenance humaine active est requise ; contrats de jobs sur liste blanche | Un principal technique borné est encore requis pour les scans et événements internes autorisés. |
| Traçabilité | Journal d’audit métier existant | Les décisions Automation peuvent rejoindre ce mécanisme, avec minimisation des données. |
| Infra Azure 4.6 | Preuve reportée à la fin de la Phase 5 | Ne fonde ni le coût ni la faisabilité T4 ; reste une réserve de production. |

Référence de cartographie : [Vague T1](./VAGUE_T1_CARTOGRAPHIE_SOCLE_FRONTIERES.md). Référence des contrats logiques : [Vague T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md). Référence de sécurité : [Vague T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md).

## 3. Modèle de charge et capacité

### 3.1 Hypothèses de dimensionnement, à mesurer

| Variable | Signification | Valeur de cadrage | À valider avant Porte 3 |
|---|---|---:|---|
| `S95` | Durée p95 d’un job Automation gardé, hors attente humaine | ≤ 3 secondes | Oui |
| `Smax` | Durée maximale acceptable d’un job unique | ≤ 9 secondes | Oui |
| `Q` | Nombre maximal de jobs en attente dans une organisation | 100 (socle actuel) | Oui, adéquation produit |
| `B` | Taille maximale d’un lot déclenché par un événement | 25 objets | Oui |
| `R` | Nombre de nouvelles tentatives automatiques | 0 pour tout effet CRM ; reprise explicitement conçue | Oui |
| `N` | Nombre de workers réellement disponibles | À mesurer dans l’environnement cible | Oui |

La borne volontairement conservatrice pour une organisation est :

`attente maximale théorique ≈ Q × S`.

Avec la limite existante de 100 jobs, `Smax ≤ 9 secondes` maintient une attente théorique sous 15 minutes si la file était pleine. La cible `S95 ≤ 3 secondes` donne une marge utile : une file pleine représenterait environ 5 minutes, avant prise en compte de nouvelles arrivées. Ce ne sont pas des promesses de service : des arrivées continues ou des jobs plus longs exigent un refus contrôlé ou un découpage.

Le débit global n’est pas simplement « un job à la fois » : des organisations différentes peuvent être traitées en parallèle. Sous hypothèse de workers disponibles et d’organisations distinctes, l’ordre de grandeur est :

`débit global ≈ N × 60 / S jobs par minute`.

La politique produit proposée est donc : **sérialiser par organisation, paralléliser entre organisations, borner chaque lot à 25 et appliquer un back-pressure avant saturation**.

### 3.2 Enveloppes de charge — non prévisions commerciales

| Palier | Organisations actives | Candidats Automation / jour / organisation | Jobs / candidat | Volume / jour | Lecture |
|---|---:|---:|---:|---:|---|
| Lancement contrôlé | 10 | 20 | 1–2 | 200–400 | Suffisant pour valider les parcours sans déformer la file. |
| Pilote élargi | 25 | 40 | 1–2 | 1 000–2 000 | Teste simultanément les trois Playbooks et les exceptions. |
| Extension | 100 | 50 | 1–2 | 5 000–10 000 | Ne peut être franchi sans résultats de charge et observabilité. |

Ces enveloppes excluent les communications externes, car V1 n’en envoie pas. Toute exploration planifiée doit être paginée, portant un curseur et respecter `B = 25` ; aucune recherche globale ne doit déposer un lot massif en file.

### 3.3 Protocole de preuve de capacité

| ID | Preuve | Critère de sortie | Échec / réponse attendue |
|---|---|---|---|
| `T4-CAP-01` | Charge d’admission et de Prévol sur une organisation saturée | Aucun dépassement silencieux du plafond ; message exploitable au-delà de la capacité | Refuser ou différer explicitement, sans perte de demande. |
| `T4-CAP-02` | Jobs concurrents sur 25 organisations | Un seul job actif par organisation ; parallélisme inter-organisations stable | Bloquer le job concurrent ou le laisser en attente avec corrélation. |
| `T4-CAP-03` | Mesure `S95` avec garde, audit et commande CRM simulée | `S95 ≤ 3 s`, `Smax ≤ 9 s` dans le palier retenu | Réduire le lot, optimiser ou revoir le niveau de service. |
| `T4-CAP-04` | Redémarrage worker au milieu d’une exécution | Aucun double effet CRM, aucune approbation réutilisée | Réconciliation et passage explicite en exception si incertain. |
| `T4-CAP-05` | Rafale de 25 entrées puis suspension globale | Aucun effet après invalidation ; indicateurs de saturation présents | Couper via feature flag et conserver les traces. |

## 4. Latence de l’expérience et contrats de service internes

| Moment | Cible produit | Mesure à instrumenter | Réserve |
|---|---|---|---|
| Interprétation de phrase IA | Réponse de plan lisible en moins de 8 s au p95 | durée IA, repli déterministe, erreur normalisée | Dépend du modèle et du fournisseur non choisis. |
| Prévisualisation déterministe | Prévol affichable en moins de 3 s au p95 | durée règles, lecture CRM, version de règle | Ne doit pas invoquer l’IA. |
| Préparation d’une action interne | Confirmation ou exception en moins de 15 min à file pleine | attente en file, durée job, profondeur par organisation | Cible conditionnée par `Smax ≤ 9 s`. |
| Vérification avant effet CRM | Ajout quasi transparent au job | temps de garde, motif de refus | Ne peut jamais être sacrifiée pour la latence. |
| Intervention humaine | Pas de promesse automatique | âge du brouillon, âge de l’exception, SLA d’équipe | L’humain reste la décision. |

## 5. Estimation de coût et de charge

### 5.1 Charge de construction

| Tranche | Contenu | Charge ingénierie estimative | Contrôle produit, QA, sécurité estimatif |
|---|---|---:|---:|
| 0 | Fondations : flags, capacités, migrations, audit de base | 8–12 j.h. | 3–5 j.h. |
| 1 | Noyau déterministe : données, version, Feu, Prévol | 10–15 j.h. | 3–5 j.h. |
| 2 | « Nouveau prospect » en Préparer avec garde avant effet | 12–18 j.h. | 4–6 j.h. |
| 3 | Plan IA encadré, repli, interface et explication | 8–14 j.h. | 3–5 j.h. |
| 4 | Brouillons, approbations, cycles et invalidation | 10–15 j.h. | 3–5 j.h. |
| 5 | Deux autres Playbooks, exceptions et réconciliation | 12–18 j.h. | 4–6 j.h. |
| 6 | Résilience, charge, observabilité, déploiement progressif | 12–18 j.h. | 5–8 j.h. |
| **Total** | **V1 de production interne, sans envoi externe autonome** | **72–110 j.h.** | **25–40 j.h.** |

Cette fourchette suppose la réutilisation du monolithe, de PostgreSQL, de la file et de l’audit existants. Elle n’inclut ni migration d’infrastructure, ni preuve Azure 4.6, ni intégration d’envoi externe, ni sessions PME post-production. Prévoir une contingence de **10 à 15 %** après les preuves `T4-CAP` et le choix du fournisseur IA.

### 5.2 Coût d’exploitation — formule, pas tarif inventé

Le fournisseur et le modèle IA ne sont pas sélectionnés. Le budget ne peut donc pas être chiffré honnêtement en devise. La formule à renseigner au choix contractuel est :

`C_IA = (tokens_entrée / 1 000 000 × prix_entrée) + (tokens_sortie / 1 000 000 × prix_sortie) + coûts_fixes`.

| Volume mensuel de plans IA | Hypothèse par plan | Jetons d’entrée / sortie | Usage attendu |
|---:|---|---:|---|
| 50 | 2 000 / 500 | 0,10 M / 0,025 M | Lancement interne. |
| 500 | 2 000 / 500 | 1,00 M / 0,25 M | Pilote élargi. |
| 2 500 | 2 000 / 500 | 5,00 M / 1,25 M | Extension à contrôler. |

Le coût du worker et de PostgreSQL doit être observé à part : `C_infra_incremental = temps_worker + lectures/écritures + stockage audit + alertes`. Aucune donnée CRM ou phrase libre ne doit être envoyée au fournisseur au-delà de la minimisation décrite en T3. Le choix de fournisseur devra confirmer résidence, conservation, non-entraînement et prix ; sans cela, `T4-COST-01` reste ouvert.

## 6. Tranches d’implémentation et retours arrière

| Tranche | Résultat livrable | Critère d’acceptation | Retour arrière |
|---|---|---|---|
| 0 — Sécuriser | Capacités, principal technique borné, feature flags, tables et audit | Aucun chemin Automation sans tenant, rôle et corrélation | Désactivation de flags ; tables conservées, aucun effet métier. |
| 1 — Voir | Moteur de règles, versions, Feu et Prévol sans effet | Prévol et exécution partagent le même noyau ; décisions explicables | Désactivation du point d’entrée ; lecture des traces conservée. |
| 2 — Préparer | Playbook « Nouveau prospect », tâche interne seulement | Garde juste avant effet ; idempotence et exception prouvées | Suspension Playbook + annulation contrôlée des jobs non commencés. |
| 3 — Demander | Assistant IA : intention structurée, plan, repli guidé | Aucune sortie IA n’appelle une commande métier | Désactivation IA, parcours Playbooks inchangé. |
| 4 — Valider | Brouillons, approbations, invalidation et Feu | Changement matériel invalide l’approbation | Suspension des approbations ; brouillons lisibles sans action. |
| 5 — Étendre | Deux autres Playbooks, exceptions, réconciliation | Aucun changement de pipeline silencieux ; les cas ambigus restent humains | Suspension indépendamment par Playbook. |
| 6 — Lancer prudemment | Charge, tableaux de bord, alertes et exposition graduelle | Les seuils T4-CAP et sécurité sont verts | Flag organisationnel/global, génération d’annulation et procédure de réconciliation. |

La tranche 2 est le premier jalon qui peut modifier le CRM, et seulement pour préparer une tâche interne autorisée. Une communication externe reste exclue de toutes les tranches V1.

## 7. ADR consolidées pour la Porte 3

| ADR | Décision candidate | État pour Porte 3 | Condition de fermeture |
|---|---|---|---|
| `ADR-AUT-001` | Module Automation interne au monolithe, ports explicites vers CRM, IA et file | Candidate acceptée | Revoir si les seuils de capacité imposent une séparation. |
| `ADR-AUT-002` | PostgreSQL/worker existant comme transport durable, admission transactionnelle | Candidate conditionnelle | Prouver concurrence, reprise et saturation ; aucun outbox générique avant besoin prouvé. |
| `ADR-AUT-003` | Versions de Playbook et règles immuables une fois actives | Candidate acceptée | Migration et stratégie de conservation testées. |
| `ADR-AUT-004` | Idempotence de bout en bout par corrélation, empreinte et étape | Candidate acceptée | Rejeu et crash-injection sans double effet. |
| `ADR-AUT-005` | Feu et Prévol évalués par le même noyau déterministe | Candidate acceptée | Tests de fidélité des trois Playbooks. |
| `ADR-AUT-006` | IA interprète et explique ; intention typée, pas d’outil ni de droit | Candidate acceptée | Évaluations adversariales et repli non-IA. |
| `ADR-AUT-007` | Approbation liée au contenu, au destinataire, au canal et à la version | Candidate acceptée | Invalidation de tout changement matériel démontrée. |
| `ADR-AUT-008` | Audit minimal, corrélé et sans texte libre/payload IA complet | Candidate acceptée | Politique de rétention et revue données. |
| `ADR-AUT-009` | Feature flag global, organisationnel et par Playbook ; suspension générationnelle | Candidate acceptée | Test d’arrêt pendant exécution. |
| `ADR-AUT-010` | Coûts IA pilotés par enveloppe de jetons et limites par organisation | Candidate conditionnelle | Fournisseur, prix, résidence et plafonds approuvés. |

Les ADR 001 et 002 restent les documents de détail de T2 ; cette table les rend décisionnelles pour la Porte 3 sans les dupliquer.

## 8. Registre des risques Porte 3

| ID | Risque | Niveau initial | Réponse / propriétaire | Preuve ou condition de clôture |
|---|---|---|---|---|
| `R-T4-01` | Saturation ou attente indéterminée de la file | Élevé | Engineering : back-pressure, lots bornés, `T4-CAP-01..03` | Seuils de charge mesurés et alertes actives. |
| `R-T4-02` | Double effet après crash, rejeu ou course | Élevé | Engineering : corrélation, idempotence par étape, réconciliation | `T4-CAP-04` vert. |
| `R-T4-03` | Effet CRM sans droit à l’instant d’exécution | Élevé | Sécurité : garde avant effet et révocation | Tests de capacités modifiées entre plan et exécution. |
| `R-T4-04` | Fuite inter-organisation ou confusion de tenant | Élevé | Sécurité : `TenantContext`, RLS, tests négatifs | Tests multi-tenant et revue migration. |
| `R-T4-05` | Principal technique trop large | Élevé | Sécurité : origine, scope et durée bornés | Journal de refus et revue de droits. |
| `R-T4-06` | IA injectée, ambiguë ou trop coûteuse | Élevé | Produit/IA : schéma fermé, repli, quotas, tests adversariaux | `AI-ADV-01..10` et choix fournisseur. |
| `R-T4-07` | Texte libre ou données personnelles conservés inutilement | Moyen/élevé | Produit/Sécurité : minimisation et rétention | Politique validée avant activation IA. |
| `R-T4-08` | Écart Prévol/exécution | Élevé | Engineering : noyau partagé, snapshot versionné | Tests de fidélité et traces comparables. |
| `R-T4-09` | Modification silencieuse de pipeline ou envoi externe | Élevé | Produit : capabilities, mode Préparer, contrats d’envoi désactivés | Test de non-régression et audit sans envoi. |
| `R-T4-10` | Adoption PME insuffisante | Moyen | Produit : parcours guidé, métriques, sessions reportées | Sessions PME après production ; pas un prérequis du GO technique. |
| `R-T4-11` | Preuve Azure 4.6 absente | Moyen | Plateforme : preuve en fin de Phase 5 | Réserve explicite avant production dépendante du socle. |
| `R-T4-12` | Découpage trop fin ou service séparé prématuré | Moyen | Architecture : conserver monolithe modulaire | Réévaluation avec métriques T4, pas par anticipation. |

## 9. Assemblage du dossier Porte 3

Le dossier préparatoire est dans [PORTE_3_FAISABILITE_MAITRISE.md](./PORTE_3_FAISABILITE_MAITRISE.md). Il ne prononce pas encore le verdict. Sa contre-validation devra confirmer les éléments suivants :

1. les cibles de capacité et les scénarios de panne sont testables sur l’environnement représentatif ;
2. les réserves `R-T4-01` à `R-T4-11` ont un propriétaire, une preuve et un jalon ;
3. le fournisseur IA, les limites d’usage et la politique de données sont décidés avant son activation ;
4. les prescriptions T3 (garde avant effet, tenant, principal technique, audit, arrêt) sont intégrées au découpage ;
5. le report Azure 4.6 et celui des sessions PME sont inchangés et visibles dans la décision.

## 10. Résultat de la Vague T4

T4 rend possible une décision Porte 3 fondée sur des éléments chiffrables et réversibles. La [contre-validation T4](./CONTRE_VALIDATION_VAGUE_T4.md) a prononcé un **`GO sous prescriptions`** et la [Porte 3](./PORTE_3_FAISABILITE_MAITRISE.md) un **`GO conditionnel` vers l’Étape 4 — Plan de livraison et protocole de validation**. Aucun de ces verdicts ne vaut GO de développement, de mise en production ou d’envoi externe.

## 11. Traçabilité

- [Étape interne 3 — Architecture, données et sécurité](./ETAPE_3_ARCHITECTURE_DONNEES_SECURITE.md)
- [Vague T1 — Cartographier le socle et les frontières](./VAGUE_T1_CARTOGRAPHIE_SOCLE_FRONTIERES.md)
- [Vague T2 — Données, règles et contrats](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md)
- [Vague T3 — Sécurité, IA et résilience](./VAGUE_T3_SECURITE_IA_RESILIENCE.md)
- [Référence fonctionnelle Automation V2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md)
- [Contre-validation T4 et verdict de Porte 3](./CONTRE_VALIDATION_VAGUE_T4.md)
- [Boussole d’évolution](./BOUSSOLE_EVOLUTION_AUTOMATISATION_MARKETTEO.md)

# Contre-validation — Vague T4 et décision de Porte 3

> **Date :** 1er octobre 2026  
> **Décision :** `GO sous prescriptions` pour T4 ; `GO conditionnel` de Porte 3 vers l’Étape 4 — Plan de livraison et protocole de validation.  
> **Ce verdict n’autorise pas le développement, une migration, l’activation de l’IA, un effet CRM Automation, un envoi externe ou la production.**

## 1. Objet de la contre-validation

La présente revue vérifie si les travaux T1 à T4 rendent l’Automatisation **faisable et maîtrisable en conception**, sans confondre :

- la solidité du socle existant ;
- une architecture proposée ;
- une preuve de performance qui n’existe pas encore ;
- une autorisation de préparer l’implémentation ;
- une autorisation de construire ou de mettre en production.

Les entrées sont [T1](./VAGUE_T1_CARTOGRAPHIE_SOCLE_FRONTIERES.md), [T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md), [T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md), [T4](./VAGUE_T4_ESTIMATION_PORTE_3.md) et la [référence fonctionnelle RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md).

## 2. Preuves examinées

| Domaine | Évidence | Conclusion honnête |
|---|---|---|
| Référence fonctionnelle | V2.1 figée : entrée IA unique, trois Playbooks, Feu, Prévol, Préparer et exceptions | Contrat fonctionnel assez précis pour planifier la construction. |
| File durable existante | États bornés, contrainte d’origine, idempotence HMAC/empreinte, limite 100 et un actif par organisation | Base réutilisable, mais non encore adaptée aux effets Automation. |
| CRM et audit | Objets canoniques, contrôles d’appartenance et audit existant | Le principe « pas de second CRM » est techniquement crédible. |
| T2 | Entités, versions, règles, API, événements, concurrence et séquences | Contrats de conception cohérents ; aucune migration ni API Automation active. |
| T3 | Droits, garde avant effet, frontière IA, menace, audit et suspension | Protections correctement spécifiées ; leur preuve de code reste à réaliser. |
| T4 | Formules de capacité/coût, `T4-CAP-01..05`, tranches, ADR et risques | Estimation utile et réversible ; ce ne sont pas des mesures de production. |
| Contrôle documentaire | 19 documents Markdown Automation, aucun lien local rompu | Traçabilité cohérente. |
| Tests ciblés du socle | 28 tests réussis : tenancy, worker lifecycle, organisation, audit, tâches et pipeline | Régression ciblée absente dans le socle contrôlé ; aucun test Automation n’existe encore. |
| Verrou complet du dépôt | Commande locale non exécutée puis écartée par décision du commanditaire pour cette consolidation | Le verrou n’est ni présenté comme vert ni requis pour le présent verdict documentaire ; les exigences ultérieures restent tracées. |

## 3. Avis croisés et contre-vérifications

| Axe | Verdict | Raisonnement | Prescription transférée |
|---|---|---|---|
| Produit PME | Favorable sous réserve | Le périmètre est Lite, guidé, sans constructeur libre ; l’Assistant unique ne concurrence ni les Playbooks ni les exceptions | `P3-PRD-01` : sessions PME conservées après production et utilisées avant élargissement. |
| Architecture | Favorable sous réserve | Monolithe modulaire, PostgreSQL/RLS et worker existant évitent une nouvelle plateforme prématurée | `P3-ARC-01` : mesurer `T4-CAP-01..05` avant tout effet Automation ; réévaluer la séparation seulement sur données. |
| Sécurité | Favorable sous réserve forte | T3 interdit une écriture CRM directe et définit une garde juste avant effet | `P3-SEC-01` : garde d’effet, TenantContext, capacité et version doivent être vérifiés côté serveur pour chaque effet. |
| Résilience | Réserve ouverte | Le worker actuel autorise 1 à 3 tentatives pour les erreurs transitoires ; une reprise générique est incompatible avec un effet CRM ambigu | `P3-RES-01` : aucun retry automatique d’effet Automation ; état incertain vers `to_verify` et reprise humaine ou idempotence d’étape démontrée. |
| IA et données | Réserve ouverte | La frontière IA est saine sur le papier, mais fournisseur, prix, résidence et conservation sont inconnus | `P3-IA-01` : aucun appel réel avant choix contractuel et évaluations adversariales réussies. |
| Coûts et exploitation | Favorable pour planifier, non prouvé pour produire | Les formules et enveloppes sont suffisantes pour estimer ; elles ne remplacent pas les mesures | `P3-OPS-01` : renseigner tarifs, volumes et seuils après choix fournisseur et test de charge. |
| Qualité | Dérogation documentaire acceptée | Les tests ciblés et les contrôles documentaires sont verts ; le verrou complet n’est pas exécuté pour cette décision sur instruction du commanditaire | `P3-QUA-01` : dérogation limitée à T4/Porte 3 ; les contrôles qualité d’implémentation et de production du socle restent applicables à l’Étape 4/Porte 4. |

## 4. Constats critiques

### 4.1 Capacité et worker

La file existante a bien un plafond d’admission de 100 travaux en attente et une concurrence maximale de un travail actif par organisation. La formule T4 — `attente ≈ Q × S` — est donc structurellement cohérente.

Mais `S95 ≤ 3 secondes` et `Smax ≤ 9 secondes` sont des **cibles**, non des observations. Leur validation exige les scénarios `T4-CAP-01` à `T4-CAP-05`, sur un environnement représentatif. La capacité reste une réserve, pas une preuve.

### 4.2 Reprises et effets CRM

Le worker actuel peut reprogrammer une erreur transitoire jusqu’au maximum de tentatives du job. Cette logique est appropriée aux jobs existants, mais ne doit pas être réemployée sans adaptation pour une commande CRM Automation. Un timeout après effet potentiel doit être traité comme incertain : pas de rejeu aveugle, contrôle d’idempotence de l’étape, sinon exception `to_verify`.

### 4.3 Sécurité et IA

Le modèle T3 est accepté comme contrat de conception : l’IA ne produit qu’une intention typée, sans outil ni capacité ; le moteur de règles et la garde sont les seuls chemins d’autorisation. Cependant, le principal technique borné, la garde d’effet et les évaluations adversariales ne sont pas implémentés. Ils sont donc des critères d’entrée de l’implémentation, non des acquis.

### 4.4 Coût, conformité et Azure

Le modèle de coût paramétré est accepté ; aucun tarif n’est fabriqué. Le choix de fournisseur IA doit fermer prix, limites, résidence, conservation et non-entraînement avant activation. La preuve Azure 4.6 reste correctement reportée à la fin de la Phase 5 et bloque toute conclusion de production qui dépendrait de ce socle.

## 5. Décision T4

### Verdict T4 : `GO sous prescriptions`

T4 est jugée suffisante pour assembler la Porte 3 parce qu’elle fournit une estimation traçable, une stratégie de preuve, des tranches réversibles, des ADR consolidées et un registre de risques avec propriétaires proposés.

Elle n’est pas une preuve de performance ni de coût réel. Les prescriptions `P3-ARC-01`, `P3-SEC-01`, `P3-RES-01`, `P3-IA-01`, `P3-OPS-01` et `P3-QUA-01` sont obligatoires.

## 6. Verdict explicite de Porte 3

### Porte 3 : `GO CONDITIONNEL — Étape 4 autorisée`

La faisabilité de conception et la maîtrise **prévisionnelle** sont établies pour ouvrir l’**Étape 4 — Plan de livraison et protocole de validation**. L’équipe peut désormais transformer les tranches T4 en backlog vertical, définir les tests d’acceptation, préparer les migrations sans les exécuter, établir les estimations actualisées et organiser les preuves de capacité.

### Ce que le GO autorise

- plan de livraison détaillé, dépendances et critères d’acceptation ;
- conception des tests de charge, de sécurité, de reprise et d’évaluations IA ;
- choix documenté du fournisseur IA et revue données ;
- préparation technique isolée et versionnée, sans branchement au produit actif ;
- mise à jour des estimations à partir des preuves obtenues.

### Ce que le GO n’autorise pas

- développement ou migration appliquée au produit actif ;
- activation d’un Playbook, d’un worker Automation ou du principal technique ;
- création de tâche CRM par Automation, y compris en apparence « interne » ;
- appel d’un fournisseur IA réel avec des données Marketteo ;
- envoi externe, changement de pipeline, production ou élargissement client.

## 7. Conditions de passage vers la construction

| ID | Condition obligatoire | Porteur proposé | Preuve attendue |
|---|---|---|---|
| `P3-ARC-01` | Exécuter `T4-CAP-01..05` et fixer les seuils réels | Engineering / plateforme | Rapport de charge, saturation, reprise et suspension. |
| `P3-SEC-01` | Implémenter et tester la garde avant effet et le TenantContext | Engineering / sécurité | Tests de révocation et d’isolation négatifs. |
| `P3-SEC-02` | Définir un principal `automation-system` à origine et portée bornées | Sécurité / architecture | Matrice de capacités, refus journalisés. |
| `P3-RES-01` | Désactiver tout retry aveugle pour les effets Automation | Engineering | Crash-injection sans double effet ; `to_verify` en cas d’incertitude. |
| `P3-IA-01` | Choisir fournisseur/modèle et valider prix, données et évaluations adversariales | Produit / sécurité / achats | Décision contractuelle, quotas et résultats `AI-ADV-01..10`. |
| `P3-DATA-01` | Approuver minimisation et rétention des données IA/audit | Produit / sécurité / conformité | Politique versionnée avant stockage ou appel réel. |
| `P3-OPS-01` | Mettre en place métriques, alertes, flags et procédure de retour arrière | Engineering / exploitation | Exercice de suspension et tableau de bord minimal. |
| `P3-QUA-01` | Appliquer les contrôles qualité de l’Étape 4 et de la Porte 4 ; le verrou complet est écarté pour la présente décision documentaire | Engineering / QA | Matrice de tests et preuves ciblées versionnées ; les exigences qualité de construction/production restent à satisfaire avant mise en service. |
| `P3-PLAT-01` | Conserver la preuve Azure 4.6 au jalon fin Phase 5 | Plateforme | Preuve séparée ; ne pas la substituer à T4. |
| `P3-PRD-01` | Réaliser les sessions PME après production avant élargissement | Produit / succès client | Rapport de recherche et décisions d’adoption. |

## 8. Registre de décision et prochain jalon

| Date | Décision | Effet |
|---|---|---|
| 1er octobre 2026 | T4 contre-validée `GO sous prescriptions` | Les hypothèses et réserves deviennent des conditions suivies. |
| 1er octobre 2026 | Porte 3 prononcée `GO conditionnel` | Étape 4 — Plan de livraison et protocole de validation autorisée, sans construction ni production. |

La prochaine porte est la **Porte 4 — Prêt à construire**. Elle ne pourra être sollicitée que lorsque les conditions de la section 7 auront des preuves vérifiables.

## 9. Qualité de la revue

- Vérification des liens locaux Automation : **19 documents, zéro lien rompu**.
- Tests ciblés du socle : **28 réussis**.
- Verrou complet : **écarté pour T4/Porte 3 sur décision du commanditaire**. Il n’est pas présenté comme exécuté ni comme vert. La dérogation ne s’étend pas aux contrôles de construction, de préproduction ou de production du socle CRM.

Cette décision réduit la preuve technique disponible ; elle est acceptable ici parce que le verdict porte uniquement sur l’ouverture d’une étape de planification, sans code Automation actif ni effet CRM.

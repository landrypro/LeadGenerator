# Porte 3 — Faisabilité et maîtrise de l’Automatisation

> **Statut : verdict prononcé le 1er octobre 2026 — `GO CONDITIONNEL` vers l’Étape 4 — Plan de livraison et protocole de validation.**  
> **Objet :** assembler les preuves de l’Étape interne 3 avant une décision de faisabilité et de maîtrise.  
> **Ce verdict n’autorise ni développement, ni production, ni envoi externe.**

## 1. Décision à prendre ultérieurement

La Porte 3 devra choisir l’un des trois verdicts suivants :

| Verdict | Sens |
|---|---|
| GO conditionnel | Autorise la planification détaillée de l’Étape 4, avec réserves datées et propriétaires. |
| GO limité | Autorise uniquement les tranches sans effet CRM ou sans IA, pour lever une preuve ciblée. |
| NO GO / report | La maîtrise n’est pas démontrée ; le périmètre ou le socle doit être corrigé. |

La recommandation issue de la conception est devenue un **GO conditionnel** après la [contre-validation T4](./CONTRE_VALIDATION_VAGUE_T4.md). Elle autorise uniquement l’Étape 4 — Plan de livraison et protocole de validation ; ses conditions restent bloquantes avant toute construction.

## 2. Dossier de preuve assemblé

| Attendu Porte 3 | Référence | État | Ce qu’il reste à prouver |
|---|---|---|---|
| Architecture cible et frontières | [T1](./VAGUE_T1_CARTOGRAPHIE_SOCLE_FRONTIERES.md), [T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) | Conçu | Capacité réelle et choix d’évolution du monolithe. |
| Modèle de données et versions | [T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) | Conçu | Migration, RLS et rétention sur environnement représentatif. |
| Règles, Feu et fidélité Prévol/exécution | [T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) | Conçu | Tests des trois Playbooks et de chaque divergence interdite. |
| API, événements, idempotence, concurrence | [T2](./VAGUE_T2_DONNEES_REGLES_CONTRATS.md) | Conçu | Charge, rejeu, crash et annulation. |
| Autorisations et garde avant effet | [T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md) | Conçu | Tests de révocation et principal technique. |
| Modèle de menace et IA encadrée | [T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md) | Conçu | Évaluations adversariales, fournisseur et politique de données. |
| Audit, télémétrie et arrêt | [T3](./VAGUE_T3_SECURITE_IA_RESILIENCE.md) | Conçu | Alertes et exercices de suspension. |
| Coût, charge, latence et découpage | [T4](./VAGUE_T4_ESTIMATION_PORTE_3.md) | Paramétré | Mesures `T4-CAP`, tarifs et enveloppe approuvée. |
| Référence fonctionnelle | [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md) | Figée | Toute évolution majeure doit être versionnée. |

## 3. Périmètre dont la maîtrise est étudiée

La décision ne couvre que V1 : point d’entrée IA unique, trois Playbooks guidés, Prévol déterministe, préparation, tâches internes, brouillons, approbations et exceptions. Les protections majeures restent : Feu relationnel, capacités par rôle, garde juste avant effet, idempotence, audit minimal et suspension globale.

Sont exclus : constructeur libre de workflows, second CRM, attribution aléatoire, changement de pipeline silencieux et envoi externe autonome.

## 4. Réserves bloquantes ou conditionnelles

| ID | Réserve | Impact sur le verdict | Responsable proposé |
|---|---|---|---|
| `P3-RSV-01` | Résultats de capacité, latence, saturation, reprise et suspension (`T4-CAP-01..05`) absents | Bloque le GO de développement avec effets CRM | Engineering / plateforme |
| `P3-RSV-02` | Contre-validation sécurité T3 intégrée à T4, pas encore formellement conclue | Bloque tout élargissement de droit ou principal technique | Sécurité / architecture |
| `P3-RSV-03` | Fournisseur IA, prix, résidence, conservation et limites non choisis | Bloque l’activation de l’assistant IA | Produit / sécurité / achats |
| `P3-RSV-04` | Politique de rétention et données minimales à valider | Bloque l’enregistrement de toute phrase libre ou sortie IA | Produit / sécurité |
| `P3-RSV-05` | Preuve Azure 4.6 reportée à la fin de la Phase 5 | Bloque la décision de production dépendante du socle 4.6, pas la conception | Plateforme |
| `P3-RSV-06` | Sessions PME V2.1 reportées après production | N’empêche pas la faisabilité technique ; conditionne l’apprentissage post-lancement | Produit |
| `P3-RSV-07` | Verrou complet écarté pour la décision documentaire T4/Porte 3 | N’empêche pas la planification ; les contrôles d’implémentation et de production restent obligatoires | Engineering / QA |

## 5. Découpage recommandé si la Porte 3 devient positive

1. Tranches 0 et 1 : fondations sans effet et moteur déterministe.
2. Tranche 2 : premier Playbook interne sous Préparer, strictement gardé.
3. Tranches 3 et 4 : assistant IA encadré, brouillons et approbations.
4. Tranches 5 et 6 : extension, résilience et déploiement progressif.

Chaque tranche porte son flag, sa preuve et son retour arrière. Aucune tranche ne débloque l’envoi externe autonome.

## 6. Checklist de contre-validation

- [ ] Les cibles `S95 ≤ 3 s` et `Smax ≤ 9 s` sont confirmées ou révisées avec justification.
- [ ] Le plafond de 100 jobs et les lots de 25 sont validés ou remplacés par une limite mesurée.
- [ ] Les tests de crash, rejeu, concurrence et révocation ne créent aucun double effet.
- [ ] Le principal `automation-system` est limité, traçable et refusé hors origines admises.
- [ ] Les évaluations adversariales IA et le repli sans IA sont exécutés.
- [ ] La minimisation, la rétention et les conditions fournisseur IA sont approuvées.
- [ ] Les ADR 001 à 010 ont une décision explicite ou une réserve datée.
- [ ] Le registre des risques T4 a des propriétaires et jalons confirmés.
- [ ] La preuve Azure 4.6 et les sessions PME restent correctement reportées.

## 7. Verdict et prochaine décision

La Porte 3 est prononcée **`GO CONDITIONNEL`**. Le détail des réserves, des preuves et des limites d’autorisation est dans la [contre-validation T4](./CONTRE_VALIDATION_VAGUE_T4.md).

La prochaine action autorisée est l’**[Étape 4 — Plan de livraison et protocole de validation](./ETAPE_4_PLAN_LIVRAISON_VALIDATION.md)**. La prochaine décision est la **[Porte 4 — Prêt à construire](./PORTE_4_PRET_A_CONSTRUIRE.md)** ; elle reste impossible tant que la checklist de la section 6 et les conditions de la contre-validation ne sont pas satisfaites.

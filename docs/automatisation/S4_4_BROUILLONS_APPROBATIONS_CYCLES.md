# S4-4 — Brouillons, approbations et cycles de vie

> **Statut : CLÔTURÉE POUR DÉFINITION — prescriptions CV-S4-4-01 à CV-S4-4-07 appliquées au niveau contractuel ; aucun runtime intégré**  
> **Date d’ouverture :** 1er octobre 2026  
> **Dépendances :** [S4-1 — Noyau déterministe et Prévol](./S4_1_NOYAU_DETERMINISTE_PREVOL.md) ; [S4-2 — Nouveau prospect et tâche interne](./S4_2_NOUVEAU_PROSPECT_TACHE_INTERNE.md) ; [S4-3 — Assistant IA encadré](./S4_3_ASSISTANT_IA_ENCADRE.md) ; [RF-AUT-2.1](./REFERENCE_FONCTIONNELLE_AUTOMATISATION_V2_1.md)  
> **Backlog :** AUT-4401 à AUT-4406 dans [BL-AUT-4.1](./BACKLOG_DETAILLE_ETAPE_4.md)  
> **Décision de porte :** Porte 4 `GO avec réserves` limité à `P4-Lite` ; cette tranche de brouillons et approbations externes reste hors périmètre et non intégrée.

## 1. Objet

S4-4 définit le parcours qui transforme un Prévol admissible en brouillon lisible, puis en décision humaine traçable.
Il protège l’utilisateur contre deux confusions : un brouillon n’est pas une communication envoyée et une approbation
n’est pas une permission de contact ni une dérogation aux règles.

> **Préparer, faire relire, puis conserver une décision explicable — sans envoi autonome.**

En V1, l’état final obtenu par Automatisation est une décision humaine enregistrée sur une révision précise. Aucun état
de S4-4 ne déclenche de message, de connecteur ou de modification silencieuse du CRM.

## 2. Portée et limites

Le GO de définition couvre :

- le brouillon versionné, sa lecture et son empreinte matérielle ;
- la demande, la décision, le refus, l’expiration et l’invalidation d’approbation ;
- les gardes serveur conceptuelles à la préparation et à la décision ;
- les conflits de concurrence, l’idempotence, la suspension et les états incertains ;
- l’expérience légère de relecture pour une PME ;
- l’audit et les preuves minimisés.

Il ne couvre pas :

- un envoi par courriel, SMS, réseau social, API ou connecteur ;
- une génération de contenu par modèle IA réel ;
- une suppression, fusion ou modification automatique d’objet CRM ;
- une dérogation au Feu, à une permission, à une capacité, à une suspension ou à un Prévol expiré ;
- une migration, une route active, une persistance ajoutée ou un worker branché.

## 3. Parcours utilisateur V1

1. L’utilisateur ouvre un plan ou un Prévol et choisit de préparer un brouillon autorisé.
2. Marketteo affiche le canal de référence, le destinataire de référence, les contrôles, le contenu de la révision et ce
   qui n’a pas été fait.
3. Le préparateur demande une approbation ; l’approbateur relit la même révision.
4. L’approbateur approuve, refuse ou laisse expirer. Une modification crée une nouvelle révision et invalide l’accord
   précédent.
5. Un brouillon approuvé devient **prêt à remettre à l’utilisateur**, jamais prêt à être envoyé par Automatisation V1.

L’interface doit employer des libellés explicites : **Préparer un brouillon**, **Demander une approbation**,
**Approuver la révision** et **Ouvrir le contexte CRM**. Les verbes Envoyer, Lancer ou Relancer sont interdits dans ce
parcours V1.

## 4. Frontières de responsabilité

| Domaine | Responsabilité S4-4 | Ne décide jamais |
|---|---|---|
| Prévol S4-1 | Évaluer les règles, le Feu, les versions, le contexte et l’expiration | Contenu libre, approbation humaine, envoi |
| S4-2 | Préparer une tâche interne et son Passeport, lorsque admissible | Contact externe ou approbation à la place de l’humain |
| Assistant S4-3 | Expliquer un plan et conduire vers une préparation autorisée | Brouillon, destinataire, canal, droit ou décision |
| Brouillon S4-4 | Porter une révision lisible et son empreinte | Permission, Feu, capacité ou effet externe |
| Approbation S4-4 | Enregistrer la décision sur une révision exacte | Dérogation Rouge, envoi ou mutation CRM |
| Serveur | Revalider tenant, capacités, règles, Feu, versions et suspension | Interpréter une approbation comme un effet |
| CRM canonique | Rester propriétaire des objets, permissions, membres et historiques | Cycle Automation, sauf références canoniques |

## 5. Modèle conceptuel

### 5.1 Brouillon et révision

Un Brouillon Automation est un conteneur de préparation. Il contient une ou plusieurs révisions ordonnées, mais une seule
révision peut être active à la fois. Une modification ne remplace jamais une révision approuvée : elle crée une nouvelle
révision liée à la précédente.

~~~text
AutomationDraft {
  draft_id,
  organization_id_server,
  execution_or_plan_reference,
  subject_reference,
  current_revision_id,
  state,
  suspension_generation,
  correlation_id
}

AutomationDraftRevision {
  revision_id,
  draft_id,
  ordinal,
  protected_content_reference,
  material_fingerprint,
  recipient_reference,
  channel_code,
  purpose_code,
  playbook_version,
  ruleset_version,
  preflight_reference,
  preflight_fingerprint,
  created_by,
  expires_at,
  supersedes_revision_id?
}
~~~

Le contenu est visible seulement aux acteurs CRM autorisés dans la surface de relecture. L’audit, la télémétrie et les
événements ne conservent pas son texte ; ils utilisent une empreinte et des références canoniques minimales. Le choix
de protection et de durée de conservation reste une décision Données/Conformité avant implémentation.

### 5.2 Approbation

Une approbation est une décision immuable sur une révision, son empreinte et son contexte contrôlé. Elle ne peut être
réutilisée sur une autre révision ni sur un autre destinataire, canal, objet, Playbook, ruleset ou Prévol.

~~~text
AutomationApproval {
  approval_id,
  organization_id_server,
  draft_revision_id,
  expected_material_fingerprint,
  expected_preflight_fingerprint,
  expected_suspension_generation,
  approver_membership_id,
  decision_code,
  reason_code?,
  decided_at?,
  expires_at,
  version,
  idempotency_key,
  correlation_id
}
~~~

Les seuls decision_code V1 sont requested, approved, refused, expired et invalidated. Les remarques optionnelles
restent dans le canal CRM approprié et ne sont ni envoyées au modèle IA ni copiées dans l’audit Automation.

### 5.3 Empreinte matérielle

material_fingerprint est calculée côté serveur à partir de :

- l’identifiant et l’ordre de la révision ;
- l’empreinte du contenu protégé, sans en exposer le texte ;
- le destinataire et le canal de référence ;
- la finalité, le Playbook et le ruleset ;
- la référence et l’empreinte du Prévol ;
- le snapshot CRM et la décision de Feu applicables ;
- la version de la politique d’approbation.

La moindre différence invalide l’approbation. Un texte seulement reformatté est matériel s’il change l’empreinte
protégée ; le produit ne tente pas de deviner qu’un changement est sans importance.

## 6. Cycles de vie

### 6.1 Brouillon

~~~mermaid
stateDiagram-v2
    [*] --> non_created
    non_created --> prepared: préparation gardée
    prepared --> awaiting_approval: demande valide
    awaiting_approval --> approved: décision conforme
    awaiting_approval --> refused: refus
    awaiting_approval --> expired: échéance atteinte
    awaiting_approval --> invalidated: révision ou contexte modifié
    approved --> invalidated: révision, Feu, Prévol ou suspension modifiés
    approved --> expired: échéance atteinte
    prepared --> invalidated: suspension ou abandon
    awaiting_approval --> invalidated: suspension ou abandon
    approved --> invalidated: suspension
    invalidated --> prepared: nouvelle révision distincte
    refused --> prepared: nouvelle révision distincte
    expired --> prepared: nouvelle révision distincte
~~~

Une suspension ou un abandon rend la révision invalidated avec un motif codifié. L’état cancelled reste réservé aux
exécutions et aux jobs, conformément à RF-AUT-2.1 ; aucun état de brouillon n’a de transition vers envoyé dans la V1.

### 6.2 Approbation

~~~mermaid
stateDiagram-v2
    [*] --> requested
    requested --> approved: empreinte et garde conformes
    requested --> refused: décision humaine
    requested --> expired: horloge dépassée
    requested --> invalidated: contexte ou révision modifiés
    approved --> invalidated: toute divergence ultérieure
~~~

Une transition est atomique au niveau du contrat : deux décisions concurrentes ne peuvent pas toutes deux gagner. La
seconde reçoit version_conflict, approval_invalid ou approval_expired et relit l’état courant.

## 7. Règles fonctionnelles non négociables

1. Un Feu Rouge bloque la préparation d’un brouillon de contact. Une approbation ne peut jamais l’abaisser.
2. Un Feu Jaune prépare au plus une vérification ou une tâche interne ; il ne prépare pas de brouillon de contact.
3. Un Feu Vert permet une préparation, jamais un envoi.
4. Une décision approved ne vaut que pour la révision, l’empreinte, l’organisation, le canal, le destinataire de
   référence, les versions et la fenêtre d’expiration contrôlés.
5. Modifier le contenu, le destinataire, le canal, la finalité, le Playbook, le ruleset, le Prévol, le snapshot CRM ou
   la suspension invalide l’approbation.
6. La garde serveur relit la capacité, la portée CRM, la qualité de membre, le Feu, la permission, le Prévol, les
   versions et la suspension avant la création du brouillon puis avant l’enregistrement d’une approbation.
7. Une approbation expirée, refusée ou invalidée — y compris par suspension — ne redevient jamais valide ; seule une nouvelle révision
   peut être soumise.
8. L’absence, la révocation ou l’inactivité de l’approbateur ouvre une exception ou empêche la demande ; aucune
   réattribution aléatoire n’est admise.
9. Une erreur d’écriture ambiguë devient to_verify. Le serveur relit l’approbation par clé d’idempotence, révision et
   corrélation avant toute nouvelle tentative.
10. L’approbation enregistrée termine le périmètre Automation V1 : ouvrir le contexte CRM est permis, envoyer par un
    connecteur Automation ne l’est pas.

## 8. Capacités et séparation des rôles

| Action | Capacité logique requise | Garde complémentaire | Résultat V1 |
|---|---|---|---|
| Consulter un brouillon | automation:drafts:read + portée CRM | Tenant et objet lisibles | Lecture seulement |
| Préparer une révision | automation:drafts:prepare + capacité CRM source | Prévol courant, Feu admissible, Playbook actif | Brouillon prepared |
| Demander une approbation | automation:approvals:request | Révision active et non expirée | Approval requested |
| Approuver ou refuser | automation:approvals:decide + portée CRM | Empreinte exacte, garde fraîche, membre actif | Décision enregistrée |
| Invalider ou expirer | Système contrôlé ou capacité de gestion | Motif codifié, version attendue | État explicable |
| Suspendre | automation:playbooks:suspend | Portée et génération contrôlées | Aucun nouvel effet |

La politique par défaut exige un approbateur distinct du préparateur pour une communication de contact. Une PME
mono-utilisateur peut choisir une politique organisationnelle versionnée de single_operator_approval avant toute
préparation. Cette exception de séparation est auditée, ne donne aucun droit d’envoi et ne peut jamais contourner le
Feu, la permission, l’expiration, la suspension ou la garde serveur.

## 9. Garde, idempotence et suspension

### 9.1 Double garde

Le serveur vérifie à la préparation puis à la décision :

~~~text
tenant_same
actor_and_approver_active
automation_capability_current
crm_scope_current
playbook_and_ruleset_current
preflight_current_and_unexpired
snapshot_and_material_fingerprint_current
relationship_fire_and_permission_admissible
suspension_generation_current
idempotency_key_and_expected_version_valid
~~~

Une divergence gagne toujours sur une décision passée. Elle produit blocked, invalidated, exception ou to_verify ; jamais
une approbation forcée.

### 9.2 Suspension et reprise

Une suspension globale, d’organisation ou de Playbook :

1. bloque toute nouvelle préparation et demande d’approbation ;
2. invalide la possibilité de décider sur une demande en attente ;
3. conserve brouillons, révisions, approbations et audit pour explication ;
4. annule les futurs travaux non commencés si un worker les porte, tout en laissant la révision et l’approbation
   Automation dans l’état invalidated ;
5. exige un nouveau Prévol et une nouvelle révision après reprise lorsque le contexte a changé.

La reprise ne réactive jamais une approbation antérieure.

## 10. Contrats conceptuels

Ces commandes seront implémentées seulement après la Porte 4. Elles refusent les champs inconnus et déterminent
organization_id depuis le contexte serveur.

| Commande | Entrée minimale | Sortie sans effet V1 | Refus principal |
|---|---|---|---|
| prepare_draft | Prévol courant, sujet, canal, révision attendue, clé | Brouillon prepared + empreinte | fire_blocked, preflight_stale |
| request_draft_approval | Brouillon/révision, expiration, version attendue, clé | Approval requested | approval_invalid, plan_expired |
| decide_draft_approval | Approbation, empreintes attendues, décision, raison codifiée, clé | approved ou refused enregistré | version_conflict, approval_expired |
| invalidate_draft_revision | Révision, motif codifié, version attendue | Brouillon/approbation invalidated | version_conflict |
| expire_draft_approval | Horloge serveur, identifiant, version attendue | État expired | approval_invalid |
| suspend_automation_scope | Portée, motif, génération attendue | Suspension persistée conceptuellement | capability_missing |

Les événements métier prévus sont automation.draft.prepared.v1, automation.draft.revised.v1,
automation.approval.requested.v1, automation.approval.recorded.v1, automation.approval.invalidated.v1,
automation.approval.expired.v1 et automation.draft.invalidated.v1. Ils n’incluent ni contenu, ni destinataire, ni
coordonnée, ni texte de rejet.

## 11. Séquences de référence

### 11.1 Préparer puis approuver sans envoi

~~~mermaid
sequenceDiagram
    participant U as Préparateur
    participant S as Serveur
    participant R as Règles/Prévol
    participant D as Brouillon
    participant A as Approbateur
    U->>S: Préparer la révision
    S->>R: Garde : tenant, capacité, Feu, versions, suspension
    R-->>S: Prévol admissible et courant
    S->>D: Créer révision + empreinte
    D-->>U: Brouillon prepared
    U->>S: Demander approbation
    S->>D: Créer approval requested
    A->>S: Décider sur empreinte exacte
    S->>R: Rejouer la garde fraîche
    alt contexte identique
        S->>D: Enregistrer approved
        D-->>A: Décision visible, aucun envoi
    else divergence
        S->>D: Invalider
        D-->>A: Nouvelle révision requise
    end
~~~

### 11.2 Modification et concurrence

~~~mermaid
sequenceDiagram
    participant E as Éditeur
    participant S as Serveur
    participant D as Brouillon
    participant A1 as Approbateur 1
    participant A2 as Approbateur 2
    E->>S: Modifier la révision
    S->>D: Créer révision N+1 ; invalider N
    A1->>S: Approuver N
    S-->>A1: approval_invalid
    par deux décisions sur N+1
        A1->>S: Approuver N+1 version v
        A2->>S: Refuser N+1 version v
    end
    S->>D: Une décision atomique gagne
    S-->>A2: version_conflict ou état courant
~~~

## 12. Exceptions et récupération

| Situation | État | Réponse sûre |
|---|---|---|
| Feu Rouge ou permission devenue invalide | blocked ou invalidated | Aucun brouillon de contact ; expliquer la règle |
| Prévol, règle ou snapshot obsolète | invalidated | Nouveau Prévol et nouvelle révision |
| Brouillon modifié | invalidated | Conserver la révision précédente ; demander une nouvelle lecture |
| Approbateur inactif ou sans portée | exception | Choix humain d’un approbateur actif, sans transfert automatique |
| Expiration | expired | Nouvelle révision et nouvelle demande |
| Suspension | invalidated | Conserver la preuve ; aucune reprise silencieuse |
| Deux décisions simultanées | version_conflict | Une seule décision terminale ; relecture de l’état |
| Timeout après écriture possible | to_verify | Recherche idempotente avant toute reprise |
| Brouillon non conforme à la politique | refused ou blocked | Motif codifié, aucune modification implicite |

## 13. Audit, données et télémétrie

L’audit minimal peut conserver : organisation résolue, acteur, rôle logique, références de brouillon/révision,
empreintes, décision, motif codifié, versions, expiration, génération de suspension et corrélation.

Sont interdits dans l’audit, la télémétrie et les journaux d’erreur : texte du brouillon, destinataire, courriel,
numéro, contenu de message, phrase utilisateur, réponse IA brute, note CRM, preuve brute de permission et secret.

Les métriques agrégées couvrent : brouillons préparés, approbations demandées/approuvées/refusées/invalidées/expirées,
conflits de version, to_verify, suspensions et âge des demandes. Elles ne portent aucun libellé libre ni UUID métier.

## 14. Preuves et critères d’acceptation

| Preuve | Scénario | Oracle | Niveau actuel |
|---|---|---|---|
| PV-FUN-04 | Brouillon de contact admissible | Brouillon visible, zéro appel de connecteur, zéro envoi | D1 défini |
| PV-APP-01 | Approbation d’une révision exacte | Empreintes, canal, référence, versions et expiration concordent | D1 défini |
| PV-APP-02 | Modification après décision | Accord invalidé, nouvelle révision requise | D1 défini |
| PV-APP-03 | Expiration | Décision et action ultérieure impossibles | D1 défini |
| PV-CONC-01 | Deux approbations concurrentes | Une seule transition gagnante | D1 défini |
| PV-CONC-02 | Suspension pendant un lot | Aucune nouvelle décision après arrêt | D1 défini |
| PV-AUD-02 | Décision auditée | Identité, version, portée et raison sans contenu sensible | D1 défini |
| PV-OPS-02 | Génération de suspension | Garde finale bloque tout effet futur | D1 défini |

Les preuves D2/D3, l’environnement isolé et l’inspection des traces sont requis après la Porte 4. Les preuves D1 ne
représentent pas une approbation réellement exécutée.

## 15. Definition of Ready et Definition of Done

### Definition of Ready

- S4-1, S4-2 et S4-3 sont figées pour leur définition ;
- politique d’approbation, de séparation éventuelle et d’expiration validée Produit/Sécurité ;
- capacités CRM et Automatisation cibles arrêtées ;
- règles de protection et de rétention du contenu validées Données/Conformité ;
- fixtures synthétiques avec Vert, Jaune, Rouge, révocation, suspension et concurrence disponibles ;
- aucun connecteur d’envoi ni fournisseur IA réel requis.

### Definition of Done de la définition

- AUT-4401 à AUT-4406 sont reliés à un état, un contrat, un oracle et une preuve ;
- brouillon, révision, empreinte, approbation et invalidation sont distingués ;
- aucune approbation ne peut déroger au Feu ou produire un envoi ;
- double garde, expiration, suspension, idempotence, concurrence et to_verify sont définis ;
- données interdites dans l’observabilité listées ;
- parcours PME et libellés sans ambiguïté fixés ;
- Porte 4 et une future décision d’intégration restent explicitement nécessaires.

## 16. Prescriptions appliquées au niveau contractuel

Les prescriptions de contre-validation sont fermées dans cette définition, ses contrats, ses cycles et ses oracles.
Elles ne constituent pas une preuve runtime : aucune table, API, persistance, worker, connecteur ou envoi n’a été
créé.

| Prescription | Application figée dans S4-4 | Preuve runtime restante |
|---|---|---|
| CV-S4-4-01 | États de brouillon alignés sur RF-AUT-2.1 ; suspension = invalidated, cancelled réservé à l’exécution | PV-APP-03 et PV-OPS-02 |
| CV-S4-4-02 | Approved est une décision enregistrée, sans état ni commande d’envoi | PV-FUN-04 |
| CV-S4-4-03 | Material fingerprint serveur lie contenu protégé, référence, canal, versions et Prévol | PV-APP-01 et PV-APP-02 |
| CV-S4-4-04 | Politique de séparation versionnée ; single_operator_approval limité et sans droit d’envoi | PV-APP-01 et revue de capacité |
| CV-S4-4-05 | Feu, permission, capacités, Prévol et suspension relus à la double garde | PV-FUN-04 et PV-OPS-02 |
| CV-S4-4-06 | Version attendue, idempotence, conflit et to_verify imposés | PV-CONC-01 et PV-CONC-02 |
| CV-S4-4-07 | Contenu protégé ; audit, événements et métriques réduits aux empreintes et codes | PV-AUD-02 |

### 16.1 CV-S4-4-01 — Cycle compatible avec la référence figée

Les seuls états fonctionnels d’un brouillon sont non_created, prepared, awaiting_approval, approved, refused, expired et
invalidated. Une suspension, un abandon ou une divergence utilise invalidated avec un reason_code ; cancelled reste
exclusivement l’état d’une exécution ou d’un job. Une nouvelle tentative crée toujours une nouvelle révision prepared.

### 16.2 CV-S4-4-02 — Aucune transition vers un envoi

Approved signifie que l’accord humain a été enregistré sur une révision exacte. Le contrat ne contient ni send_draft, ni
connector, ni destinataire de transport, ni job d’expédition. Le seul prolongement V1 est Ouvrir le contexte CRM ; tout
futur envoi nécessitera une référence fonctionnelle, un contrat, une garde et une décision de porte distincts.

### 16.3 CV-S4-4-03 — Empreinte matérielle et invalidation

Material fingerprint est calculée côté serveur et couvre le contenu protégé, la référence de destinataire, le canal, la
finalité, les versions, le Prévol, le snapshot CRM, le Feu applicable et la politique d’approbation. Une décision qui ne
porte pas l’empreinte courante est rejetée ou invalidée ; elle ne peut pas être réparée en place.

### 16.4 CV-S4-4-04 — Séparation adaptée aux PME

La règle par défaut est préparateur distinct de l’approbateur. Single_operator_approval est une politique
d’organisation explicite, versionnée et auditée, disponible seulement lorsqu’aucun second approbateur actif n’est
désigné. Elle autorise une décision enregistrée sans jamais autoriser un envoi, une dérogation au Feu ou une capacité
supplémentaire.

### 16.5 CV-S4-4-05 — Garde d’approbation non dérogeable

La demande et la décision relisent tenant, membre, capacité Automation, portée CRM, Playbook, ruleset, Prévol,
snapshot, Feu, permission, empreinte, expiration et génération de suspension. Rouge, absence de permission admissible,
révocation ou divergence gagnent toujours sur une décision passée.

### 16.6 CV-S4-4-06 — Concurrence et résultat incertain

Toute transition porte une version attendue et une clé d’idempotence. Deux décisions concurrentes ne peuvent produire
qu’un seul état terminal ; une réponse perdue ou un timeout mène à to_verify puis à une recherche par révision,
empreinte, clé et corrélation avant tout rejeu.

### 16.7 CV-S4-4-07 — Contenu et observabilité minimisés

Le contenu n’est disponible que dans la surface CRM autorisée et n’est jamais copié dans l’audit, les événements, les
métriques ou les journaux d’erreur. Ces canaux ne portent que références minimales, empreintes, codes, versions,
expirations, génération et corrélation.

## 17. Risques et décisions ouvertes

| ID | Risque ou décision | Réponse avant intégration |
|---|---|---|
| S4-4-R01 | Approbation confondue avec permission ou envoi | Libellés V1, garde et test PV-FUN-04 |
| S4-4-R02 | Révision approuvée puis modifiée | Empreinte, nouvelle révision, invalidation PV-APP-02 |
| S4-4-R03 | PME mono-utilisateur bloquée | Politique versionnée single_operator_approval, sans droit d’envoi |
| S4-4-R04 | Approbations concurrentes contradictoires | Version attendue, transition atomique, PV-CONC-01 |
| S4-4-R05 | Donnée sensible dans audit | Empreinte et codes seulement, PV-AUD-02 |
| S4-4-R06 | Suspension contournée par un travail en attente | Génération relue par la garde, PV-CONC-02 |
| S4-4-R07 | Ambiguïté d’écriture d’une décision | to_verify et relecture par clé, jamais retry aveugle |
| S4-4-R08 | Politique de protection du contenu insuffisamment décidée | Décision Données/Conformité avant persistance |

## 18. Décision et suite

S4-4 est **clôturée pour sa définition** dans [CONTRE-VALIDATION-S4-4](./CONTRE_VALIDATION_S4_4.md). Les prescriptions
CV-S4-4-01 à CV-S4-4-07 sont appliquées dans les états, contrats, gardes, oracles et règles de données.

Les preuves D2/D3 restent à produire : PV-FUN-04, PV-APP-01..03, PV-CONC-01..02, PV-AUD-02 et PV-OPS-02 devront être
exécutées après la Porte 4. Aucun runtime, envoi, connecteur, API ou persistance n’est autorisé par cette clôture.

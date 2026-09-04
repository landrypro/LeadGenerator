# Phase 3 — Cœur CRM

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Phase | 3 — Cœur CRM |
| Version | 1.2 — 3.1 clôturé avec réserve, spécifications 3.2 validées |
| Prérequis | Phase 2.5 livrée ; verrou qualité local 2.6 vert ; recette multi-instance 2.6 différée au staging |
| Statut | 3.1 clôturé avec réserve — 3.2 en attente du GO d’implémentation |
| Date | 4 septembre 2026 |

## 1. Objet

La phase 3 transforme le socle de conformité livré en phase 2 en outil commercial utilisable au quotidien. Elle ajoute l’acquisition CSV réelle, le suivi commercial Kanban, les activités, les tâches, les opportunités et la fondation bilingue, sans assouplir les règles de provenance, permission, conservation, isolation d’organisation ou conformité Google.

Les éléments suivants ne sont **pas reconstruits** : établissement prospect, personnes de contact, canaux, provenance, permission par canal, ajout contrôlé depuis Google, `place_id`, quotas Google Redis, audit transactionnel et Row-Level Security. Ils deviennent les prérequis des nouveaux parcours.

Les besoins fournis comportaient deux doublons : « pipeline » correspond au Kanban et « activités, tâches et rappels » forme un module unique. Ils sont regroupés afin de conserver des livraisons testables.

## 2. Périmètre

### Inclus

- import CSV d’une organisation : dépôt temporaire, aperçu, correspondance de colonnes, validation, confirmation explicite, déduplication, quarantaine et rapport interne ;
- pipeline Kanban à neuf étapes, responsable, priorité, étiquettes, prochaine action et transitions versionnées ;
- journal d’activités, notes assainies, appels déclaratifs, tâches, échéances, rappels et vues personnelles ;
- opportunités liées à un prospect, avec montant/devise, échéance, état et issue gagnée/perdue ;
- réemploi des fiches prospects, contacts, canaux, provenances et permissions déjà livrés ;
- hydratation Google directe et ponctuelle lorsque les capacités et règles Google l’autorisent ;
- résolution serveur de Ville + région facultative + Pays, avec confirmation explicite et mode coordonnées avancé ;
- fondation de traduction `fr-CA` / `en-CA`, préférences et courriels ;
- audits, RLS, tests, documentation utilisateur, technique et recette QA.

### Exclus

- scraping LinkedIn, Facebook ou de tout réseau social ;
- tout connecteur social ou API publique avant la revue contractuelle dédiée ;
- export de données descriptives Google, téléphone ou site Web provenant de Google ;
- import sans aperçu et confirmation, fusion approximative automatique ou permission de contact implicite ;
- envoi automatisé, séquence commerciale, IA de scoring, marketing ou SMS ;
- facturation, plans, paiement, taxes, portail client ou webhooks de paiement ;
- tableau de bord complet et connecteurs de production, reportés à la phase 4.

## 3. Découpage proposé

| Incrément | Résultat livré | Dépendances |
| --- | --- | --- |
| **3.1 — Import CSV conforme** | Fichier temporaire, aperçu, mapping, validation, confirmation idempotente, quarantaine et rapport | 2.5 provenance/conservation ; 2.6 Redis/audit |
| **3.2 — Pipeline Kanban** | Neuf étapes, transitions contrôlées, assignation, filtres, conflits et historique | 2.5 prospects ; 2.4 audit |
| **3.3 — Activités, tâches et rappels** | Chronologie, tâches, échéances, rappels et droits | 3.2 ; audit |
| **3.4 — Opportunités** | Montants, échéances, issues et lien avec le pipeline | 3.2 et 3.3 |
| **3.5 — Lieux, Google et bilinguisme** | Résolution Ville/Région/Pays, hydratation directe et fondation `fr-CA`/`en-CA` | 2.6 ; écrans phase 3 |
| **3.6 — Verrou qualité de phase** | Recette regroupée, sécurité, accessibilité, RLS, non-régression Google et documentation | 3.1 à 3.5 |

Chaque incrément reçoit ses spécifications détaillées, décisions propres, implémentation, tests et rapport avant le suivant. La recette métier globale de phase 3 est exécutée après 3.6 ; les tests automatisés restent obligatoires à chaque incrément.

## 4. Règles métier transversales

### 4.1 Import CSV et acquisition

1. Un import appartient à une organisation et à une acquisition approuvée, dont fournisseur et contrat sont actifs lorsqu’ils sont requis.
2. Le fichier est privé et temporaire. Il est supprimé selon la politique, après succès, annulation ou échec ; son contenu brut ne va ni dans les journaux ni dans l’audit.
3. L’aperçu est limité, sans persistance métier et sans création de prospect. Le mapping est confirmé par un utilisateur autorisé.
4. Seules les catégories déclarées et admises par l’acquisition sont importables. Une colonne ou valeur non conforme est rejetée ou mise en quarantaine avec motif lisible.
5. La confirmation est idempotente : un rejeu réseau, fichier ou ligne identique ne crée pas de doublon.
6. La déduplication exacte est automatisable sur les identifiants autorisés. Une proximité de nom, adresse ou personne déclenche une revue humaine, jamais une fusion silencieuse.
7. Une provenance est créée pour chaque donnée persistée. Un canal importé reçoit `unknown` par défaut et ne devient jamais un droit de contacter.

### 4.2 Pipeline commercial

Les codes système stables sont `new`, `qualifying`, `qualified`, `contacted`, `opportunity`, `proposal_sent`, `negotiation`, `won` et `lost`. Libellé, couleur et ordre sont configurables par organisation sans changer les codes ni casser les rapports.

Tout déplacement porte la version courante du prospect. Un conflit retourne `409` et ne remplace jamais une transition concurrente. Le passage à `lost` exige un motif contrôlé. Les étapes `won` et `lost` sont terminales mais réversibles selon le droit. Chaque transition est auditée et ajoute un élément d’historique commercial interne.

### 4.3 Activités, tâches et opportunités

- Une activité est volontaire, porte un prospect, un auteur, un type, une date et éventuellement une note assainie. Aucun contenu Google ne crée d’activité automatique.
- Une tâche comporte responsable, échéance, priorité, statut et rappel. Son retard est calculé côté serveur dans le fuseau de l’organisation, sans notification externe en phase 3.
- Une opportunité est facultative, liée à un prospect et une étape compatible. Son montant est une donnée CRM interne avec devise ISO ; elle ne constitue pas une facture.

### 4.4 Contact, Google et lieu

Les canaux gardent provenance et permission propres. L’interface bloque une action de contact automatisée sur un canal `unknown` ou opposé ; un appel/courriel déclaré n’est pas une preuve de permission.

Google reste limité : un Text Search explicite, vingt résultats, sans pagination, téléphone ni site Web. `place_id` et nom interne CRM restent séparés. Une fiche peut demander un affichage direct autorisé, sans copier la réponse dans PostgreSQL, logs, audit ou navigateur au-delà de la session.

La résolution de lieu accepte Ville, région/province/État facultatif et Pays. Elle ne lance aucun Text Search Google, demande une confirmation en cas d’ambiguïté et conserve les coordonnées manuelles comme mode avancé.

### 4.5 Langues

La langue suit : utilisateur > organisation > `fr-CA`. Les messages API gardent des codes stables ; l’interface et les courriels utilisent des clés traduites. Codes de rôle, étape, statut et permission ne sont pas traduits en base. Toute nouvelle chaîne visible de phase 3 est livrée en `fr-CA` et `en-CA`.

## 5. Modèle de données et interfaces attendus

| Famille | Données minimales | Protections |
| --- | --- | --- |
| Import | acquisition, fichier temporaire, mapping, état, compteurs, commande, rapport | RLS, TTL/suppression, idempotence, audit |
| Quarantaine | référence opaque, motifs codés, décision humaine | contenu brut interdit dans logs/audit |
| Pipeline | catalogue d’étapes, étape prospect, historique de transition | codes stables, version, audit |
| Activité/tâche | prospect, auteur/responsable, type, dates, statut, note assainie | RLS, suppression logique, audit |
| Opportunité | prospect, état, montant décimal, devise, échéance, issue | RLS, transition, audit |
| Lieu | requête éphémère, choix confirmé, coordonnées CRM | cache borné, aucune recherche implicite |
| Traduction | clés applicatives, préférences et gabarits courriel | aucune donnée utilisateur dans les clés |

Les routes suivent les conventions existantes : JSON UTF-8, erreur avec `code`, `message`, `request_id`, curseurs signés, CSRF pour mutations, `409` pour conflits et `422` pour validation.

## 6. Sécurité et observabilité

- PostgreSQL RLS reste la frontière d’organisation ; aucune portée n’est fournie par le navigateur.
- Les autorisations sont contrôlées côté serveur sur toute lecture ou mutation.
- Un fichier est borné en taille, encodage, lignes et colonnes ; aucune macro ni formule n’est exécutée.
- Journaux JSON et métriques 2.6 excluent contenu CSV, coordonnées détaillées, courriels, texte de note, résultats Google et secrets.
- L’audit décrit l’action et ses motifs minimisés ; il ne recopie ni fichier ni données personnelles hors modèle approuvé.
- Tout nouveau worker, stockage, géocodeur ou connecteur est spécifié avec ses coûts, panne et rétention avant son ajout.

## 7. Validation de phase

1. Un CSV conforme produit un aperçu sans donnée CRM, puis une confirmation idempotente et un rapport.
2. Une colonne interdite, source inactive ou ligne douteuse est rejetée ou mise en quarantaine.
3. Aucune fusion approximative n’est automatique et aucun canal importé ne devient autorisé implicitement.
4. Une transition Kanban concurrente retourne un conflit ; Perdu exige un motif et chaque transition est auditée.
5. Activités, tâches, rappels et opportunités respectent rôles, RLS et suppression logique.
6. Les contenus Google ne sont pas persistés, exportés ou utilisés pour remplir un canal.
7. La résolution de lieu est explicite, bornée et séparée de Text Search.
8. Tout écran/courriel de phase 3 existe en français canadien et anglais canadien.
9. Ruff, mypy, pytest réel, Alembic, ESLint, Vitest/axe, build, verrou local et Azure sont verts.
10. La recette multi-instance 2.6 et les preuves Azure 2.6 sont archivées avant préproduction.

## 8. Seize décisions validées

1. La phase 3 est découpée en 3.1 Import CSV, 3.2 Kanban, 3.3 Activités/Tâches, 3.4 Opportunités, 3.5 Lieux/Google/Bilinguisme et 3.6 Verrou final.
2. L’import CSV est le premier incrément fonctionnel, conformément à la priorité « immédiatement après le socle prospect » ; il ne démarre jamais sans acquisition conforme.
3. Tout fichier importé est privé, temporaire, borné et supprimé selon la politique ; son contenu brut est interdit dans logs, métriques et audit.
4. Aperçu, mapping et confirmation sont distincts ; seule la confirmation crée des données CRM.
5. La confirmation est idempotente et auditée ; un rejeu réseau ne duplique aucune ligne.
6. La déduplication exacte est automatisable ; toute correspondance approximative est mise en revue humaine.
7. Toute donnée/canal importé a une provenance ; tout canal démarre `unknown` sans preuve autorisée et vérifiable.
8. Le Kanban utilise les neuf codes système définis, avec libellé, couleur et ordre configurables par organisation.
9. Une transition Kanban porte une version, est auditée, retourne `409` en conflit et exige un motif codé pour `lost`.
10. Activités, tâches et rappels sont des actions internes explicites ; aucun n’est créé automatiquement depuis Google ou import.
11. Les opportunités sont internes, facultatives, liées à un prospect ; elles ne sont ni devis comptable ni facture.
12. Prospects, personnes, canaux, provenance, permissions et hydratation Google réemploient le socle 2.5/2.6 ; aucune donnée Google descriptive n’est ajoutée au CRM.
13. Ville + région facultative + Pays est résolu côté serveur, confirmé en ambiguïté et séparé de Google Places ; les coordonnées manuelles restent disponibles.
14. `fr-CA` et `en-CA` sont obligatoires pour chaque chaîne visible ou courriel de phase 3 ; préférence utilisateur, puis organisation, puis français.
15. RLS, permissions, audit append-only, CSRF, `no-store` Google, quotas Redis et journaux fermés sont non négociables.
16. Aucun incrément n’est clôturé sans tests et rapport ; la clôture globale exige la recette 2.6 en staging, un verrou sans skip et Azure vert.

## 9. Décision de sortie

Les seize décisions de cadrage de la phase 3 ont été validées par le responsable produit le 26 août 2026. Les spécifications, l’implémentation et la recette locale de **3.1 — Import CSV conforme réel** sont terminées. La clôture avec réserve a été prononcée le 4 septembre 2026 ; la recette multi-instance 2.6 en staging et la preuve Azure restent obligatoires avant préproduction.

Le GO de rédaction des spécifications détaillées de **3.2 — Pipeline Kanban** a été accordé. Les seize décisions disponibles dans [`PHASE_3_2_SPECIFICATIONS_DETAILLEES.md`](PHASE_3_2_SPECIFICATIONS_DETAILLEES.md) ont été validées le 4 septembre 2026. Un GO d’implémentation explicite reste nécessaire avant toute modification de code 3.2.

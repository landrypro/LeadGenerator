# Phase 2.4.2 — Rapport d’implémentation de la couverture des mutations

| Métadonnée | Valeur |
| --- | --- |
| Produit | Marketteo CRM |
| Incrément | 2.4.2 — Couverture des mutations existantes |
| Date | 9 août 2026 |
| Statut technique | Implémenté et vérifié automatiquement |
| Migration | `20260809_0007`, tête Alembic |
| Changement API ou visuel | Aucun |
| Recette utilisateur | Regroupée à la fin de 2.4.3, décision produit validée |

## 1. Résultat livré

Les mutations d’organisation, d’appartenance, d’invitation, de provisioning, d’acceptation et de changement
d’organisation active utilisent désormais une unité de travail auditée. La mutation et ses événements partagent la
même session SQLAlchemy et un seul `commit`. Une erreur d’audit quitte l’unité de travail sans commit et annule donc
la transition métier.

SMTP reste délibérément entre deux transactions : la demande est validée avant l’envoi, puis le statut de livraison
est finalisé dans une deuxième transaction auditée. Redis reste post-commit pour ne pas étendre la transaction
PostgreSQL à un système externe.

## 2. Architecture réalisée

- factories d’unités de travail auditées pour les contextes locataire, plateforme, acteur et acceptation anonyme ;
- gateways de mutation liées à une `AsyncSession`, sans ouverture de transaction et sans `commit` interne ;
- `AuditRecorder` lié à la même session que la mutation ;
- construction applicative centralisée d’événements avec acteur, organisation, `request_id` et `correlation_id`
  provenant uniquement du serveur ;
- établissement tardif du contexte locataire après acceptation d’une invitation par un nouveau compte ;
- résultats SQL minimaux pour les anciennes et nouvelles valeurs, invitations remplacées et finalisations réelles ;
- compatibilité transitoire des anciens ports conservée seulement pour les doubles de test existants ; la composition
  de production injecte systématiquement les nouvelles unités de travail.

## 3. Contrats PostgreSQL

La migration `20260809_0007` ajoute des fonctions `SECURITY DEFINER` dédiées aux mutations auditées. Elles verrouillent
les lignes nécessaires, appellent les règles métier existantes et retournent uniquement les faits codifiés requis par
la politique de métadonnées. Les fonctions sont possédées par `prospect_rls_definer`, révoquées à `PUBLIC` et seulement
exécutables par `prospect_app`.

Les tests réels ont découvert que la politique RLS de lecture de 2.4.1 appelait `current_actor_id()` sans que le rôle
Web puisse exécuter cette fonction de contexte. La migration 0007 accorde ce droit minimal ; la fonction ne lit que la
valeur transactionnelle `app.actor_id` et ne donne aucun accès aux tables.

## 4. Événements branchés

- organisation modifiée ;
- rôle et statut d’une appartenance, avec deux événements corrélés lorsque les deux changent ;
- invitation membre créée, remplacée, renvoyée, finalisée ou révoquée ;
- organisation provisionnée et invitation initiale créée ;
- invitation initiale remplacée, renvoyée, finalisée ou révoquée ;
- invitation acceptée et organisation initiale activée ;
- préférence d’organisation active modifiée dans la nouvelle organisation.

Les refus, conflits, opérations inchangées et rejeux idempotents ne créent aucun événement. Les métadonnées ne
contiennent ni nom, courriel, mot de passe, jeton, donnée Google, coordonnée ni texte libre.

## 5. Preuves exécutées

### Backend et base réelle

- 135 tests non-intégration réussis, aucun échec ;
- 39 tests d’intégration PostgreSQL/Redis/Mailpit réussis au total ; 38 ont tourné sur la base locale persistante ;
- le scénario de bootstrap concurrent, qui exige une base sans Administrateur de plateforme, a été rejoué avec succès
  dans une base temporaire migrée depuis zéro puis supprimée, sans toucher au compte local existant ;
- les 5 tests PostgreSQL ciblés d’audit sont réussis, dont atomicité, RLS, append-only, double événement rôle+statut
  et finalisation rejouée sans doublon avec refus d’un rejeu divergent ;
- Mailpit réel : 1 test réussi après configuration explicite des ports locaux ;
- Alembic `current` : `20260809_0007 (head)` ;
- Alembic `check` : aucune opération supplémentaire détectée ;
- Ruff, Ruff format et mypy backend : conformes ;
- `git diff --check` : conforme hors avertissements de conversion LF/CRLF.

### Frontend et artefact

- ESLint : conforme ;
- Vitest : 29 fichiers et 126 tests réussis, exécutés en deux groupes pour tenir compte de la lenteur JSDOM locale ;
- build Vite : réussi ;
- audit npm : zéro vulnérabilité ;
- contrôles de confidentialité des sources navigateur et de l’artefact : conformes.

## 6. Critique experte finale

### 6.1 Atomicité et cohérence

Le point fort est la propriété explicite de la transaction par le cas d’utilisation. Les faits de transition sont
obtenus sous verrou et contrôlés avant le commit ; une réponse PostgreSQL incomplète provoque un rollback. Le risque
résiduel principal est la coexistence temporaire des méthodes de mutation historiques dans les ports de lecture pour
les anciens doubles de test. Elles ne sont pas utilisées par le conteneur de production et devront être supprimées
après migration complète des tests.

### 6.2 Sécurité et isolation

Les fonctions conservent un `search_path` fermé, un propriétaire non connectable et des droits d’exécution ciblés.
Le droit ajouté à `current_actor_id()` est nécessaire à RLS et ne donne pas de privilège de données. La lecture de
l’audit demeure séparée entre portée locataire et portée plateforme. Les tests d’intégration ont confirmé cette
isolation sur deux organisations.

### 6.3 Exploitabilité et suite

Le journal est maintenant alimenté, mais reste volontairement non consultable par l’utilisateur. 2.4.3 doit ajouter
les requêtes, curseurs, filtres autorisés, routes `no-store` et écrans accessibles sans contourner RLS. La recette
fonctionnelle cumulée 2.4.1–2.4.3 vérifiera alors les libellés et la visibilité réelle. Le cas local de bootstrap exige
une base éphémère et ne doit jamais conduire à supprimer l’Administrateur de plateforme d’une base de développement
active.

## 7. Conclusion

2.4.2 est techniquement prêt pour la définition de 2.4.3. Sa clôture fonctionnelle reste volontairement ouverte
jusqu’à la recette utilisateur cumulée prévue après l’interface de consultation.

# Incrément 2.5.5-D — Rapport d’implémentation

L’écran `/app/compliance/retention` livre les politiques de conservation, les revues, les holds et les déclarations
d’import. Les capacités serveur sont reflétées dans l’interface. Les mutations utilisent CSRF, idempotence et
confirmation ; les archivages restent logiques.

L’import est uniquement déclaratif : aucun champ fichier, dépôt, parsing, aperçu ou stockage de contenu brut. Un test
React vérifie explicitement l’absence de `input[type=file]` et la présence de l’avertissement utilisateur.

Aucune migration supplémentaire n’est requise. La migration `20260814_0011` et les routes de 2.5.4 sont réutilisées.

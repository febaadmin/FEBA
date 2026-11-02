# Matrice de tests par profil

| Test | Profil | Attendu | Obtenu | Statut | Preuve |
|---|---|---|---|---|---|
| Ouverture de toutes les pages, 1366 et 390 px | Les 5 | 0 erreur JS, 0 débordement | 0 et 0 | Réussi, local | `INVENTAIRE_PAGES.md` |
| Formulaires soumis à vide | Admin, enseignant, superadmin | Refus, message, 0 × 5xx | Refus et 0 × 5xx sur 92 pages, 50 formulaires. Message ajouté par PR 50 | Réussi, local | Sondage `boutons.mjs` |
| Parcours d'examen en 15 étapes | Enseignant, élève, parent | Du brouillon au transfert unique | Conforme | Réussi, local | Mission précédente |
| Types de questions | Enseignant, élève | Tous corrigés | Conforme | Réussi, local | `types.mjs` |
| Coupure réseau pendant une épreuve | Élève | Réponses conservées | Réponse retrouvée après rechargement | Réussi, local | `coupure.mjs` |
| Objectif : créer, modifier, historique, archiver, restaurer, recharger | Enseignant | Persistant | 201, 200, 200, 200 ; 1 carte après rechargement | Réussi, local | `obj.mjs` |
| Objectifs archivés cachés | Parent | Liste vide | Vide | Réussi, auto | `ObjectifEditionArchivageTests` |
| Objectif d'une autre classe | Enseignant | Refus | Refus | Réussi, auto | Idem |
| Création de classe | Admin | 201, visible | Conforme | Réussi, local | `crit.mjs` |
| Paiement et reçu | Admin | 201, reçu ouvert | 201 ; reçu généré 200, ouverture en onglet non observée | Partiel, local | `crit.mjs` |
| Devoir enseignant visible par l'élève de la classe | Enseignant, élève | Visible | Visible | Réussi, local | `crit.mjs`, `dev.mjs` |
| Recette en production des 5 profils | Les 5 | | Non exécutée | **Non testé** | Comptes à créer par l'établissement |
| Téléphone réel | Les 5 | | Non exécuté | **Non testé** | Viewport simulé seulement |
| Lecteur d'écran réel | Tous | | Non exécuté | **Non testé** | Attributs contrôlés seulement |

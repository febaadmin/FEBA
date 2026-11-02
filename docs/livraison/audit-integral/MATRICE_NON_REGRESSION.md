# Matrice de non-régression

État après la PR 53, en local sauf mention contraire.

| Domaine | Contrôle | Résultat |
|---|---|---|
| Backend PostgreSQL | CI | 2227 réussis, 3 ignorés, 0 échec |
| Backend SQLite | CI | 2219 réussis, 11 ignorés, 0 échec |
| Bulletin une page | CI | 24 réussis |
| Frontend | CI | 445 réussis, 65 fichiers |
| Pages | 245 ouvertures, 2 largeurs, 5 profils | 0 erreur JS, 0 débordement, seul 5xx : santé visio, sans serveur local |
| Parcours d'examen | 15 étapes | Réussi après correction de mon script, qui attendait « 8.00 » au lieu de « 8 » |
| Types de questions | 10 types | Réussi, notes partielles conformes aux réponses fausses voulues |
| Coupure réseau | Hors ligne, retour, rechargement | Réponse et chrono conservés |
| Objectifs, plans | Créer, modifier, archiver, restaurer, recharger | Réussi, relancé après la refonte |
| Compétences | Évaluer une classe, fiche, historique | Réussi |
| Fenêtres | Fond, Échap, focus | Réussi |

**Non rejoué après la refonte :** sondage de tous les formulaires, parcours classe, paiement et devoir (dernier passage avant la PR 52), import CSV et dépôt de fichier en navigateur.

**Défauts antérieurs distingués :** voir l'inventaire. Seule la régression de la PR 49 m'est imputable.

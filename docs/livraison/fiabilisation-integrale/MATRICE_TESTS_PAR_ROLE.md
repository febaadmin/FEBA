# Tests par rôle

| Parcours | Superadmin | Admin | Enseignant | Élève | Parent |
|---|---|---|---|---|---|
| Connexion | Local | Local | Local | Local | Local |
| Toutes les pages, 2 largeurs | Local | Local | Local | Local | Local |
| Sélecteur d'académie | Local | Absent | - | - | - |
| Notes | - | - | Local | Lecture | Lecture |
| Bulletins | - | Local | - | - | - |
| Paiements | - | Local | Refus | Lecture | - |
| Examens | - | - | Local | Local | Local |
| Messages | - | - | Local | - | Local |
| Annonces | - | Local | - | Lecture | Lecture |
| Refus, IDOR | - | PostgreSQL | PostgreSQL | PostgreSQL | PostgreSQL |
| **Production connectée** | **Non** | **Non** | **Non** | **Non** | **Non** |

Bloqué par l'absence de comptes de test en production, que je ne crée pas.

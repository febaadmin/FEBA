# Performance

| Route, ajout de 30 élèves et 60 notes | Avant | Après |
|---|---|---|
| `/api/grades/` | +120 requêtes | Stable, `VolumeTests` |
| `/api/auth/users/` | +30 | Stable |
| `/api/grades/student-summary/` | +150 | **Inchangé**, calcul officiel |

| Élément | Taille compressée |
|---|---|
| Entrée JS | 179,95 Ko, +5,8 Ko avec React Router 7 |

Tableaux de bord élève et parent : environ 67 requêtes, constantes.

**Non mesuré :** téléphone réel, nouveaux rendus React, fuites mémoire, charge.

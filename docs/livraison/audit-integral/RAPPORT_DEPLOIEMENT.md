# Déploiements du 02/11/2026

| PR | Commit | CI | Instantanés | Contrôle |
|---|---|---|---|---|
| #48 | `9db14cf` | 10 verts | Non relu | Commit, 0 migration, 0 traceback |
| #49 | `2918183` | 10 verts | Non relu | Commit, 0 traceback. A introduit la régression du fond des fenêtres |
| #50 | `96d4bc3` | 10 verts | `6e745d92`, `2af60c51` | Migration `suivi.0006` appliquée |
| #51 | `da2a3c1` | 10 verts | `2af60c51`, `7f707f00` | 7 conteneurs, 0 migration, 0 traceback |
| #52 | `d1ab9e0` | 10 verts après 2 échecs : ESLint sur mon test, puis l'isolation (A1) | Non relu | Déploiement réussi |
| #53 | `f25868c` | 10 verts | `e7b906bf`, `c7a15b2d` | 7 conteneurs, 0 migration, 0 traceback, 4 réponses 502 au redémarrage |

## Retour arrière

- Code : revert du commit, nouveau déploiement.
- framer-motion : revenir à la version 11 ramènerait le flash.
- Migration : `migrate suivi 0005` retire `archive_le` ; les archivages faits entre-temps seraient perdus.

## Non vérifié

- Restauration d'un instantané jamais testée : elle exige root.
- Pas de parcours connecté en production.

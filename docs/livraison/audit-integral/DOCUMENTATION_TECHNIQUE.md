# Documentation technique

Pile : Django 5.2, DRF, PostgreSQL, Celery, React et Vite, Tailwind, framer-motion 12, Recharts.

Références : `../../SUIVI_PEDAGOGIQUE.md`, `../../EXAMENS_EN_LIGNE.md`, `../../RAPPORTS_ET_ALERTES.md`, `../ARCHITECTURE_REFERENTIELS_COMPETENCES.md`, `DESIGN_SYSTEM_FEBA.md`.

## Ajouts de cette période

| Élément | Rôle |
|---|---|
| `suivi.0006` | Champ nul `Objectif.archive_le` |
| `objectifs/{id}/archiver/`, `desarchiver/` | Archivage réversible |
| `objectifs/?archives=1` | Liste des archives, personnel seulement |
| `utils/useFormulaire.js` | `useForm` avec message de validation |
| `utils/useLabelLinker.js` | Relie les libellés aux champs |
| `components/ui/Modal.jsx` | Rendu dans `body`, focus |

## Déploiement

Fusion sur `main`, CI, instantané Restic, déploiement. Vérifier ensuite le commit, les migrations et les journaux. Retour arrière : voir `RAPPORT_DEPLOIEMENT.md`.

## Tests

`cd frontend && npx vitest run`, `cd backend && pytest`.

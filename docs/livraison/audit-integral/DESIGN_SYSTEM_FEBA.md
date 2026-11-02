# Design system FEBA Academic Premium

Source : `frontend/src/index.css`, `frontend/tailwind.config.js`.

## Couleurs

| Rôle | Valeur |
|---|---|
| Navigation | `sidebar` #071D49, `sidebar-2` #0E2A63 |
| Action | `primary` #1D4ED8 |
| Accent | `secondary` #8B5CF6 |
| Marque | `feba-gold` #D89B16 |
| Succès, alerte, danger | Émeraude, ambre, rouge |
| Fond | #F4F6FB, `.fond-app` |

## Classes

| Classe | Usage |
|---|---|
| `.btn-primary`, `.btn-secondary`, `.btn-tertiaire`, `.btn-danger`, `.btn-succes`, `.btn-icone` | Boutons |
| `aria-busy="true"` sur un bouton | État de chargement |
| `.card`, `.carte-active`, `.bento` | Cartes et grille |
| `.input`, `.label`, `.badge` | Formulaires et étiquettes |
| `.nav-item`, `.nav-item-actif` | Menu |
| `.barre-haute` | En-tête |
| `.etat-vide`, `.skeleton` | États vide et de chargement |
| `.page-entree`, `.table-cartes` | Entrée de page, tableaux sur téléphone |

## Règles de mouvement

- Jamais d'opacité de départ nulle pour une page.
- Aucun fond animé, aucun éclat traversant l'écran.
- `prefers-reduced-motion` coupe les mouvements.
- Garder framer-motion en version 12 ou plus : `sansFlash.test.js` le contrôle.
- Une carte indicateur affiche sa valeur exacte, sans partir de 0.

## À ne pas faire

Coder en dur une couleur hors charte, utiliser `window.confirm`, importer `useForm` directement de react-hook-form (utiliser `utils/useFormulaire`).

# Refonte visuelle et animations

La refonte passe par la couche commune : toutes les pages en héritent sans réécriture. Elle ne remplace pas une revue page par page, qui reste partielle.

## Système de design

| Élément | Emplacement | Détail |
|---|---|---|
| Couleurs | `tailwind.config.js` | Primaire `#1D4ED8`, menu `#071D49`, or du logo conservé |
| Boutons | `index.css` `.btn*` | Survol, clic, focus, désactivé |
| Cartes, champs, badges | `index.css` | Ombres `carte`, `relief`, `fenetre` |
| Menu des 5 profils | `layouts/*Layout.jsx`, `.nav-item*` | Même état actif, barre or |
| Tableaux | `DataTable.jsx`, `.table-cartes` | Tri au clavier, cartes compactes sur téléphone |
| Fenêtres | `Modal.jsx`, `ConfirmDialog.jsx` | Rendu dans `body`, focus, Échap |
| Formulaires | `useFormulaire.js`, `useLabelLinker.js` | Message de validation, libellés reliés |
| Indicateurs | `StatCard.jsx`, `anime.jsx` | Valeur exacte, jamais de faux zéro |

## Animations

| Animation | Composant | Réduction de mouvement |
|---|---|---|
| Entrée de page | `AcademyScopedOutlet`, `.page-entree` | Coupée |
| Fenêtres | `Modal` | Via `MotionConfig` |
| Compteurs, anneaux, squelettes, cascade | `anime.jsx` | Oui |
| Carte d'objectif déplacée, objectif atteint | `TableauObjectifs` | Oui ; le glisser a une liste équivalente au clavier |
| Courbes | `Graphiques.jsx` | Coupées avec `useReducedMotion` |

## Neo Glass (PR 53)

Fond fixe et discret, cartes claires à ombre douce, tuiles d'icône en dégradé, en-tête vitré, couleurs hors charte retirées de 36 fichiers. Détail : `DESIGN_SYSTEM_FEBA.md`.

## Limites

- Pas de compteur animé sur `StatCard` : le test `academyBoot` interdit un faux zéro au chargement, et je ne l'ai pas affaibli.
- Une régression m'est imputable : l'animation d'entrée a capturé les fenêtres en PR 49, corrigé en PR 50.
- **Ce n'est pas 100 % des interfaces :** la couche commune couvre toutes les pages connectées, mais des styles propres à certaines pages subsistent, et le site public n'a pas été refondu.
- Non harmonisés à fond : Admissions, Fichiers, Transactions, couleurs des graphiques.

# Système de design FEBA

Une seule source par sujet. Ce qui ne figure pas ici n'est pas une règle : ne pas inventer une couleur ou un style local.

## 1. Où vivent les jetons

| Sujet | Fichier | Usage |
|---|---|---|
| Couleurs de marque, états, surfaces, texte, rayons, durées | `frontend/src/index.css` (`:root --feba-*`) et `frontend/tailwind.config.js` (`primary`, `feba.*`, `success`, `warning`, `info`, `danger`) | classes Tailwind et CSS |
| Composants de base | `frontend/src/index.css` (`@layer components`) | `.btn-primary`, `.btn-secondary`, `.btn-tertiaire`, `.btn-danger`, `.btn-succes`, `.btn-icone`, `.card`, `.input`, `.label`, `.badge`, `.etat-vide`, `.nav-item(-actif)`, **`.onglet(-actif)`**, **`.puce(-active)`**, `.table-cartes` |
| Graphiques | `frontend/src/theme/graphiques.js` | `PALETTE`, `ETAT`, `couleurNature`, `couleurMode`, `useAnimation`, `AXE`, `GRILLE`, `LEGENDE` |
| Infobulle et légende des graphiques | `frontend/src/components/charts/Infobulle.jsx` | `<Infobulle />`, `encre` |
| Carte d'un graphique (titre, description « i », période, population, unité, état vide, tableau de détail) | `frontend/src/components/analytics/elements.jsx` (`CarteGraphique`) | tous les graphiques d'analyse |
| Explication d'un indicateur | `frontend/src/components/payments/AideKpi.jsx` | bouton « i » accessible (survol, focus, toucher, Échap) |
| Menu latéral | `frontend/src/layouts/menus.js` et `frontend/src/components/navigation/MenuLateral.jsx` | 5 profils |
| Fermeture des panneaux | `hooks/useFermetureExterieure.js` et `hooks/useEchap.js` | menus déroulants, cloche, menu mobile |

## 2. Couleurs

- **Marque** :
  - bleu nuit `#071D49` / `#0E2A63` : menu, onglets actifs, titres forts ;
  - or `#D89B16` : accent, page active du menu ;
  - ciel `#4AA3DF` ;
  - bleu d'action `#1D4ED8` : boutons principaux, liens, focus.
- **États** : succès `#15803D`, attention `#B45309`, alerte `#B91C1C`, information `#1D4ED8`. Ils ne servent qu'aux états, toujours accompagnés d'un libellé ou d'une icône.
- **Palette des graphiques**, dans cet ordre et jamais recyclée : `#1E4FA8` bleu, `#D89B16` or, `#3A9BD9` ciel, `#2E8B57` vert, `#8E5BB5` violet, `#C8553D` terre.
  - Validée par l'outil de contrôle des couleurs : bande de luminosité, saturation, séparation pour les daltonismes ΔE ≥ 15,1 et en vision normale ΔE ≥ 19,2.
  - L'or et le ciel ont un contraste inférieur à 3:1 sur blanc : jamais de texte à leur couleur.
- **Couleur par catégorie, identique dans tous les modules** :
  - natures de frais : scolarité bleu, inscription or, cantine vert, transport ciel, garderie violet, autres terre ;
  - modes de paiement : espèces bleu, MTN or, Moov ciel, carte violet, virement vert, chèque terre.

## 3. Animations

- **Graphiques** : 700 ms, décélération (`useAnimation`), pour l'apparition, les barres, les segments, le tracé des courbes et les changements de filtre.
- **Interface** : 150 à 250 ms. Ouverture des fenêtres par ressort court ; apparition des pages et des lignes de tableau par un léger glissement (`animate-apparition`) ; transitions de couleur au survol.
- **`prefers-reduced-motion`** : toutes les animations sont coupées (`useAnimation`, `motion-reduce:*`, règle globale dans `index.css`).
- Aucune animation permanente, et aucune ne retarde l'affichage des valeurs.

## 4. Graphiques : règles

1. **Un graphique répond à une question** :
   - évolution dans le temps : aire ou courbe ;
   - comparaison : barres horizontales ;
   - répartition simple (≤ 6 parts) : anneau avec le total au centre ;
   - catégories liées : barres groupées.
   
   **Jamais deux axes verticaux.**
2. **Chaque graphique** a un titre, une description (« i »), une période ou un contexte, une population, une unité, une légende dès deux séries, des infobulles, un état vide expliqué et, quand c'est utile, un tableau de détail (également exporté).
3. **Aucune donnée inventée ni extrapolée** : un cumul n'est qu'une somme de montants réels ; sans donnée, le graphique dit pourquoi.

## 5. Accessibilité

- Focus visible partout (`:focus-visible`).
- Fenêtres : focus capturé, Échap pour fermer (seulement celle du dessus).
- Menus : `aria-expanded`.
- Tri : `aria-sort`.
- Explications : `role="tooltip"`.
- Libellés des icônes : `aria-label`.

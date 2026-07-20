# MEDIA_DUPLICATES_REPORT.md — Déduplication des images (V6 + V6.1, 20/07/2026)

## V6.1 — audit des doublons APRÈS intégration des remplacements

| Média | Emplacement(s) | Doublon ? | Décision | Remplacement |
|---|---|---|---|---|
| `campus-batiment` (façade rouge) | était : galerie « Notre campus » + bannières À propos/Campus | doublon visuel avec `campus-garderie-maternelle` | retiré de la galerie | `campus-logo` |
| `campus-garderie-maternelle` (façade rouge) | était : galerie « Notre campus » + mosaïque d'accueil | doublon visuel avec `campus-batiment` | retiré des deux | `campus-fresque` (accueil) / `campus-logo` (galerie) |
| `apropos-direction` (homme au bureau) | À propos « La direction » + `galerie-mosaique-3` | **image bannie** (personne assise seule dans un bureau) | **supprimé du site ET du paquet** | portrait `apropos-encadrement` (une seule photo de la personne) |
| `apropos-direction-2` (même homme au bureau) | inutilisé (registre seul) | même personne, même type de scène banni | **supprimé du paquet** | — |
| `galerie-mosaique-3` (composite) | « Moments FEBA » | incrustait l'image bannie | **supprimé du site ET du paquet** | — |
| `apropos-encadrement` (portrait directeur) vs `apropos-direction*` | « La direction » | **doublon de personne** (À propos montrait 2× le directeur) | on ne garde que le portrait | photo d'équipe `apropos-equipe-pedagogique` pour « L'encadrement » |

**Résultat V6.1** : « Notre campus » = 4 vues distinctes (bâtiment+logo,
façade, fresques, cour) ; « Une équipe engagée » = 3 catégories distinctes,
aucune personne répétée ; aucune image de bureau bannie présente (vérifié :
`apropos-direction*` et `galerie-mosaique-3` absents du DOM public **et** des
fichiers packagés). Les 4 nouveaux médias n'apparaissent chacun qu'aux
emplacements prévus (pas de réutilisation en section voisine).

---

# MEDIA_DUPLICATES_REPORT.md — Déduplication des images (V6, 20/07/2026)

Objectif : plus aucune image réutilisée de façon abusive sur le site vitrine
(un même visuel répété sur plusieurs pages/cartes donnait une impression de
« remplissage »). Le cas le plus flagrant : `hero-campus` apparaissait ~8 fois.

## 1. Méthode

Chaque visuel est identifié par un *slug* canonique du registre
`frontend/src/site/mediaMeta.js` (62 slugs). Le décompte ci-dessous est
**réel** : occurrences du slug dans les sources qui *placent* réellement une
image (`content.js`, `siteDefaults.js`, `pages/*.jsx`, `components/*.jsx`) —
hors registre et hors fichiers de test.

## 2. Après déduplication — usage par image (extrait)

| Occurrences | Image (slug) | Emplacements |
|---|---|---|
| 2 | `hero-campus` | slide carrousel par défaut (repli) + carte « bâtiment principal » (Campus). Sert aussi d'`og_image` par défaut (métadonnée, pas un visuel de page). |
| 2 | `hero-excellence`, `hero-bilingue`, `hero-vie-scolaire`, `hero-admissions` | bannière de page + slide de carrousel correspondant (réemploi **légitime** : chaque hero est aussi son propre slide) |
| 1 | tous les autres visuels placés (activités, académique, campus, niveaux, galerie, à-propos, admissions, online…) | une seule position chacun |

**Maximum d'usage = 2**, et uniquement pour des *hero* réutilisés comme fond de
leur propre slide (association 1 hero ↔ 1 slide, voulue). Aucun visuel de
contenu n'est répété. La sur-utilisation de `hero-campus` (≈8×) est éliminée.

## 3. Déduplications appliquées (V6)

| Lieu | Avant | Après |
|---|---|---|
| Accueil — grille de présentation | `hero-campus` (déjà en tête du carrousel) | `academique-lecture` (visuel distinct) |
| Accueil — meta `og_image` | `hero-campus` | conservé en meta (non affiché comme visuel) |
| Campus — bannière hero | `hero-campus` | `campus-batiment` |
| Campus — cartes « espaces » | 6 cartes dont `campus-batiment` en doublon avec la bannière | 5 cartes, `campus-batiment` retiré des cartes |
| Accueil — carte niveau CM1·CM2 | `academique-participation` (mur crème, voir crop audit) | `valeurs-projet` |
| Galerie « Notre campus » (seed) | contenait `hero-campus` (doublon du carrousel) | `hero-campus` retiré |
| Galerie « Moments FEBA » (seed) | contenait `valeurs-projet` | `valeurs-projet` retiré, `admissions-visite` ajouté |

## 4. Galerie — anti-doublon durable (backend)

Le seed `seed_website.py` applique désormais un **élagage** : pour chaque album,
les `GalleryItem` de type image dont le chemin n'est pas dans la liste voulue
sont supprimés —

```python
album.items.filter(kind="image").exclude(image_path__in=wanted_paths).delete()
```

Un re-seed ne peut donc plus laisser d'ancien média orphelin ou dupliqué. La
sortie du re-seed indique `−1 obsolète` sur « Notre campus » et « Moments FEBA ».
Chaque album expose des visuels **distincts** (vérifié en navigateur, § galerie
du `VISUAL_FIXES_REPORT`).

## 5. Vérification

- Décompte d'usage ci-dessus : reproductible par `grep` des slugs.
- `src/site/carousel-gallery.test.jsx` : `DEFAULT_ALBUMS` et `DEFAULT_SLIDES`
  sans doublon (assertions de déduplication).
- `tests/test_website.py` : la galerie API expose des albums avec items
  distincts + points focaux valides.
- Navigateur (1920) : page Galerie remplie de visuels tous différents ; aucune
  vignette répétée ; plus de « La galerie sera bientôt disponible ».

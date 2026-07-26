# VIDEO_INTEGRATION_REPORT.md — Vidéo galerie (V7-P6, 25/07/2026)

## 1. Inspection de la source (ffprobe)

| Propriété | Valeur |
|---|---|
| Conteneur / codecs | MP4 — **H.264** (vidéo) + **AAC** (audio) |
| Résolution | **576 × 1024** (portrait 9:16) |
| Images/s | 30 |
| Durée | **54 s** |
| Audio | stéréo (présent) |
| Poids source | 11,2 Mo (~1,66 Mbps) |
| Compatibilité | H.264/AAC → lisible nativement par tous les navigateurs |

## 2. Optimisation

`ffmpeg -c:v libx264 -crf 26 -preset slow -c:a aac -b:a 96k -movflags +faststart`

| | Avant | Après |
|---|---|---|
| Poids | 11,2 Mo | **6,6 Mo** |
| Faststart (streaming web) | non | **oui** |
| Codecs | H.264/AAC | H.264/AAC (conservés) |

Affiche (poster) régénérée depuis une image de la vidéo :
`feba-presentation-poster.webp` (576 × 1024, 68 Ko).

## 3. Intégration

- Fichiers : `frontend/public/site/video/feba-presentation.mp4` (+ poster).
  Réutilise l'emplacement vidéo existant de la galerie (album **« Moments
  FEBA »**), déjà administrable via le seed backend (`GalleryItem` `kind=video`).
- Carte galerie : miniature (poster) + icône de lecture (`PlayCircle`) + titre
  « FEBA en vidéo ».
- Visionneuse (lightbox) : élément `<video controls>` — lecture/pause, barre de
  progression, **volume/sourdine**, **plein écran** ; navigation flèches
  (image ↔ vidéo) ; **pas de lecture automatique avec le son** ; **arrêt de la
  lecture à la fermeture** (l'élément vidéo est retiré du DOM).

## 4. Preuves navigateur (session réelle)

- Carte vidéo présente (poster `feba-presentation-poster.webp`, 1 bouton de
  lecture).
- Lightbox ouverte : `<video>` `src=feba-presentation.mp4`, `controls=true`,
  **`readyState=4`** (chargée/prête), **durée 54 s**, **576 × 1024** — capture
  du lecteur à l'appui (bâtiment FEBA réel avec le panneau « Faith & Excellence
  Bilingual Academy »).
- `autoplay=false`, `muted=false` (pas de son intempestif).
- Fermeture → `<video>` retiré du DOM (lecture stoppée).

> Note : la lecture programmatique (`video.play()`) est bloquée par l'économie
> d'énergie du volet navigateur en arrière-plan (`AbortError`), sans rapport
> avec le fichier : `readyState=4` prouve que la vidéo est entièrement chargée
> et lisible ; en premier plan elle se lit normalement.

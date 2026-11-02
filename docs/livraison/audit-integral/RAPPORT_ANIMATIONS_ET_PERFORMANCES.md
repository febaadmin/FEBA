# Animations et performances

## Flash

| Mesure locale, Chrome | Avant | Après |
|---|---|---|
| Chute d'opacité du voile sur 6 ouvertures | 6 | 0 |
| Pics isolés à 1366 px | non mesuré | 2 sur 642 images, variation de 11 et 21 sur 255 |
| Pics isolés à 640 px | non mesuré | 0 sur 925 images |
| Pics isolés en mouvement réduit | non mesuré | 2 sur 609 images, variation de 6 et 25 sur 255 |

Référence de la vidéo : 85, 150, 85, soit 65 niveaux. Les petits pics restants n'ont pas été identifiés. Autres navigateurs non mesurés.

## Coût de la refonte

| Fichier | Avant, compressé | Après, compressé |
|---|---|---|
| Entrée JS | 172,9 Ko | 173,7 Ko |
| CSS | 13,7 Ko | 14,5 Ko |
| framer-motion | 36,5 Ko | 40,6 Ko |

**La version finale est légèrement plus lourde : environ 5 Ko de plus au total.** Les mesures de temps ci-dessous n'ont pas de point de comparaison avant et après.

Page de connexion en production, depuis ma machine : 1,4 s jusqu'au repos du réseau, 1 seule mesure.

# Performance

Mesuré le 02/11/2026 sur le build de production local et, pour le serveur, depuis la machine elle-même.

| Mesure | Valeur |
|---|---|
| Entrée JS | 539 Ko, 173 Ko compressés |
| CSS | 85 Ko, 14 Ko compressés |
| Fichiers JS | 236, routes chargées à la demande |
| Plus gros morceau différé | Recharts, 350 Ko, 98 Ko compressés, seulement sur les pages à graphiques |
| Dictionnaire de traduction | 194 Ko bruts, dans l'entrée |
| Page d'accueil, premier octet, sur le serveur | 12 à 16 ms, sans réseau |

**Piste principale :** sortir le dictionnaire anglais de l'entrée, puisqu'il ne sert qu'en anglais. Non fait.

**Non mesuré :** temps réels sur téléphone et réseau mobile, nouveaux rendus React, temps des API sous charge. Aucune conclusion n'est donc tirée sur ces points.

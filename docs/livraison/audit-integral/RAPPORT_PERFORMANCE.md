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

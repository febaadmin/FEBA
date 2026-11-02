# Isolation entre académies

## Anomalie A1

**Message :** `T07Z/admin GET /api/bulletins/ contient l'étiquette de T14Z`, run 41466038561.

**Conclusion : faux positif du détecteur, forte présomption démontrée.** Les liens de fichiers privés contiennent un jeton signé en base64. Le détecteur cherchait l'étiquette sans tenir compte de la casse dans tout le texte.

| Preuve | Résultat |
|---|---|
| 400 000 vrais jetons d'un fichier T07Z | 71 contiennent par hasard une autre étiquette |
| Premier exemple | `T14Z`, comme dans l'échec, dans un jeton qui ne désigne que le fichier T07Z |
| Fréquence compatible | Environ 60 jetons par campagne : échec rare |
| Filtre de la vue | `student__school=school` |
| Campagne sous PostgreSQL | 8 sur 8 sans fuite |

**Limite :** le texte de l'échec d'origine n'a pas été enregistré. La démonstration établit le mécanisme, pas cette occurrence précise.

**Correction :** le détecteur décode les jetons et contrôle le fichier désigné. Il ne crie plus au hasard, et une vraie fuite dans un jeton devient détectable (`DetecteurDeFuiteTests`).

## Couverture

Listes et détails sur 2, 7, 19 académies, écritures croisées, paramètres `school_id` et en-tête d'académie forgés, personnes d'une même académie.

Non couvert par ces tests : contenu des PDF, tâches Celery, caches, notifications.

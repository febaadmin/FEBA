# Formulaires de contact — le WhatsApp ne disparaît plus, le message n'est plus coupé

## Les deux défauts signalés

La capture annotée montrait un message de contact dont le numéro WhatsApp
saisi par le visiteur ne s'affichait nulle part, et dont le texte était
coupé sur le côté droit.

Ce sont deux défauts distincts, de deux natures différentes.

## Défaut 1 — le WhatsApp

**Côté FEBA** : le formulaire ne demandait pas de numéro WhatsApp, et
`ContactMessageCreateSerializer` ne le déclarait pas. DRF ignore
silencieusement une clé non déclarée : un navigateur qui l'envoyait voyait
la valeur disparaître entre la requête et la base — sans erreur, sans
journal, sans rien.

**Côté FEBA FHA** : le champ était bien enregistré. C'est l'écran
d'administration qui ne l'affichait pas.

Dans les deux cas, une famille laissait son WhatsApp en pensant qu'on la
rappellerait dessus.

### La correction

- Le formulaire FEBA demande désormais un numéro WhatsApp.
- Le serializer public le déclare.
- Le détail d'un message affiche **tout** ce que le visiteur a saisi.
- Une action « Répondre sur WhatsApp » ouvre la conversation.

Un champ vide n'est pas affiché plutôt que rempli d'un tiret : la liste
reste lisible, et l'absence se distingue d'une valeur.

| Champ | FEBA | FEBA FHA | Affiché |
|---|:-:|:-:|:-:|
| Nom, e-mail, sujet, message | ✅ | ✅ | ✅ |
| Téléphone | ✅ | ✅ | ✅ |
| **WhatsApp** | ✅ *(ajouté)* | ✅ | ✅ *(ajouté)* |
| Pays | — | ✅ | ✅ |
| État / province | — | ✅ | ✅ |
| Fuseau horaire | — | ✅ | ✅ |
| Langue préférée | — | ✅ | ✅ |
| Catégorie | — | ✅ | ✅ |
| Consentement | ✅ | ✅ | ✅ |

## Défaut 2 — le message coupé

`whitespace-pre-line` conserve les retours à la ligne mais **ne coupe pas
un mot**. Une URL de 300 caractères, ou un mot collé sans espace,
élargissait le bloc au-delà de la fenêtre. Le texte partait à droite, hors
écran, sans barre de défilement et sans le moindre signe qu'il manquait
quelque chose.

Le message paraissait complet. C'est ce qui rend ce défaut coûteux : rien
n'indique qu'on lit un texte tronqué.

### La correction

Un composant dédié, `LongText` :

| Propriété | Valeur | Ce qu'elle empêche |
|---|---|---|
| `white-space` | `pre-wrap` | perdre les retours à la ligne du visiteur |
| `overflow-wrap` | `anywhere` | un mot continu qui pousse le bloc |
| `word-break` | `break-word` | idem, sur les navigateurs plus anciens |
| `overflow-x` | `hidden` | tout débordement latéral |
| `overflow-y` | `auto` + hauteur max | des boutons repoussés hors écran |
| `text-overflow` | **jamais** `ellipsis` | faire croire que le visiteur s'est arrêté là |

Aucun `line-clamp`, aucun `slice()`, aucune troncature. Une action
« Copier » emporte le texte intégral, y compris ce qu'il faut faire défiler
pour voir.

### Sécurité

Le contenu est rendu comme du **texte** (`{value}`), jamais avec
`dangerouslySetInnerHTML`. Un message contenant `<script>alert(1)</script>`
s'affiche littéralement — vérifié dans le navigateur : `0` balise `script`
créée dans le DOM.

Le message est en revanche **stocké tel quel**. Échapper à l'enregistrement
détruirait le message d'un visiteur qui parle légitimement de code. La
protection est à l'affichage, où elle est complète.

## Mesures dans un vrai navigateur

Message de 1 011 caractères comprenant un mot continu de 300 caractères,
une URL de plus de 400 caractères, des accents et du contenu ressemblant à
du code :

| Mesure | Attendu | Obtenu |
|---|---|---|
| `whiteSpace` | `pre-wrap` | `pre-wrap` |
| `overflowWrap` | `anywhere` | `anywhere` |
| `textOverflow` | ≠ `ellipsis` | `clip` |
| `scrollWidth` ≤ `clientWidth` | oui | **720 ≤ 720** |
| Caractères affichés | 1 011 | **1 011** |
| Balises `script` créées | 0 | **0** |
| Défilement horizontal de la page | 0 px | **0 px** |

Capture : `e2e/captures/v9-4-contact-detail.png`.

## Isolation entre académies

| Vérification | Résultat |
|---|---|
| Un admin FEBA ne voit pas les messages FHA | ✅ |
| Un admin FHA ne voit pas les messages FEBA | ✅ |
| Accès direct par identifiant → 404 | ✅ |
| Le super administrateur voit les deux, étiquetés | ✅ |
| Chaque ligne porte le code de son académie | ✅ |
| Le contenu saisi reste en lecture seule | ✅ |

En mode « Toutes les Académies », chaque ligne porte un badge **FEBA** ou
**FEBA FHA**. Deux messages voisins peuvent venir d'établissements
différents : sans étiquette, on répond au nom du mauvais.

## Tests

- `backend/tests/test_contact_forms_fields.py` — 11 tests, 10 sous-tests
- `frontend/src/components/ui/LongText.test.jsx` — 14 tests couvrant les
  neuf cas demandés : 10 / 500 / 5 000 caractères, mot continu de 300,
  URL longue, retours à la ligne, accents, caractères spéciaux, contenu
  ressemblant à du HTML
- `e2e/parcours-v9.mjs`, parcours 4 — mesures réelles dans Chromium

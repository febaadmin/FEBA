# Documents multi-académies — chaque document porte SON académie

## Le principe

Un document officiel engage une personne morale précise. L'académie n'est
donc jamais déduite du contexte : elle vient de **l'élève**, seule source
qui ne peut pas se désynchroniser du document produit.

## Vérification sur documents réels

Chaque exemple ci-dessous a été produit sur cette instance, puis son texte
extrait et confronté à ce qui doit — et ne doit pas — y figurer.

| Document | Doit contenir | Ne doit PAS contenir | Résultat |
|---|---|---|---|
| `recu-feba.pdf` | Faith & Excellence, FCFA, Cotonou | French Heritage, `$` | ✅ |
| `recu-fha.pdf` | FEBA French Heritage Academy, `$` | Faith & Excellence, FCFA | ✅ |
| `bulletin-feba.pdf` | FAITH & EXCELLENCE, Cotonou | FRENCH HERITAGE | ✅ |
| `bulletin-fha.pdf` | FEBA FRENCH HERITAGE ACADEMY | FAITH & EXCELLENCE | ✅ |
| `FHA-2026-0009-fiche-inscription.pdf` | FEBA French Heritage Academy, WhatsApp | Faith & Excellence | ✅ |

Aucun élément de l'une n'apparaît sur les documents de l'autre.

## Les gabarits déclarent leurs académies

| Gabarit | Académies autorisées | Pourquoi |
|---|---|---|
| `diploma_feba` | `FEBA` | Le fond porte l'identité visuelle de FEBA |
| `certificate_feba` | `FEBA` | Idem |

Ce n'est pas une restriction arbitraire. Le fond d'un diplôme **est** une
identité visuelle : le proposer à l'académie en ligne produirait un
document au nom de l'une et à l'effigie de l'autre — une erreur que celui
qui le reçoit ne peut pas voir.

L'écran ne masque pas le gabarit : il affiche la raison.

> Ce gabarit est réservé à : FEBA. Son fond porte l'identité visuelle de
> cette académie ; l'utiliser pour « FEBA French Heritage Academy »
> produirait un document au nom d'une académie et à l'effigie d'une autre.

**Pour lever cette réserve** : l'académie en ligne fournit son propre fond,
qui fera l'objet d'un gabarit distinct — pas d'un partage.

## Trois barrières, pas une

1. **Le gabarit** déclare ses académies (`academies` dans le JSON).
2. **Le serveur** refuse la production croisée, même en mode consolidé
   (`test_produire_un_document_feba_pour_un_eleve_en_ligne_est_refuse`).
3. **L'interface** exige une confirmation explicite de l'académie, remise à
   zéro dès que l'élève ou le gabarit change.

Une seule aurait suffi à empêcher l'erreur courante. Les trois empêchent
aussi celles qu'on n'a pas prévues.

## Portée de la page

| Académie sélectionnée | Élèves | Gabarits | Documents | Colonne Académie |
|---|---|---|---|---|
| FEBA | FEBA seuls | ceux qui l'autorisent | FEBA seuls | masquée |
| FEBA FHA | FHA seuls | aucun (voir ci-dessus) | FHA seuls | masquée |
| Toutes les Académies | tous | tous, étiquetés | tous, étiquetés | **affichée** |

En mode consolidé, un bandeau annonce explicitement la portée. Une page qui
n'annonce pas son académie laisse l'utilisateur supposer la mauvaise, et la
supposition ne se voit qu'après coup.

## Le défaut d'origine

`_visible_documents` filtrait sur `user.school`. Pour un super
administrateur, la page renvoyait donc TOUS les documents des deux
académies, quelle que soit l'académie choisie : sélectionner FEBA affichait
quand même les diplômes de FEBA French Heritage Academy. La page
contredisait le sélecteur placé juste au-dessus d'elle.

La liste d'élèves de la fenêtre de production avait le même défaut. Produire
un diplôme au fond FEBA pour un élève de l'académie en ligne ne demandait
alors qu'une erreur de frappe.

13 tests couvrent la correction (`tests/test_documents_academy_scope.py`).

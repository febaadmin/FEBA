# Audit de l'identité des documents — une seule source par académie
## V9-bis — vérification reconduite après le recalibrage

Le recalibrage des gabarits FEBA FHA touche des coordonnées, pas des
identités. La vérification a néanmoins été rejouée en entier, parce
qu'une coordonnée déplacée peut faire apparaître un élément qu'on croyait
hors zone.

| Contrôle | Résultat |
|---|---|
| Image rattachée à une académie apparaissant sur un document d'une autre | aucune (comparaison par CONTENU, pas par nom de fichier) |
| Mention textuelle de l'autre académie | aucune, dans les deux sens |
| Fond dessiné | celui de son académie, vérifié par empreinte |
| Gabarit ouvert à l'autre académie | aucun |
| Cachet apposé sur un document FEBA FHA | aucun — voir ci-dessous |

`test_academy_identity_separation.py` : **20 tests, 57 sous-tests**.

### Le cachet FEBA FHA

Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet d'une autre
académie n'est réutilisé. Le médaillon du certificat reste net, sa seule
mention d'exemple « YOUR SEAL » ayant été neutralisée par un masque
radial. Le document se produit, se télécharge et se remet normalement.

Levée : déposer le fichier dans `backend/feba_project/static_files/` et
renseigner `stamp` pour l'académie. Aucun code à modifier.

---

## Le défaut

Chaque générateur portait sa propre idée de l'établissement.

| Fichier | Ce qui était écrit en dur | Ce que cela produisait |
|---|---|---|
| `payments/pdf_generator.py` | `"FAITH & EXCELLENCE BILINGUAL ACADEMY"` en repli | Reçu FHA sous le nom de l'école de Cotonou |
| `payments/pdf_generator.py` | `"Cotonou"` au-dessus de la date | « Cotonou, le … » sur un reçu d'une académie sans campus |
| `payments/pdf_generator.py` | `#1E3A6E`, `#C9A227`, `#EEF3FF` | Les deux académies aux mêmes couleurs |
| `payments/pdf_generator.py` | `cachet_secretariat.png` | Cachet d'une académie sur les reçus de l'autre |
| `bulletins/pdf_generator.py` | `PRIMARY`, `GOLD`, `LIGHT` (constantes de module) | Idem, sur tous les bulletins |
| `bulletins/pdf_generator.py` | `"Cotonou, le …"` sous le cachet | Idem |
| `bulletins/pdf_generator.py` | `cachet_feba.png` | Idem |
| `documents/renderer.py` | `RESOURCE_FILES` (noms de fichiers) | Sceau d'une académie sur le diplôme de l'autre |
| `documents/models.py` | `(academy.code or "FEBA")` | Diplômes FHA numérotés `FEBA-DIP-…` |

Avec une seule école, aucune de ces lignes ne posait problème. Avec deux
académies, chacune devient un document faux — et un document faux qui a
l'air correct ne se corrige jamais, parce que personne ne le voit.

## La correction

`backend/apps/schools/branding.py` est la seule source. Elle expose
28 champs, tous résolus depuis l'académie :

| Groupe | Champs |
|---|---|
| Identité | `academy_id`, `academy_code`, `legal_name`, `display_name`, `short_name`, `group_name` |
| Images | `logo`, `document_logo`, `stamp`, `director_signature`, `secretary_stamp` |
| Couleurs | `primary_color`, `secondary_color`, `accent_color`, `background_color` |
| Coordonnées | `postal_address`, `city`, `country`, `phone`, `whatsapp`, `email`, `website` |
| Localisation | `currency_code`, `currency_symbol`, `locale`, `language`, `timezone` |
| Documents | `footer_text`, `document_prefix` |

### Trois décisions qui comptent

**Sans académie identifiable, `get_branding` lève.** L'ancien repli vers
`School.objects.first()` produisait un document complet, plausible et faux.
Une exception est bruyante ; un document erroné en circulation ne l'est pas.

**Le moteur de rendu ne connaît plus aucun nom de fichier.** Il traduit un
rôle — « le sceau officiel » — en un champ de l'identité qu'on lui remet.
Sans identité, il n'appose rien. C'est ce qui rend impossible d'apposer par
inadvertance le cachet d'une académie sur le document d'une autre.

**Une académie sans code connu n'hérite de rien.** Palette neutre, aucune
image. `manage.py branding_check` la signale plutôt que de lui prêter
l'emblème d'une autre.

## Identité effective, par académie

| Champ | FEBA | FEBA FHA |
|---|---|---|
| `legal_name` | Faith & Excellence Bilingual Academy | FEBA French Heritage Academy |
| `short_name` | FEBA | FEBA FHA |
| `primary_color` | `#071D49` | `#071D49` |
| `secondary_color` | `#0E2A63` | `#1F6B36` |
| `accent_color` | `#D89B16` | `#D89B16` |
| `background_color` | `#F7F2E8` | `#FFFFFF` |
| `city` | Cotonou | — |
| `currency_code` | XOF (FCFA) | USD ($) |
| `language` | fr | en |
| `timezone` | Africa/Porto-Novo | America/New_York |
| `document_prefix` | FEBA | FHA |
| `whatsapp` | — | +1 (215) 715-5406 |

Le bleu est commun : les deux académies appartiennent réellement au même
groupe éducatif. Ce qui les distingue est la couleur secondaire — l'or de
l'école de Cotonou, le vert de l'académie en ligne — exactement comme sur
le site public.

## Ce qui empêche la régression

`tests/test_branding_source.py` lit le CODE SOURCE des générateurs et
refuse la réapparition d'un nom d'académie, d'une ville, d'une adresse,
d'une devise, d'une couleur institutionnelle ou d'un nom de cachet.

Les commentaires sont exclus de l'analyse : expliquer le défaut corrigé
(« `Cotonou` codé en dur apparaissait sur les reçus FHA ») reste utile, et
un test qui interdirait d'en parler pousserait à effacer la mémoire du
défaut.

Les tests fonctionnels produisent ensuite deux reçus réels et vérifient
qu'aucun élément de l'une n'apparaît sur ceux de l'autre.

## Réserves honnêtes

**Aucune signature officielle n'est fournie.** Les zones
`director_signature` restent vides. Le moteur ne dessine, ne reconstitue et
n'approche jamais une signature : une signature inventée sur un diplôme
n'est pas une approximation graphique, c'est un faux. Déposer
`signature_direction.png` dans `feba_project/static_files/` suffit à la
faire apparaître.

**`website` est vide pour les deux académies.** Aucune adresse de site
n'a été communiquée. Inventer un domaine sur un document officiel serait
pire que de laisser le champ vide.

**Les deux gabarits de documents officiels sont réservés à FEBA.** Leur
fond porte son identité visuelle. L'académie en ligne n'a pas encore fourni
le sien ; le jour où elle le fera, ce sera un gabarit distinct — pas un
partage. Voir `MULTI_ACADEMY_DOCUMENT_REPORT.md`.

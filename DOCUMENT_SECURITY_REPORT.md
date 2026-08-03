# Sécurité des documents officiels

Un diplôme n'est pas un fichier : c'est une affirmation de l'établissement,
opposable, qui circule hors de l'application. Ce rapport décrit ce qui le
protège, et comment chaque protection a été vérifiée.

## 1. Le fichier n'a aucune URL publique

Les documents produits vont dans `PRIVATE_MEDIA_ROOT`, **hors du
répertoire servi par le serveur web**, en permissions `0600`.

Un diplôme déposé dans `/media/` est accessible à qui devine son nom — et
un nom de fichier n'est pas un secret.

Le seul accès est :

```
GET /api/documents/<id>/download/     (authentifié)
```

La réponse d'API n'expose **ni chemin, ni nom de fichier** : elle annonce
uniquement cette route. Un test le vérifie en cherchant `.pdf` et la
racine privée dans la sérialisation complète.

En-tête posé sur chaque téléchargement :

```
Cache-Control: private, no-store
```

Sans lui, un poste partagé entre plusieurs familles servirait le diplôme
d'un autre élève depuis son cache.

## 2. L'appartenance se vérifie sur l'élève, jamais sur l'identifiant reçu

Une requête arrive avec un numéro dans l'URL. Ce numéro ne prouve rien.
Le filtre part de l'**utilisateur** et descend vers les documents qu'il
peut légitimement voir :

| Qui | Voit | Produit | Délivre | Révoque |
|---|---|---|---|---|
| Parent | les documents de ses enfants | non | non | non |
| Élève | les siens | non | non | non |
| Enseignant | rien | non | non | non |
| Administration (`role_level ≥ 80`) | ceux de son académie | oui | oui | oui |
| Super administrateur | tous | oui | oui | oui |
| Administration d'une **autre** académie | **404** | non | non | non |

**404 et non 403** : confirmer l'existence d'un document qu'on n'a pas le
droit de voir est déjà une information.

Tests d'anti-IDOR exécutés :

- un parent télécharge le document de son enfant → **200**
- le même identifiant, demandé par un parent d'une autre académie → **404**
- le même identifiant, demandé par l'administration d'une autre académie → **404**
- un anonyme → **401/403**
- un parent qui tente de produire un document → **403**
- un parent qui tente de délivrer un document → **403**
- un administrateur qui produit pour un élève hors de son académie → **404**

## 3. Un document émis ne se modifie plus

```
draft ──→ to_validate ──→ validated ──→ issued ──→ revoked
  ↑            │              │            └────→ replaced
  └────────────┴──────────────┘
```

Les transitions autorisées sont une **table explicite**. Ce qui n'y figure
pas est interdit, et se lit.

« Corriger » un document émis est le réflexe naturel de quelqu'un qui vient
de repérer une faute de frappe. C'est précisément ce qu'il ne faut pas
laisser faire silencieusement : une copie imprimée circule peut-être déjà.

| Garantie | Mécanisme | Vérifié par |
|---|---|---|
| Le fichier d'un document émis ne change plus | `store_pdf()` refuse sur un état figé | test |
| On remplace, on n'écrase pas | `replaces` / `replaced_by`, l'ancien passe à `replaced` et **reste sur le disque** | test |
| Une révocation se justifie | motif obligatoire, sinon refus | test |
| Une transition interdite échoue | table `ALLOWED_TRANSITIONS` | test |
| Un document ne franchit pas la frontière entre académies | `clean()` compare l'académie de l'élève | test |

## 4. Un document se prouve

Chaque `GeneratedDocument` conserve :

| Empreinte | Ce qu'elle permet |
|---|---|
| `file_sha256` | dire si un fichier présenté est bien celui qui a été délivré |
| `template_fingerprint` | dire avec quelle version de la mise en page il a été produit — **coordonnées comprises** |
| `background_sha256` | dire sur quel fond exact il a été imprimé |

Le troisième point compte particulièrement dans cette livraison : les fonds
installés sont des **variantes acceptées**, pas les PNG d'origine. Chaque
document en porte donc la trace, et le rapport de fidélité le dit aussi.

## 5. Un numéro ne se devine pas et ne se duplique pas

Format : `FEBA-DIP-2026-0001`, séquentiel par académie, type de document et
année.

Le compteur est une table dédiée avec `select_for_update` — un verrou pris
**en base**, pas dans le processus. Un `count() + 1` donnerait le même
numéro à deux émissions simultanées, et deux diplômes portant le même
numéro ne sont plus des preuves. Deux instances du serveur n'ont aucune
mémoire commune : un verrou applicatif ne les coordonnerait pas.

Contrainte d'unicité partielle en base : `UniqueConstraint(number)` avec
`condition=~Q(number="")`. Les brouillons n'ont pas encore de numéro, et
plusieurs chaînes vides ne sont pas des doublons.

## 6. Chaque opération laisse une trace

`DocumentEvent` enregistre action, état de départ, état d'arrivée, auteur,
détail et horodatage.

Sans ce journal, un document révoqué est un document dont personne ne sait
qui l'a révoqué ni quand — ce qui revient à ne pas pouvoir le justifier
devant celui qui le détient.

## 7. Aucune donnée personnelle dans la livraison

Les documents produits contiennent des noms d'élèves. Ils sont donc :

- stockés hors du répertoire public ;
- **exclus de l'archive** (`backend/private_media/` est ignoré par Git) ;
- absents du ZIP livré — vérifié à l'extraction.

Les exemples livrés utilisent **cinq noms fictifs**, choisis pour ce qu'ils
font au moteur (long, composé, accentué, apostrophe typographique, court)
et non pour ressembler à quelqu'un.

## 8. Ce qui n'est jamais fabriqué

| Élément | Règle |
|---|---|
| Signature | jamais dessinée, reconstituée ni approchée. Aucun fichier officiel n'existe : la zone porte « (signature requise) » |
| Sceau | remplacé **uniquement** par le cachet officiel du projet. À défaut, « YOUR SEAL » reste visible |
| Nom | jamais tronqué : la police est réduite, puis le rendu **échoue** |
| Fond | jamais redessiné : bordures, ornements, médailles, rubans, logo et texture viennent du fichier, tel quel |

Une signature inventée sur un diplôme n'est pas une approximation
graphique : c'est un faux. Un nom tronqué sur un document officiel est une
erreur qui circule sans se voir.

## 9. Ce qui reste à faire

| Point | État |
|---|---|
| Signature officielle du directeur | **absente** — déposer `signature_direction.png` dans `feba_project/static_files/` |
| PNG d'origine des fonds | **absents** — les fichiers installés sont des variantes transcodées, tracées comme telles |

Aucun des deux n'est contourné par une approximation.

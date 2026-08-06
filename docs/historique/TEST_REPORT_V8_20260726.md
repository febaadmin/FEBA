# TEST_REPORT — V9

Chaque ligne correspond à une commande réellement exécutée depuis le
commit final, sur cette instance. Les nombres sont ceux qu'elle a
affichés, pas ceux qu'on attendait. Le rapport de la livraison précédente
est conservé sous `TEST_REPORT_V8.md`.

Date d'exécution : 2 août 2026.
Services actifs : PostgreSQL 16, Redis 7, serveur Django, serveur Vite,
Chromium.

---

## 1. Suites automatisées

| Suite | Commande | Résultat |
|---|---|---|
| Backend PostgreSQL | `pytest tests/ -q` | **1057 réussis, 529 sous-tests** |
| Backend PostgreSQL, base de test **recréée** | `pytest tests/ -q --create-db` | **1044 réussis, 529 sous-tests** (avant la correction du limiteur) |
| Backend SQLite | `DJANGO_SETTINGS_MODULE=…test_sqlite pytest tests/ -q` | **1056 réussis, 1 ignoré, 529 sous-tests** |
| Frontend | `npx vitest run` | **163 réussis, 18 fichiers** |
| ESLint | `npx eslint src` | **0 erreur**, 83 avertissements |
| Build de production | `npm run build` | réussi, `dist/` produit en 9,77 s |

Le test ignoré sous SQLite porte son motif dans son propre message : test
de concurrence multi-processus, et SQLite en mémoire verrouille la table
entière. Il s'exécute sur PostgreSQL.

Les 83 avertissements ESLint sont la référence antérieure, inchangée :
variables inutilisées et dépendances de hooks, aucune erreur.

### Ce que la V9 ajoute

| Fichier | Volume | Ce qu'il tient |
|---|---|---|
| `backend/tests/test_textfit.py` | 50 tests, 147 sous-tests | Métriques réelles de la police, composition du nom, analyse de pixels du rendu |
| `backend/tests/test_academy_identity_separation.py` | +2 tests | La formulation exacte de la limitation du cachet, et le fait que le nom sur deux lignes n'en soit plus une |
| `frontend/src/router/roleRedirect.test.jsx` | 2 tests | Un rôle pas encore chargé n'oriente personne |
| `backend/tests/test_ratelimit_degrade.py` | 13 tests | La connexion répond 503 et non 500 quand le cache est injoignable, et ne délivre aucun jeton |

Progression : 974 → **1057** tests backend, 161 → **163** frontend.

---

## 2. Installation neuve

Base PostgreSQL créée vide, chaîne de migrations complète appliquée.

```
DROP DATABASE IF EXISTS feba_v9_final ; CREATE DATABASE feba_v9_final
manage.py migrate
```

| Contrôle | Résultat |
|---|---|
| Migrations appliquées | **126** |
| Migrations en attente | **0** |
| Échec, saut ou avertissement | aucun |

### Les documents sont produisibles sans commande supplémentaire

`manage.py documents_ready` — **17 contrôles passés**, tels qu'affichés :

```
✓ polices — 3 embarquées
✓ stockage privé — backend/private_media
✓ certificate_feba        · fond original — variante acceptée
✓ certificate_feba        · calibrage — tolérance 0.2 mm
✓ certificate_feba        · rendu — 997 Ko produits
✓ certificate_feba_fha    · fond original — empreinte conforme
✓ certificate_feba_fha    · fond neutralisé — 94bf155423f558b0… conforme
✓ certificate_feba_fha    · calibrage — tolérance 0.2 mm
✓ certificate_feba_fha    · rendu — 2163 Ko produits
✓ diploma_feba            · fond original — variante acceptée
✓ diploma_feba            · fond neutralisé — f233b6bcfe3d5672… conforme
✓ diploma_feba            · calibrage — tolérance 0.2 mm
✓ diploma_feba            · rendu — 1684 Ko produits
✓ diploma_feba_fha        · fond original — empreinte conforme
✓ diploma_feba_fha        · fond neutralisé — 9fa7d7a23dfaf511… conforme
✓ diploma_feba_fha        · calibrage — tolérance 0.2 mm
✓ diploma_feba_fha        · rendu — 3244 Ko produits
```

Aucun `document_neutralize` n'est à lancer : les fonds neutralisés sont
versionnés et vérifiés par empreinte avant chaque émission.

### Empreintes des fonds dérivés

| Gabarit | Dérivé installé | Déclarée | Conforme |
|---|---|---|---|
| `diploma_feba` | `f233b6bc…9de2cbc902` | `f233b6bc…9de2cbc902` | oui |
| `diploma_feba_fha` | `9fa7d7a2…50fe2371` | `9fa7d7a2…50fe2371` | oui |
| `certificate_feba_fha` | `94bf1554…5a5efc66c6` | `94bf1554…5a5efc66c6` | oui |
| `certificate_feba` | — | — | sans objet |

Il y a **trois** dérivés et non quatre : le certificat de Cotonou ne
porte aucune mention d'exemple à neutraliser. Lui déclarer un dérivé
reviendrait à vérifier l'empreinte d'un fichier sans raison d'exister.

---

## 3. Contrôles dédiés

| Contrôle | Commande | Résultat |
|---|---|---|
| Vue exposant un modèle d'académie sans filtrage | `manage.py academy_scope_audit --strict` | **0 sur 13 examinées**, 11 exemptées avec motif écrit |
| Champ collecté mais perdu dans la chaîne | `manage.py field_mapping_audit --strict` | aucun |
| Identité codée en dur hors de la source unique | `pytest tests/test_branding_source.py` | 17 tests, 5 sous-tests |
| Documents officiels — ensemble des suites | six fichiers de tests dédiés | **155 réussis, 215 sous-tests** |

### Noms longs

Le nom de test de **79 caractères** —
`Marie-Élisabeth Joséphine Adjovi-Bokô d'Almeida de Souza Hounkpatin Ahouangonou`
— est composé sur deux lignes centrées sur les quatre gabarits :

| Gabarit | Lignes | Corps | Encre (y) | Zone autorisée |
|---|---|---|---|---|
| `diploma_feba` | 2 | 22,75 pt | 120,83 – 136,79 mm | 119,93 – 136,85 mm |
| `diploma_feba_fha` | 2 | 21,00 pt | 127,84 – 142,57 mm | 126,50 – 142,62 mm |
| `certificate_feba` | 2 | 19,75 pt | 122,05 – 135,90 mm | 121,62 – 135,95 mm |
| `certificate_feba_fha` | 2 | 15,00 pt | 126,68 – 137,20 mm | 126,30 – 137,24 mm |

Le contrôle décisif n'est pas ce tableau mais une **analyse de pixels** :
le document est produit, rastérisé à 200 dpi, puis comparé au même fond
posé par le même calcul, sans un seul champ. Les deux pages passent par
`drawImage` avec la même transformation ; leur différence est, au pixel
près, ce que le moteur a ajouté.

C'est le seul contrôle qui voyait le défaut d'origine : la phrase gravée
est un dessin dans le fond, et aucune analyse de la structure du PDF ne
peut constater qu'un nom la recouvre. Trois versions successives du repli
sur deux lignes ont passé les contrôles géométriques et recouvert cette
phrase.

### Les contrôles mordent-ils ?

Un test qui ne peut pas échouer ne prouve rien. Trois mutations
volontaires ont été appliquées, observées, puis annulées :

| Mutation | Résultat |
|---|---|
| Réserve de jambage 0,23 → 0,002 em | **52 échecs** |
| Limiteur remis à `django_ratelimit` nu | les **13** tests du limiteur échouent |
| Zone du diplôme FEBA étendue à y 114 mm, sur la phrase gravée | `test_la_zone_tient_entre_la_phrase_gravee_et_la_regle` échoue |
| `RoleRedirect` sans attente du rôle | les 2 tests du routeur échouent |

### Téléchargement sécurisé et autorisations

Éprouvés dans le navigateur (§ 4) et par
`tests/test_official_documents.py` : fichiers hors du répertoire public,
permissions `0600`, `Cache-Control: private, no-store`, et **404 et non
403** pour un identifiant d'une autre académie — répondre « interdit »
confirmerait que le dossier existe.

---

## 4. Parcours navigateur

Chromium réel, backend et frontend lancés, PostgreSQL et Redis en
service.

| Parcours | Commande | Contrôles |
|---|---|---|
| Documents officiels, deux académies | `node e2e/parcours-documents-officiels.mjs` | **54 / 54** |
| Préinscriptions FEBA | `node e2e/parcours-preinscription-feba.mjs` | 41 |
| Rapports mensuels FEBA FHA | `node e2e/parcours-rapports-mensuels.mjs` | 30 |
| Envoi réel via Mailpit | script de vérification SMTP | 19 |

Le parcours des documents couvre : production d'un certificat **et** d'un
diplôme pour chacune des deux académies, délivrance, attribution du
numéro officiel, téléchargement réel des PDF, vérification que
l'empreinte affichée est bien celle des octets reçus, changement
d'académie **sans rechargement**, cloisonnement des deux administrateurs
dans les deux sens, six sondes anti-IDOR, recherche d'élève, liste vide
et erreur maîtrisée.

Le changement d'académie est vérifié par un **témoin** posé sur `window`
avant la bascule : s'il a disparu après, la page a rechargé. Une liste
qui se met à jour après un rechargement complet a l'air correcte et ne
l'est pas.

Dix captures nommées : `e2e/captures/documents-01…10-*.png`.

### Les erreurs de console sont comptées, pas filtrées

Le scénario provoque lui-même sept réponses en erreur — un refus de
gabarit (400) et six sondes anti-IDOR (404) — et **leur nombre est une
assertion**. S'il change, c'est qu'une requête a échoué là où on ne
l'attendait pas, ou qu'une sonde a cessé d'être refusée.

Deux familles sont écartées, chacune avec sa raison nommée :

- la feuille de style de Google Fonts, coupée par la politique réseau du
  bac à sable — un CDN tiers, sans effet sur le rendu ;
- les annulations volontaires de requêtes au changement d'académie. Leur
  nombre n'est **pas** une assertion : il dépend de ce qui est en vol à
  cet instant précis, et un contrôle sur une course est un contrôle qui
  échouera un jour sans qu'il se soit rien passé.

### Deux défauts trouvés par ce parcours

1. **Un administrateur qui rechargeait sa page atterrissait dans l'espace
   élève.** `RoleRedirect` attendait la réhydratation du magasin
   d'authentification, mais pas le chargement de l'utilisateur ; dans
   cette fenêtre `role` vaut `undefined` et le repli final envoyait vers
   `/student/home`. Corrigé, avec deux tests qui échouent contre
   l'ancien code.

2. **Un identifiant de gabarit inconnu renvoyait le chemin absolu du
   serveur** au navigateur. Corrigé : le chemin ne sort plus, la liste
   des gabarits disponibles reste.

### Le limiteur de débit, vérifié en conditions réelles

Redis réellement arrêté puis relancé, contre le serveur de
développement — pas seulement simulé dans un test.

| Situation | Attendu | Obtenu |
|---|---|---|
| Redis actif | 200, jeton délivré | 200, jeton délivré |
| Redis arrêté, `Accept-Language: fr` | 503, message français | 503, `Retry-After: 30`, message français |
| Redis arrêté, `Accept-Language: en` | 503, message anglais | 503, message anglais |
| Redis arrêté | incident ouvert | `ERR-4C707E`, `module=ratelimit`, `status_code=503`, `severity=high` |
| Redis relancé | service rétabli | 200 sans intervention |

---

## 5. Inspection visuelle

Huit rendus produits, ouverts et examinés : diplôme et certificat × FEBA
et FEBA FHA × nom de 12 et de 79 caractères.

Ce que l'inspection a montré et qu'aucun test ne disait :

- les signatures du diplôme FEBA FHA flottaient 8,3 mm au-dessus de leur
  trait, et sa date 1,1 mm ; le certificat FEBA FHA avait le même défaut
  de 5,2 mm ;
- une fois recalées, elles **traversaient un fleuron** — un ornement
  centré de 4,4 mm posé au-dessus de chaque règle, propre à ce fond.
  Pour un détecteur, un fleuron est un trait horizontal de plus ; il a
  fallu regarder.

Les deux sont corrigés et documentés dans
`DOCUMENT_TEMPLATE_CALIBRATION.md`.

---

## 6. Ce que ce rapport ne prouve pas

- Les suites ne remplacent pas une relecture humaine de la mise en page.
  Un test affirme qu'un nom ne touche pas une règle ; il n'affirme pas
  qu'il est bien posé.
- La recherche de secrets porte sur les fichiers suivis par Git et sur
  des motifs connus. Un secret d'une forme inhabituelle passerait.
- `academy_scope_audit` détecte une vue qui **ignore** l'académie. Il ne
  prouve pas qu'une vue qui la mentionne filtre correctement — cela
  relève des tests de cloisonnement par module, qui existent.
- Le parcours navigateur s'exécute sur un serveur de développement
  mono-processus. Le comportement sous charge réelle n'est pas mesuré
  ici.
- `RATELIMIT_ENABLE = False` reste dans les réglages de test, pour que
  les autres suites ne se bloquent pas elles-mêmes en enchaînant les
  connexions. Le limiteur n'est donc éprouvé que par
  `test_ratelimit_degrade.py`, qui le rallume explicitement. Aucune autre
  suite ne mesure son comptage.

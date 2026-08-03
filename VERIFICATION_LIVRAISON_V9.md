# Vérification de la livraison V9

L'archive n'est pas déclarée valide parce qu'elle a été construite. Elle
est **extraite**, puis éprouvée, hors du dépôt de travail, sur une base
de données neuve. Les résultats ci-dessous sont ceux de cette
vérification-là.

Commit livré : `6803f379` — branche `claude/feba-multi-entity-integration-kqx181`.

---

## 1. Intégrité

| Contrôle | Commande | Résultat |
|---|---|---|
| Empreintes de tous les fichiers | `sha256sum -c SHA256SUMS.txt` | toutes conformes |
| Extraction | `unzip feba_multi_academies_v9.zip` | propre, 39 Mio |
| **Le ZIP est-il exactement le HEAD ?** | `diff -rq <(git archive HEAD) <extraction>` | **identique, 920 fichiers** |
| Le bundle porte-t-il le HEAD ? | `git bundle verify` | oui, historique complet |
| Le diff part-il du bon point ? | en-tête du fichier | `1a70a25` → HEAD, 30 fichiers |

## 2. Ce que l'archive ne contient pas

| Recherché | Trouvé |
|---|---|
| `node_modules/` | absent |
| `venv/` | absent |
| `__pycache__/`, `*.pyc` | absent |
| Base de données de test (`db.sqlite3`) | absent |
| `private_media/` (documents d'élèves) | absent |
| `staticfiles/` (artefact de build) | absent |
| `dist-livraison/`, `dist-rendus/` | absent |
| Fichier d'environnement **réel** | absent |

Fichiers d'environnement présents : `.env.example`, `.env.dev.example`,
`.env.prod.example`, `.env.jitsi.example`. Tous des modèles, aucun n'a de
valeur.

La recherche de secrets (`SECRET_KEY = "…"`, `sk_live_`, `pk_live_`,
clés privées PEM) ne trouve que des **exemples de documentation** :
`sk_live_…` avec points de suspension, dans le guide Stripe et l'aide de
`payments_setup`. Aucune clé réelle.

## 3. L'archive extraite fonctionne

Base PostgreSQL créée vide, code de l'archive, aucune modification.

| Contrôle | Résultat |
|---|---|
| `manage.py migrate` | **126 migrations appliquées**, 0 en attente |
| `manage.py init_academies` | deux académies créées avec leur identité |
| `manage.py documents_ready` | **17 contrôles passés** |
| Tests critiques (`test_textfit`, `test_ratelimit_degrade`, `test_academy_identity_separation`, `test_official_documents`, `test_documents_academy_scope`) | **148 réussis, 215 sous-tests** |

Aucun `document_neutralize` n'a été lancé. Les trois fonds neutralisés
sont versionnés et leurs empreintes vérifiées : le diplôme fonctionne
immédiatement après l'installation.

## 4. Les quatre documents sont produisibles depuis l'archive

Avec le nom de test de **79 caractères** :

| Gabarit | Taille | En-tête |
|---|---|---|
| `diploma_feba` | 1684 Kio | `%PDF` |
| `certificate_feba` | 1476 Kio | `%PDF` |
| `diploma_feba_fha` | 3244 Kio | `%PDF` |
| `certificate_feba_fha` | 2163 Kio | `%PDF` |

Chacun sur **deux lignes** : 22,75 pt · 19,75 pt · 21,00 pt · 15,00 pt.
Aucun refus, aucune troncature.

## 5. La séparation d'identité tient sur une installation neuve

C'est le contrôle qui compte le plus : un défaut de séparation
réintroduit par l'initialisation ne se verrait pas dans le dépôt de
travail, où les académies existent déjà.

| Académie | `stamp` | `secretary_stamp` | Logo | Sceau réellement résolu |
|---|---|---|---|---|
| FEBA | `cachet_feba.png` | `cachet_secretariat.png` | `logo_feba.jpeg` | `…/cachet_feba.png` |
| FEBA FHA | **`None`** | **`None`** | `logo_groupe_feba.png` | **aucun** |

Aucun cachet officiel FEBA FHA n'a été fourni ; aucun cachet d'une autre
académie n'est réutilisé.

## 6. Contenu livré

| Élément | Volume |
|---|---|
| `feba_multi_academies_v9.zip` | 33 Mio |
| `feba_multi_academies_v9.bundle` | 43 Mio, dépôt clonable |
| `feba_multi_academies_v9.diff` | 234 Kio |
| Rapports | 25 fichiers Markdown |
| `exemples/` | 20 PDF, dont un par gabarit avec le nom de 79 caractères |
| `comparaison/` | rendus, masques, images de différence et scores |
| `captures/` | 51 captures de navigateur, dont les dix de cette itération |
| `fonds/sources/` | 4 visuels officiels d'origine |
| `fonds/derives/` | 3 fonds neutralisés |
| `preuve-parcours-navigateur.txt` | sortie brute des 54 contrôles |
| `SHA256SUMS.txt`, `MANIFESTE.md` | empreintes et inventaire |


---

## 7. Ce que la livraison ne fait pas

| | |
|---|---|
| Push GitHub | **non effectué — HTTP 403.** Autorisation d'écriture sur `febaadmin/FEBA` ; `git ls-remote` réussit, ce n'est donc pas le réseau. |
| Historique complet | **inclus dans le bundle.** `git clone feba_multi_academies_v9.bundle` restitue les 62 commits, sans aucun accès distant. |
| Commits signés | **non.** La clé de signature du conteneur fait 0 octet et `ssh-keygen` est absent. Git accepte `commit.gpgsign=true` et produit des commits non signés, sans erreur — vérifié par une sonde, puis retirée. |
| Code et archive | **testés depuis le HEAD final.** |

L'historique n'a pas été réécrit : un rebase changerait les 62 empreintes
sans ajouter la moindre signature, et invaliderait cette vérification.

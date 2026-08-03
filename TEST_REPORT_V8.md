# TEST_REPORT — V9

Toutes les sorties de ce fichier ont été produites sur cette instance.
Aucune n'est reconstituée. La colonne « où » distingue le dépôt source de
l'archive extraite : c'est la distinction qui compte, puisque plusieurs
défauts n'apparaissaient que dans la seconde.

## 1. Suites

| Suite | Où | Commande | Résultat |
|---|---|---|---|
| pytest PostgreSQL 16 | dépôt source | `python -m pytest tests/ -q` | **806 passés**, 298 sous-tests |
| pytest PostgreSQL 16 | **archive extraite** | `./venv/bin/python -m pytest tests/ -q` | **806 passés**, 298 sous-tests |
| pytest SQLite | **archive extraite** | `DJANGO_SETTINGS_MODULE=…test_sqlite pytest tests/ -q` | **805 passés, 1 ignoré** |
| Vitest | **archive extraite** | `npx vitest run` | **123 passés** (15 fichiers) |
| ESLint | **archive extraite** | `npx eslint src` | **0 erreur**, 83 avertissements hérités |
| Build de production | **archive extraite** | `npm run build` | ✅ `built in 8.53s` |
| Parcours navigateur | **archive extraite** | `node e2e/parcours-v9.mjs` | **34 vérifications, toutes vertes** |

Le test ignoré sur SQLite est un test de concurrence multi-threads : SQLite
en mémoire verrouille la table entière. Il s'exécute sur PostgreSQL.

## 2. Suites ciblées, depuis l'archive extraite

| Domaine | Fichier | Résultat |
|---|---|---|
| Identité par académie + chaînes en dur | `test_branding_source.py` | 17 passés, 5 sous-tests |
| Documents officiels | `test_official_documents.py` | 49 passés |
| Diplôme après installation | `test_diploma_ready_after_install.py` | 16 passés |
| Portée par académie | `test_documents_academy_scope.py` | 16 passés, 7 sous-tests |
| Inscription FEBA FHA (18 étapes) | `test_fha_enrollment_workflow.py` | 43 passés, 194 sous-tests |
| Contacts + messages longs | `test_contact_forms_fields.py` | 16 passés, 10 sous-tests |
| Stockage privé / anti-IDOR | `test_private_storage.py` | 6 passés |
| Isolation entre académies | `test_entity_isolation.py` | 23 passés |
| Sécurité multi-tenant | `test_tenant_security.py` | 23 passés |
| Audit des champs | `test_field_mapping_audit.py` | 4 passés, 22 sous-tests |
| E-mails | `…::EmailTests` | 12 passés |
| Gabarits installés | `…::InstalledTemplatesTests` | 8 passés |

## 3. Installation propre, depuis le ZIP livré

Aucun élément n'a été copié depuis l'arbre de travail : ni virtualenv, ni
`node_modules`, ni base, ni cache, ni fichier d'environnement.

```bash
unzip -q feba_multi_academies_v9.zip -d /dossier/vide      # code 0
cd feba_multi_academies_v9/backend
python3 -m venv venv                                        # venv NEUF
./venv/bin/pip install -r requirements/dev.txt              # code 0
sudo -u postgres createdb -O feba_user feba_valid_v9        # base VIDE
./venv/bin/python manage.py migrate                         # 0 → 69 tables
./venv/bin/python manage.py init_academies
./venv/bin/python manage.py seed_demo_data
cd ../frontend && npm ci                                    # code 0
```

| Étape | Résultat |
|---|---|
| Extraction | ✅ code 0, aucune erreur |
| `python3 -m venv` | ✅ 7 paquets avant, installation depuis l'archive seule |
| `pip install -r requirements/dev.txt` | ✅ 71 paquets, code 0 |
| Base PostgreSQL neuve | ✅ **0 table avant, 69 après** |
| `init_academies` | ✅ deux académies, identité visuelle complétée |
| `seed_demo_data` + `seed_check` | ✅ **20 contrôles, isolation intacte** |
| `branding_check` | ✅ identité essentielle complète, 2 avertissements (signature absente) |
| `documents_ready` | ✅ **9 contrôles — produisibles sans commande supplémentaire** |
| `field_mapping_audit --strict` | ✅ aucun champ saisi invisible |
| `email_check` | ✅ diagnostic honnête : **aucun fournisseur réel** |
| `npm ci` | ✅ code 0, `node_modules` vide avant |

Python 3.11.15 · Node v22.22.2 · npm 10.9.7 · PostgreSQL 16 · Redis 6379

## 4. Ce que le test de l'archive a trouvé

Cinq défauts, tous invisibles depuis le dépôt source :

| # | Défaut | Correction |
|---|---|---|
| 1 | La livraison partait avec les rapports V8 | Liste explicite et **vérifiée** : un rapport manquant interrompt la construction |
| 2 | La règle d'académie ne tenait que dans la vue HTTP | Déplacée dans `create_document`, le point d'entrée unique |
| 3 | L'adresse imprimée se répétait (`Cotonou, Bénin, Cotonou, Bénin`) | Ville et pays ajoutés seulement s'ils manquent |
| 4 | Deux caractères perdus sur chaque message long | `trim_whitespace=False` sur les textes libres |
| 5 | `.env.dev` réel versionné et livré | Retiré du suivi + garde-fou qui refuse de construire |

Chacun a reçu un test de non-régression, et l'archive a été régénérée puis
réinstallée depuis zéro après chaque correction — quatre tours de boucle.

## 5. Documents produits depuis l'archive

| Document | Académie | Format | Identité | Contamination |
|---|---|---|---|---|
| `recu-feba.pdf` | FEBA | A4 portrait | Faith & Excellence · FCFA · Cotonou | aucune |
| `recu-fha.pdf` | FEBA FHA | A4 portrait | FEBA French Heritage Academy · `$` | aucune |
| `bulletin-feba.pdf` | FEBA | A4 portrait | FAITH & EXCELLENCE · Cotonou | aucune |
| `bulletin-fha.pdf` | FEBA FHA | A4 portrait | FEBA FRENCH HERITAGE ACADEMY | aucune |
| `diplome-feba.pdf` | FEBA | **A4 paysage 842×595** | `FEBA-DIP-2026-0001` | aucune |
| `certificat-feba.pdf` | FEBA | **A4 paysage 842×595** | `FEBA-CER-2026-0001` | aucune |
| `fiche-inscription-fha.pdf` | FEBA FHA | A4 portrait, 3–4 pages | FEBA French Heritage Academy | aucune |

Diplôme et certificat pour FEBA FHA : **refusés**, par règle métier. Leur
fond porte l'identité visuelle de FEBA. Voir `MULTI_ACADEMY_DOCUMENT_REPORT.md`.

### Neutralisation, mesurée au pixel

| Contrôle | Attendu | Obtenu |
|---|---|---|
| Pixels dorés dans la bande du placeholder, fond **original** | > 1 000 | **4 220** |
| Pixels dorés, fond **neutralisé** | 0 | **0** |
| Encre du nom réel sur le document produit | > 500 | **3 937** |

## 6. Sécurité

| Contrôle | Résultat |
|---|---|
| Fichier d'environnement réel dans le ZIP | **aucun** (4 modèles `.example` seulement) |
| `venv`, `node_modules`, `__pycache__`, `*.pyc`, `*.log` | **0** |
| Base de données, `private_media`, médias générés | **0** |
| Clés Stripe / AWS / GitHub / PEM / JWT réels | **0** |
| Téléchargement de fiche : admin propriétaire | 200 · `private, no-store` |
| Téléchargement : admin de l'autre académie | **404** (l'existence n'est pas révélée) |
| Téléchargement : enseignant, parent | 403 |
| Téléchargement : anonyme | 401 |

## 7. Parcours navigateur, depuis l'archive

`e2e/parcours-v9.mjs`, Chromium réel, build de production — **34
vérifications**. La plus parlante : le message de 1 011 caractères est
affiché entier, `scrollWidth` vaut exactement `clientWidth` (720 = 720), et
`<script>alert(1)</script>` s'affiche littéralement sans créer une seule
balise dans le DOM.

Routes vérifiées : 7 publiques, 5 privées, 1 inexistante — toutes rendues.
**0 réponse 5xx, 0 réponse 404.** Les 14 messages de console sont des
requêtes volontairement annulées à la navigation (`ERR_ABORTED`, registre
`academyScope.js`) et l'échec de `fonts.googleapis.com`, injoignable
derrière le proxy de ce conteneur.

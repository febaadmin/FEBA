# FEBA — Audit du 28 octobre 2026 : bulletin sur une page, conversions, sécurité, CI/CD

Branche `fix/audit-bulletin-ci-deploiement`.

| | |
|---|---|
| Départ | `705468c` (= version V2 `FEBA_LAST_VERSION`, vérifiée fichier par fichier ; seuls les deux workflows différaient, modifications reprises) |
| Base GitHub | `main` = `d3bc137` (ancêtre de `705468c` : provenance linéaire) |
| Commit final | voir `git log -1` ; les campagnes de référence ont tourné sur `1e464ff`, la documentation a été ajoutée ensuite |

Statuts utilisés :
- **CORRIGÉ ET TESTÉ** ;
- **NON VÉRIFIABLE** (environnement indisponible) ;
- **NON CORRIGÉ** ;
- **BLOQUÉ** (accès ou autorisation) ;
- **RECOMMANDÉ**.

---

## 1. Bulletin sur une seule page — CORRIGÉ ET TESTÉ

**Cause racine.** La mise en page ReportLab était rigide : logo de 2 cm, intertitres de 11 à 14 pt, marges internes des lignes, bloc commentaire et cachet de 3 cm. Elle ne vérifiait jamais la hauteur disponible. Mesuré : dès 6 matières françaises et 4 anglaises, les signatures, le cachet et le pied de page passaient en page 2. Les tests existants n'utilisaient que 2 à 4 matières.

**Correction** (`apps/bulletins/pdf_generator.py`). Quatre densités de mise en page sont essayées, de « standard » à « très compact ». Elles ne changent que les espacements, les marges internes, la taille du logo et du cachet, puis la police, jamais sous 7 pt. Le moteur conserve la première densité dont le PDF **produit** compte exactement une page.

Ni matière, ni note, ni appréciation, ni calcul ne sont retirés ou modifiés. Au-delà de la densité la plus compacte : `BulletinLayoutError`, HTTP 422 sur l'aperçu et la génération, ancien PDF conservé. Le bulletin de maternelle utilise le même mécanisme.

**Capacité mesurée** : 28 matières, ou 22 avec le commentaire maximal de 1 200 caractères. Les données réelles de développement comptent au plus 10 matières par classe.

**Défaut découvert pendant l'audit** : les lettres hors Windows-1252 étaient imprimées en carrés noirs (« Ìyábọ̀ » sortait « Ìyáb■■ »). Cela touche ɖ, ɛ, ɔ, ŋ, les voyelles pointées et les tons des noms en fon et en yoruba. Correction : repli glyphe par glyphe sur DejaVu Sans, police libre embarquée avec sa licence (`apps/core/pdf_longtext.py`).

**Preuves** :
- `tests/test_bulletin_one_page.py`, sur la base et l'API réelles, vérifie :
  - exactement une page A4, chaque matière et chaque information d'identité ;
  - la moyenne pondérée sur /10 et sur /20, et toutes les périodes ;
  - les notes manquantes, le commentaire maximal, les noms longs et accentués (fon et yoruba), deux académies ;
  - qu'aucun caractère ne sort de la page et qu'aucune police n'est sous 7 pt ;
  - l'aperçu, la génération, le fichier téléchargé et une classe entière ;
  - le refus explicite au-delà de la capacité.
- Navigateur réel (`e2e/parcours-bulletin-une-page.mjs`) : l'aperçu et 6 PDF officiels font une page chacun, avec les sections FR et EN et les signatures.

## 2. Délai de conversion des documents — CORRIGÉ ET TESTÉ

**Cause racine.** Le contrat, tel que l'annoncent le réglage et le message d'erreur, est un délai **global** par téléversement. Or `convert_office` enchaîne jusqu'à trois appels LibreOffice, et chacun recevait le délai entier. Avec un délai de 1 s, une conversion de 2,43 s était donc acceptée.

**Correction** (`apps/documents/conversion.py`) :
- un objet `Deadline` transmet à chaque étape le temps **restant** ;
- le relevé et le retrait des marqueurs comptent dans le délai ;
- le groupe de processus (LibreOffice et ses descendants détachés) est tué dans tous les cas ;
- les répertoires temporaires sont supprimés et aucun gabarit partiel n'est enregistré.

**Preuves** :
- `GlobalDeadlineTests` utilise un faux convertisseur à durée maîtrisée. Contre-épreuve : 2 échecs sur l'ancien code, 4 réussites sur le nouveau.
- `test_delai_de_conversion_depasse` (LibreOffice réel) a réussi 5 fois sur 5 dans l'image Python 3.12.
- Le test réel n'a été ni supprimé ni affaibli, et le délai n'a pas été relevé.

## 3. Données, migrations, retour arrière — CORRIGÉ ET TESTÉ (en local) ; production NON VÉRIFIABLE

- **96 migrations** séparent `main` de cette version, toutes non destructives.
- Copie peuplée par le code `main` (2 400 notes, 276 paiements, 120 bulletins…), puis migrée : effectifs, empreintes des identifiants et sommes **identiques** (`scripts/audit/data_counts.py`).
- **Défaut trouvé** : sept colonnes NOT NULL ajoutées sans défaut en base. Revenir à l'ancien code **sans restaurer la base** cassait la création de paiements (IntegrityError). Correction : `db_default` (migrations `notifications 0008`, `payments 0015`, `website 0013`). Avec le code `main` sur le schéma migré, les écritures fonctionnent (`scripts/audit/rollback_columns_check.py` → `RISKY []`).

## 4. Sécurité — CORRIGÉ ET TESTÉ

| Composant | Avant → après | Constat |
|---|---|---|
| Django | 5.0.4 → **5.2.18 LTS** | branche 5.0 non maintenue, 43 vulnérabilités publiées |
| DRF / simplejwt | 3.15.1 → 3.18.3 / 5.3.1 → 5.5.1 | 7 + 2 vulnérabilités |
| Pillow | 10.3.0 → 13.0.0 | 66 vulnérabilités |
| pypdf | 6.14.2 → 6.21.4 | 27 vulnérabilités |
| gunicorn / sentry-sdk | 21.2.0 → 23.0.0 / 1.45.0 → 1.45.1 | vulnérabilités publiées |
| WeasyPrint | **retiré** | inutilisé (6 vulnérabilités) |
| axios, follow-redirects, zod (+ resolvers) | 1.18 → 1.21, 1.16.0 → 1.16.2, 3 → 4 | sévérité haute |

Changements liés :
- `STATICFILES_STORAGE` → `STORAGES` (supprimé en Django 5.1).
- `fontTools` est déclaré : utilisé directement, il n'était présent que par WeasyPrint (158 tests échouaient sans lui).
- DRF ≥ 3.16 rendait `school` obligatoire au téléversement d'un logo : le validateur généré pour une contrainte conditionnelle est désactivé, avec justification.

Résultat de `pip-audit` après correction : aucune vulnérabilité (base et production). `npm audit --omit=dev --audit-level=high` : aucune haute ni critique. Reste React Router 6, avis **modéré**, atténué par la garde `safeInternalPath` (voir `KNOWN_LIMITATIONS.md`).

## 5. CI/CD — CORRIGÉ ; exécution GitHub : voir la pull request

**CI** :
- Python **3.12**, comme les images Docker (la CI testait en 3.11).
- LibreOffice et polices installés, et exigés (`FEBA_REQUIRE_LIBREOFFICE=1`). Les tests de conversion étaient auparavant **ignorés en silence**.
- Service Mailpit, et `-rs` pour lister chaque test ignoré.
- Contrôle bloquant explicite du bulletin sur une page et du délai de conversion.
- `pip-audit` et `npm audit`.
- Construction des images de production.

**Déploiement** : le commit **testé** (`GITHUB_SHA`) est déployé, et non plus `origin/main` au moment de l'exécution. Le commit précédent est enregistré pour le retour arrière. La fusion dans `main` déclenche **automatiquement** le déploiement en production.

## 6. Autres corrections

- Pagination ordonnée (enseignants, parents, académie).
- `CheckConstraint(check=)` → `condition=`.
- pypdf 7 : la page est rattachée au writer avant rotation et fusion.
- 39 libellés visibles codés en dur passent par `t()` (16 traductions anglaises).
- Liens de notification filtrés par `safeInternalPath`.

## 7. Tests exécutés (résultats exacts) — voir `TEST_REPORT.md`

| Suite | Résultat |
|---|---|
| Backend PostgreSQL 16, image Python 3.12 + LibreOffice, commit exporté `1e464ff` | **1959 passed**, 0 failed, 4 skipped |
| Backend SQLite, même image | **1948 passed**, 0 failed, 15 skipped |
| `manage.py check`, `makemigrations --check` | aucun problème, aucune migration manquante |
| Vitest | **413 passed** |
| ESLint | 0 erreur (74 avertissements préexistants) |
| Build Vite ; images Docker de production | réussis |
| E2E navigateur (Chrome) : bulletin, langues/identité (2 phases), académies, espaces anglais, préinscription, site public anglais | **tous verts** |

## 8. BLOQUÉ — production et intégration

- **Accès production** : la lecture de la production (SSH vers `62.238.38.111`, sondes de `globalfeba.com`) a été **refusée par la politique de permissions** de cette session. N'ont donc pas pu être vérifiés : la version en service, les volumes, les sauvegardes Restic, le TLS, Jitsi et les services. Aucun déploiement n'a eu lieu.
- **Fusion** : non effectuée. Elle déclenche le déploiement automatique, qui exige votre accord explicite et les contrôles de `MANUAL_PRODUCTION_ACTIONS.md` § 000000000.
- **plugNmeet réel** : NOT RUN.

## 9. Recommandé

- Protéger `main` : contrôles obligatoires, environnement GitHub `production` avec approbation.
- Épingler l'empreinte SSH du serveur, au lieu de `ssh-keyscan`.
- Vérifier que le dépôt doit bien rester public.
- Prévoir React Router 7 et ReportLab ≥ 4.4.

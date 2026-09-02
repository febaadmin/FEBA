# Rapport final — livraison FEBA

---

## 1. Source utilisée

| | |
|---|---|
| Origine | `https://drive.google.com/file/d/1_XB0DUpHUOFcqO-gGCzZfLzRgLRUp2zS/view` |
| Fichier | `feba.zip` — 34 457 093 octets |
| **SHA-256** | `e06cdab5bad530087cf1a1c2c6917faff957d84b7ff48bca9e992dbb04d53c74` |
| `unzip -t` | PASS — 1 076 entrées, aucune erreur |
| Racine | `feba_v6_version_finale_corrigee/` |

L'archive a été téléchargée, vérifiée (`file`, `sha256sum`, `unzip -t`) et
extraite dans un dossier **neuf et vide**. Aucune copie antérieure n'a
servi de base.

---

## 2. Correctifs

| Priorité | Problème | Cause racine | Correction | Test | Résultat |
|---|---|---|---|---|---|
| **P1** | Documents portant `0196697363` | `get_branding()` lisait `School.phone`, colonne administrable par entité. Le numéro n'était dans aucun fichier source : il venait de la base, saisi via l'écran « Paramètres ». Aucun `grep` ne pouvait le voir. | Source institutionnelle unique `apps/schools/institution.py` (`OFFICIAL_PHONE`, rotation par `FEBA_OFFICIAL_PHONE`, refus des numéros retirés). `get_branding()` la lit ; les champs libres sont nettoyés ; migration `schools.0015` répare la base. | `test_institutional_phone.py` (20) — documents réellement produits, inspectés visuellement | ✅ **Corrigé** |
| **P1b** | Bulletins **sans aucun** numéro | Le bulletin recomposait son en-tête à partir de la seule adresse, au lieu d'utiliser la ligne d'identité commune | `_add_header()` utilise `brand.address_line` | idem | ✅ **Corrigé** |
| **P2** | « Voir le détail des formules » menait à `/feba-fha` | `<Link to="/feba-fha">` : navigation au lieu de remise du document. Le parent perdait en outre toute sa saisie (étape 12/12 du formulaire) | Composant `FhaFlyerDownload` → téléchargement du flyer officiel en PDF, plus deux règles Nginx (`Content-Disposition: attachment`, `try_files $uri =404`) | `fhaFlyerDownload.test.jsx` (6) + parcours navigateur réel | ✅ **Corrigé** |
| **P4/P5** | Instances publiques proposées par défaut | Les trois `.env.*.example` — **dont celui de production** — proposaient `JITSI_DOMAIN=meet.jit.si`, que le backend refuse déjà | Modèles pointant `meet.globalfeba.com` ; modèle de développement **vide** (aucun repli) ; guides corrigés | `test_jitsi_production_domain.py` (21) | ✅ **Corrigé** |
| **P6** | `make jitsi-health` limité au conteneur local | La cible passait obligatoirement par `docker compose exec` | `JITSI_TARGET=` pour viser la production, repli sur Python local ; contrôles DNS, TLS, HTTP, page Jitsi ; cibles `jitsi-restart`, `jitsi-config-check`, `jitsi-prod-*` | 6 mauvaises configurations injectées, **6 détectées** | ✅ **Corrigé** |
| **P7** | Aucune configuration de production Jitsi | Seule une pile de développement existait | `docker-compose.jitsi.prod.yml` : Let's Encrypt, ports 80/443, `JVB_ADVERTISE_IPS` obligatoire, `JWT_ALLOW_EMPTY=0`, `restart: always`, rotation des journaux | test de la surcouche livrée | ✅ **Corrigé** |
| **P15** | `CSRF_TRUSTED_ORIGINS` **absent** | Jamais défini. Invisible car l'API utilise JWT sans cookie — seul `/django-admin/`, exposé par Nginx, devenait inaccessible | Réglage lu depuis l'environnement, dérivé d'`ALLOWED_HOSTS` à défaut ; `SameSite=Lax` | `test_production_settings.py` (10) | ✅ **Corrigé** |
| **Audit** | Un fichier statique absent répondait `200` + HTML | `try_files … /index.html` du SPA capture aussi les fichiers. **Constaté sur le site en ligne** | `location` exacte avec `try_files $uri =404` pour le flyer | vérifié par HTTP réel | ✅ **Corrigé (flyer)** |
| **Base** | 2 tests en échec **dans l'archive source** | Contenu attendu disparu de `KNOWN_LIMITATIONS.md`, et fichier introuvable depuis le conteneur (`./backend:/app`) — contourné par une **duplication** ayant divergé | Document rétabli ; recherche du fichier en remontant l'arborescence ; montage dans `docker-compose.yml` ; duplication supprimée | tests d'origine, inchangés | ✅ **Corrigé** |

---

## 3. Résultats

### Tests backend

| Base | Avant | Après |
|---|---|---|
| PostgreSQL 16.13 | 1 111 réussis · **2 échecs** | **1 164 réussis · 0 échec** |
| SQLite | 1 151 réussis · **2 échecs** · 1 ignoré | **1 163 réussis · 0 échec · 1 ignoré** |

> Deux exécutions intermédiaires ont montré 2 échecs dans
> `test_fha_sheet_download_per_row.py`. Cause identifiée : les deux suites
> avaient été lancées **en parallèle** sur le même dossier
> `backend/private_media/`, où elles écrasaient mutuellement leurs
> fichiers. Erreur de méthode de ma part, pas un défaut du produit —
> vérifié en rejouant depuis un état vierge, puis séquentiellement.

### Frontend

| | |
|---|---|
| Tests | **191 réussis** (21 fichiers + 1 ajouté) |
| ESLint | **0 erreur**, 81 avertissements (82 dans la source ; 1 corrigé, 0 ajouté) |
| Build de production | **PASS** |

### Parcours en navigateur réel

Chromium, build de production servi par Nginx, backend Django, PostgreSQL.

| Parcours | Résultat |
|---|---|
| 1 — visiteur → formulaire FHA → flyer téléchargé | **PASS** (identique octet pour octet, mobile compris) |
| 2 — admin → paiement → reçu PDF → `0160011717` | **PASS** |
| 3 — salle virtuelle → jamais `meet.jit.si` | **PASS** (503 explicite) |
| 4 — admin FHA → salles de la bonne académie | **PASS** |
| 5 — cloisonnement, y compris IDOR | **PASS** (404 sur accès croisé) |

---

## 4. Jitsi

| | |
|---|---|
| Domaine configuré | `meet.globalfeba.com` |
| `meet.jit.si` en production | **NON** — refusé par le code, absent des modèles |
| Healthcheck | 7 contrôles : configuration, domaine non public, signature, DNS, TLS, HTTP, page Jitsi |
| JWT | HS256, 15 min, salle nommée, expiration vérifiée |
| **État réel** | **DÉGRADÉ — `meet.globalfeba.com` ne résout pas** |

`getent hosts globalfeba.com` → `62.238.38.111` ✅
`getent hosts meet.globalfeba.com` → **aucun enregistrement** ❌

Actions restantes, avec leurs commandes de vérification :
[`MANUAL_PRODUCTION_ACTIONS.md`](MANUAL_PRODUCTION_ACTIONS.md).
**Aucune n'a été effectuée, aucune n'est présentée comme faite.**

---

## 5. Documents

| | |
|---|---|
| Ancien numéro détecté | **NON** — y compris espacé, pointé, tireté, préfixé |
| Numéro officiel | **0160011717** |
| Vérifiés | reçu FEBA, reçu FHA, bulletin FEBA, bulletin FHA, fiche de préinscription, 4 certificats/diplômes |

Produits avec les deux académies portant **délibérément** l'ancien numéro
en base — l'état exact de la production — puis rendus en image et
**inspectés visuellement**.

## 6. Flyer

| | |
|---|---|
| Fichier | `frontend/public/images/feba-fha/feba-fha-flyer.pdf` (856 088 octets) |
| Source | le JPEG officiel fourni, sans retouche du contenu |
| Lien | `/images/feba-fha/feba-fha-flyer.pdf` |
| HTTP | `200` · `application/pdf` · `attachment; filename="FEBA-French-Heritage-Academy-flyer.pdf"` |
| Fichier retiré | `404` (et non un `200` HTML) |
| Téléchargement réel | **PASS** — desktop et mobile, identique octet pour octet |

---

## 7. Une divergence assumée entre l'archive et le dépôt

`.github/workflows/deploy.yml` **n'a pas été repris de l'archive**.

Le dépôt en contient une version plus avancée : sauvegarde Restic
pré-déploiement avec vérification qu'un nouveau snapshot a bien été créé,
attente de l'état sain du backend, et retour arrière. La version de
l'archive ne les a pas.

Appliquer l'archive aurait supprimé la sauvegarde automatique avant chaque
déploiement de production. Ce n'est demandé nulle part, et la conséquence —
un déploiement raté sans point de retour — est irréversible. La version du
dépôt a donc été conservée, et le fait est signalé ici plutôt que passé
sous silence. Tout le reste vient de l'archive.

---

## 8. Ce qui n'a pas été fait

- **Docker Compose n'a jamais démarré** — aucun démon disponible. Fichiers
  validés syntaxiquement, configurations Nginx validées par `nginx -t` sur
  un binaire réel.
- **Aucun appel Jitsi réel** — l'infrastructure n'existe pas encore.
- **Aucun e-mail réellement envoyé** — backend en mémoire pendant les tests.
- **Les 13 tests e2e existants** n'ont pas été joués (ils supposent Docker).
  Les cinq parcours demandés ont été écrits et exécutés séparément.
- **Aucune action DNS, Hetzner ou de secret de production.**

Détail : [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) ·
[`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) §6.

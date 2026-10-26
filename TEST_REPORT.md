# FEBA — Rapport de tests : aperçu et commentaires des bulletins, logo, favicons, onglets de visio

26 octobre 2026, branche `fix/feba-logo-favicon-visio-commentaires`, **en local
uniquement**. Version précédente : `docs/historique/TEST_REPORT_2026-10-26_commentaires_visio.md`.
Statuts : PASS · FAIL · BLOCKED · NOT RUN · SIMULATED. Un test ignoré n'est
jamais compté comme réussi. Vérification depuis l'archive extraite :
`DELIVERY_VERIFICATION_*.txt`, livré à côté du ZIP.

## 1. Tests automatisés (dépôt, code final)

| Suite | Résultat | Statut |
|---|---|---|
| Backend PostgreSQL 16 + Mailpit SMTP + plugNmeet v2.5.3 réel | **1733 réussis, 0 ignoré, 0 échec** | PASS |
| Backend SQLite | 1723 réussis, **10 ignorés** (PostgreSQL, Mailpit ou plugNmeet requis — tous exécutés et réussis sur PostgreSQL), 0 échec | PASS |
| Frontend Vitest | 329 / 329 (41 fichiers) | PASS |
| ESLint | 0 erreur (74 avertissements antérieurs ; 6 supprimés, aucun ajouté) | PASS |
| Build Vite | réussi ; favicons fournis et `apple-touch-icon` dans `dist/`, plus de `favicon.svg` | PASS |
| `nginx -t` (frontend de production) | configuration valide | PASS |
| `scripts/build_branding_assets.py --check` | dérivés conformes aux fichiers fournis | PASS |

Nouveaux tests (les tests de défaut échouent sur `575d493`, vérifié) :
- `test_bulletin_comments.py` (+15) : commentaire avant génération (ajout,
  modification, suppression, brouillon invisible des familles, PDF à la
  génération), cinq cycles après génération avec PDF relu à chaque étape et
  une URL par version, régénérations successives, erreur de sauvegarde
  (aucun succès annoncé), idempotence, conflit 409, isolation, opérations
  bloquées expirées, **deux requêtes simultanées (PostgreSQL : 200 + 409, un
  seul bulletin)**, aperçu sans écriture, aperçu = PDF officiel hormis le
  filigrane, permissions de l'aperçu, liste de révision.
- `test_branding_logo_2026_10_26.py` (23) : priorité du logo actif, image
  du PDF inspectée (couleur du logo activé), isolation, téléversement
  (valide, faux PNG, SVG, trop petit, GIF), académie imposée, contrainte et
  activation atomique, version active protégée, API publique sans connexion,
  favicons fournis à l'octet près puis dérivés, version/URL changées, autre
  académie inchangée, commande de régénération (aperçu, application,
  idempotence, échec qui conserve l'ancien fichier), diplômes et certificats
  (blason incrusté remplacé seulement après activation), fichiers fournis
  installés et `index.html` sans ancienne icône, logo de repli recopié par
  `init_academies` sans effet et retiré par la migration `0019` (aller-retour).
- `test_visio_multi_academies.py` (+6) : titres exacts par académie, jeton
  re-signé ou modifié refusé, rechargement après expiration (≤ 24 h), CORS,
  titre dans la réponse d'adhésion, script client installé par le setup.
- Frontend : `BulletinPreviewDialog.test.jsx` (4), `useBranding.test.jsx` (5),
  `Seo.test.jsx` (2), titres des pages de session et de fin de réunion (3).

## 2. Validations réelles (local, Chrome)

| Contrôle | Résultat | Statut |
|---|---|---|
| Commentaires : 3 cycles ajout / modification / suppression, 2 élèves, avant ET après génération, pages Notes et Bulletins, rechargement + relecture en base après chaque opération | **72 / 72** (avant correction : 12 échecs / 24) | PASS |
| Aperçu avant génération : aperçu, commentaire saisi rendu, enregistrement sans génération, génération définitive, brouillon annulé, modification et suppression régénérées | 0 bulletin créé par l'aperçu ; **5 PDF relus conformes** | PASS |
| Révision d'une génération de classe, aperçu individuel au premier plan, confirmation, bilan | 6 / 6 régénérés, 0 échec | PASS |
| Logo : site public sans connexion (FEBA et /feba-fha), téléversement par l'admin FEBA (académie 2), barre latérale et favicons changés sans rechargement, enseignant / parent / élève / site public, FEBA FHA inchangée, bulletin régénéré (image inspectée : nouveau logo), logo identique après redémarrage du backend | conforme | PASS |
| Favicon FEBA sans logo activé = fichier fourni, octet pour octet | conforme | PASS |
| Onglet de visio sur la VRAIE page plugNmeet : FEBA et FEBA FHA, ouverture / réunion / rechargement / page de fin, favicon de l'académie | titres exacts, favicons conformes, réunion fonctionnelle | PASS |
| Sondes d'isolation (4 664 requêtes) et d'escalade (133 routes) | 0 fuite, 0 erreur serveur, aucune écriture illégitime | PASS |
| Scénarios e2e (8) | tous verts | PASS |

## 3. Non exécuté ou bloqué

| Contrôle | Statut |
|---|---|
| Hetzner, préproduction, plugNmeet de production | BLOCKED (SSH refusé) |
| SMTP Hostinger, Twilio | BLOCKED |
| Partage d'écran, réunion entre réseaux distincts | NOT RUN |
| Navigation privée et CDN réels de production | NOT RUN (cache vérifié par URL versionnées et en-têtes) |

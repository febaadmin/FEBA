# FEBA — Rapport final : aperçu et commentaires des bulletins, logo actif, favicons, onglets de visioconférence

26 octobre 2026 · branche `fix/feba-logo-favicon-visio-commentaires`.
Départ : commit `575d493` (archive `FEBA_VERSION_COMMENTAIRES_BULLETINS_VISIO_MULTI_ACADEMIES.zip`),
qui contient déjà toutes les corrections des versions précédentes, dont celles
de `FEBA_VERSION_PLUGNMEET_SMS_AUDIT_COMPLET.zip` (plus ancienne : elle n'a pas
remplacé le dépôt). Commit livré : `SOURCE_COMMIT.txt` dans l'archive.

Statuts : **PASS** · **FAIL** · **BLOCKED** · **NOT RUN** · **SIMULATED**.
Détail : `TEST_REPORT.md`. Limites : `KNOWN_LIMITATIONS.md` § 00000.
Actions de l'exploitant : `MANUAL_PRODUCTION_ACTIONS.md` § 0000.

**Lieu des validations : en local uniquement** (piles Docker isolées du poste,
plugNmeet v2.5.3 local, Chrome réel). Ni préproduction ni Hetzner (accès SSH
refusé). Rien n'a été déployé, migré ni envoyé en production.

---

## 1. Commentaires des bulletins — causes racines et corrections

| Cause (reproduite) | Correction |
|---|---|
| La régénération SUPPRIMAIT le bulletin puis le recréait (commentaire perdu, identifiant changé) ; un échec effaçait l'ancien PDF | (version précédente, conservée) bulletin réutilisé ; PDF construit en mémoire puis remplacé seulement après réussite ; nom de fichier unique |
| **Avant la première génération, impossible d'ajouter, modifier ou supprimer un commentaire** sans générer le bulletin (12 échecs sur 24 opérations dans le scénario réel) | `POST /bulletins/comment-target/` : élève + année + période, bulletin généré ou non ; brouillon sans PDF (invisible des familles et des enseignants) ; verrou de ligne ; 409 si modifié entre-temps ; PDF produit seulement s'il y a des notes |
| Une opération groupée restée « en file » (worker arrêté) bloquait toutes les suivantes (409) indéfiniment | opérations bloquées expirées (10 / 60 min) |
| L'interface affichait l'état local comme acquis | confirmation affichée uniquement d'après la réponse du serveur ; zone verrouillée pendant l'enregistrement ; erreurs affichées, saisie conservée |

Résultat réel (Chrome, rechargement de la page et relecture en base après
CHAQUE opération) : **72/72 opérations confirmées** (3 cycles × ajout /
modification / suppression × 2 élèves × avant et après génération × pages
Notes et Bulletins), contre 12 échecs sur 24 avant correction.

## 2. Aperçu des bulletins avant génération

- `render_bulletin_pdf` : rendu SANS écriture, partagé par la génération
  officielle et l'aperçu (mêmes calculs, même mise en page, même identité).
  `POST /bulletins/preview/` renvoie le PDF en mémoire, filigrané « APERÇU » :
  aucun bulletin créé, aucun PDF officiel remplacé, aucun fichier temporaire.
- Fenêtre « Aperçu du bulletin » (page Bulletins : bouton principal et
  bouton « Aperçu » de chaque ligne ; page Notes) : élève, année, période,
  aperçu PDF réel, commentaire éditable, **Actualiser l'aperçu** (rend le
  commentaire saisi), **Enregistrer le commentaire** (sans générer),
  **Supprimer le commentaire**, **Générer le bulletin définitif** (après
  confirmation explicite ; un commentaire saisi est d'abord enregistré),
  **Annuler** (rien n'est enregistré).
- Générations par classe / académie : étape de **révision** (portée, année,
  période, nombre de bulletins, liste des élèves avec aperçu individuel,
  commentaire commun facultatif) puis confirmation explicite ; bilan réel.

Vérifié en navigateur réel : aperçu avant génération (0 bulletin avant,
0 après), commentaire saisi rendu dans l'aperçu, enregistrement sans
génération, génération définitive, brouillon annulé non enregistré,
modification et suppression régénérées — **5 PDF relus, tous conformes** ;
aperçu individuel depuis la révision d'une classe au premier plan.

## 3. Logo actif — source de vérité

| Cause (reproduite) | Correction |
|---|---|
| `get_branding().document_logo` prenait l'image statique AVANT le logo activé : **tous les PDF** l'ignoraient | ordre : logo documentaire administré explicitement → logo activé de l'académie → repli de CETTE académie (FEBA : logo fourni) ; jamais celui d'une autre |
| Page Branding : académie = « premier établissement » ou `"1"` — **constaté sur la pile de test : le logo FEBA téléversé par le super administrateur avait été posé sur FEBA FHA (académie n° 1)** | académie du contexte ; super administrateur : sélection obligatoire ; contrôle serveur |
| `/branding/active/` : 401 sans connexion → site public et page de connexion toujours au logo statique | API publique en lecture seule `/schools/public-branding/<code>/` (logo, favicons, titre de visio, couleurs ; rien d'administratif) |
| Client privé : la réponse du branding rejetée comme « périmée » pendant l'amorçage de la portée → barre latérale au logo embarqué (trouvé en navigateur réel) | client public dédié, sans jeton ni portée |
| Même nom de fichier → même URL → ancienne image en cache ; plusieurs versions actives possibles ; tout fichier « .png » accepté | nom unique `branding/<académie>/<uuid>` ; URL versionnées `?v=` ; contrainte « une version active » (migration `schools.0018`) ; activation atomique ; image décodée (PNG/JPEG/WebP, 5 Mo, 64–6000 px) ; version active non supprimable |
| Diplômes / certificats : blason **dans les pixels du fond** | après activation, zone du blason recouverte (couleur papier) et logo actif apposé ; sans logo activé, visuel officiel intact |
| Reçus : ancien supprimé puis nouveau sous le MÊME nom | nom unique, ancien supprimé après réussite |
| PDF déjà stockés | `manage.py branding_refresh_documents --academy CODE [--apply]` (aperçu, régénération atomique, idempotente, bilan ; rapports envoyés conservés) |

Vérifié en navigateur réel : site public sans connexion (FEBA et /feba-fha),
téléversement par l'admin FEBA (école n° 2, plus 1), barre latérale et
favicons changés **sans rechargement**, enseignant / parent / élève / site
public au nouveau logo, **FEBA FHA inchangée**, bulletin régénéré
contenant le nouveau logo (image du PDF inspectée), logo identique après
redémarrage du backend.

## 4. Favicons fournis

Installés tels quels (`branding/source/` → `frontend/public/`,
`backend/feba_project/static_files/`) ; `favicon.svg` (le triangle) retiré ;
`apple-touch-icon` 180 px dérivé du logo fourni par
`scripts/build_branding_assets.py` (reproductible, `--check`). Favicons par
académie servis par l'API (FEBA : fichiers fournis à l'octet près tant
qu'aucun logo n'est activé ; ensuite dérivés du logo actif ; FEBA FHA : son
propre logo). Cache : URL versionnées ; favicons fixes revalidés à l'heure ;
`index.html` en `no-cache`.

## 5. Onglets de visioconférence

Cause : le client plugNmeet impose `document.title` = nom de la salle à
chaque mise à jour des métadonnées ; la page FEBA qui redirige ne pouvait
donc rien imposer. Solution réelle sur le client servi :
`plugnmeet/client-branding/feba-branding.js`, injecté par
`scripts/plugnmeet_setup.sh` (idempotent, redémarre le serveur plugNmeet qui
garde `index.html` en mémoire) ; l'académie est déterminée par FEBA à partir
du **jeton plugNmeet dont la signature est vérifiée** (`POST
/api/virtual-rooms/meeting-branding/`) — un paramètre modifié ne change rien.

Vérifié sur la **vraie page plugNmeet** (local) : FEBA « FEBA - Faith &
Excellence Bilingual Academy », FEBA FHA « FEBA FHA - FEBA », à l'ouverture,
dans la réunion, après rechargement et sur la page de fin ; favicon
identique à celui de l'académie ; réunion fonctionnelle. Pages publiques
/feba-fha : titres à l'identité FEBA FHA.

## 6. Audit

Sondes rejouées sur la pile de démonstration : lecture 4 664 requêtes
(234 routes de liste, 194 de détail) → **0 fuite, 0 erreur serveur** ;
écriture par rôle (133 routes) → aucune écriture illégitime ; défauts
trouvés et corrigés pendant les tests réels : branding rejeté par la garde
de portée, aperçu masqué derrière la révision, client plugNmeet non
rechargé, reçus sous un nom fixe.

## 7. Migrations

`schools.0018_branding_unique_active` (contrainte ; la plus récente des
versions actives reste active ; aucune suppression ; réversible).

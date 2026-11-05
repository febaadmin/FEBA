# Aperçu des bulletins (PDF) — phase 7

## 1. Symptôme
Fenêtre « Aperçu du bulletin » : zone vide et message « L'aperçu n'a pas pu être affiché. Ouvrez ou téléchargez le PDF. », alors que « Ouvrir le PDF officiel » fonctionnait. Signalé une première fois en phase 6 (« Ce contenu est bloqué ») ; la correction de phase 6 (rendu pdf.js dans des `<canvas>` au lieu d'un cadre) était juste dans son principe mais restait cassée **en production uniquement**.

## 2. Cause racine (reproduite en production le 05/11)
- pdf.js charge son *worker* depuis le fichier `assets/pdf.worker.min-*.mjs` produit par Vite.
- L'image `nginx:1.28.1-alpine` (conteneur frontend) **ne connaît pas l'extension `mjs`** dans `mime.types` : le fichier partait en `application/octet-stream`.
- nginx ajoute `X-Content-Type-Options: nosniff` : le navigateur refuse alors d'exécuter le script.
- Erreur exacte reproduite contre globalfeba.com : `Setting up fake worker failed: "Failed to fetch dynamically imported module: https://globalfeba.com/assets/pdf.worker.min-yatZIOMy.mjs"`.
- Invisible en CI et en local : `vite preview` sert `.mjs` avec le bon type.
- Écartés après vérification : CSP (`script-src 'self'` autorise le worker de même origine ; aucune violation), CORS (même origine), authentification et permissions (le PDF est bien reçu : le lien officiel fonctionne), X-Frame-Options (plus de cadre depuis la phase 6).

## 3. Correction (aucune protection assouplie, CSP inchangée)
- `frontend/vite.config.js` : tout script émis porte l'extension `.js` (servie en `application/javascript`).
- `frontend/scripts/verifier_types_assets.mjs` + étape CI : chaque fichier du build est contrôlé contre le `mime.types` **extrait de l'image nginx de production** ; une régression de ce type bloque désormais la CI.
- `ApercuPdf.jsx` journalise la cause d'un échec de rendu (diagnostic futur).
- PR #99 (fusionnée, déployée le 05/11).

## 4. Architecture de l'aperçu
1. Le formulaire demande l'aperçu (élève, année, période, commentaire) ; le serveur génère le PDF **avec le même générateur que le bulletin définitif** et applique les mêmes permissions.
2. Le PDF arrive en mémoire (blob) ; pdf.js (worker de même origine, `isEvalSupported: false`) dessine chaque page dans un `<canvas>` : aucun cadre, aucune URL `blob:` dans un cadre, aucune exception de sécurité.
3. « Actualiser l'aperçu » régénère avec le commentaire saisi ; « Enregistrer le commentaire » le conserve ; « Générer le bulletin définitif » produit le document officiel ; « Ouvrir le PDF officiel » passe par un lien signé.

## 5. Vérifications
| Vérification | Résultat | Où |
|---|---|---|
| Rendu d'un PDF par le chunk pdf.js du build, servi par `nginx:1.28.1-alpine` + `frontend/nginx.prod.conf`, CSP de production et `nosniff` | page rendue, pixel attendu (0,0,255) | local, image nginx de production |
| Même test contre globalfeba.com **avant** correctif | échec identique à la capture | production |
| Même test contre globalfeba.com **après** déploiement de #99 | page rendue, aucune erreur ; worker `pdf.worker.min-yatZIOMy.js` servi en `application/javascript` | **production** |
| Parcours complet (élève, année, période, aperçu, commentaire, actualisation, enregistrement, génération, PDF officiel) | OK | E2E `apercu_pdf` (CI, CSP de production injectée) |
| Contrôle MIME du build en CI | OK (385 fichiers) | CI |
| Isolation : un utilisateur ne peut pas obtenir le bulletin d'un élève hors de son périmètre | OK (tests existants phase 5–6) | CI |

## 6. Non vérifié
- **Parcours connecté en production avec un vrai compte** (aperçu d'un bulletin réel dans le navigateur) : le navigateur intégré n'est pas connecté à globalfeba.com et je ne saisis pas de mot de passe. Le rendu du moteur PDF en production est, lui, vérifié (ligne 3 du tableau). Action : se connecter une fois dans le panneau navigateur, ou ouvrir l'aperçu d'un bulletin et confirmer l'affichage.
- Safari et Firefox : non testés (seul Chrome est disponible ici).

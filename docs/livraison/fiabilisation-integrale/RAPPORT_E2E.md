# Tests navigateur (E2E)

**Environnement :** GitHub Actions et poste local. PostgreSQL jetable, `seed_demo_data` avec des mots de passe générés à chaque exécution, serveur Django réel, application construite, Chromium. **Ce ne sont pas des tests de production.**

**Suite :** `e2e/ci/`, lancée par le job « Parcours navigateur (E2E) » de `.github/workflows/ci.yml` sur chaque PR.

| Scénario | Contrôles | Contenu |
|---|---|---|
| connexion | 30 | 5 profils à 0, 250 et 600 ms ; double clic ; Entrée ; téléphone ; anglais ; mauvais mot de passe ; compte inconnu ; coupures ; 429, 502, 504 ; rechargement ; déconnexion et reconnexion ; session expirée |
| sélecteur | 15 | Clic neutre, Échap, autre bouton, menu latéral, bascule, persistance, ordinateur et téléphone, admin sans sélecteur |
| navigation | 10 | Toutes les pages des 5 profils, 1366 et 390 px : erreurs JS, 5xx, débordement, déconnexion |
| formulaires | 8 | Champ obligatoire, double envoi sous 500 ms (paiement, classe, annonce), persistance, recherche, tri au clavier, pagination |
| messagerie | 5 | Aller-retour enseignant et parent, non-lu |
| données | 34 | Notes, bulletins et PDF, paiements et reçus, fichiers, avatar SVG, comptes, rôles changés sans reconnexion, compte désactivé |
| modules | 25 | Site public FR et EN, préinscription, champ piège, export protégé, relances, transactions, rapports mensuels, admissions FHA |
| suivi | 13 | Référentiel, compétences, import, archivage, évaluation de classe, graphique, objectifs, plans |
| examens | 16 | 9 types, droits, rechargement, coupure, remise unique, correction, publication, clôture, corrigé, parents |
| flash | 1 | Voile du menu mobile |

## Résultats

| Date | Environnement | Commit | Contrôles | Échecs |
|---|---|---|---|---|
| 03/11 | GitHub Actions, PR #63 | `381a836` | 131 | 0 |
| 03/11 | GitHub Actions, PR #65 | `6ceb792` | 156 | 0 |
| 03/11 | Local, backend non-root (image de la PR #64) | - | 131 | 0 |

**Preuve que la suite détecte les régressions :** l'ancien bug de connexion, réintroduit, fait échouer 6 contrôles.

**Pendant la mise au point, 9 échecs venaient de mes tests**, pas de l'application : règle de promotion de rôle, corrigé visible seulement après clôture, clic tombant sur une ligne, bouton nommé « English ». L'application n'a jamais été modifiée pour faire passer un test.

**Non couvert :** classes virtuelles plugNmeet (pas de serveur en CI), conversions Word (LibreOffice absent du job E2E), envoi réel d'e-mails, téléphone réel, lecteur d'écran.

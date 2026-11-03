# Non-régression

| Fonction | Test | Résultat |
|---|---|---|
| Connexion | `useAuth.connexion.test`, `login.mjs` | Réussi |
| Erreurs de connexion | `LoginPage.erreurs.test`, `auth2.mjs` | Réussi |
| Double envoi | `sansDoublon.test`, `useFormulaire.test`, `dbl.mjs` | Réussi |
| Portée d'académie | `connexion.test`, `academyScope.test` | Réussi |
| Sélecteur | `EntitySwitcher.test`, `sel.mjs` | Réussi, 1 KO de script expliqué |
| Flash | `sansFlash.test` | Réussi. `flash.mjs` non rejoué après React Router 7 |
| Pages | `sweep.mjs`, 244 ouvertures | 0 erreur JS, 0 débordement |
| Examens | `parcours.mjs` | 0 échec |
| Notes, bulletins, paiements, fichiers | `mod2.py` | Réussi |
| Isolation | `test_isolation_2_7_19_academies`, PostgreSQL | Réussi |
| Personnes | `test_securite_personnes`, PostgreSQL, témoin positif | Réussi |
| Attaques | `test_securite_attaques`, PostgreSQL | Réussi |
| Volume SQL | `VolumeTests` | Réussi |
| CI complète | PR #60, #61 et de livraison | 10 contrôles verts |

Les scripts `*.mjs` et `mod2.py` vivent hors du dépôt, dans mon espace de travail : ils ne sont **pas encore automatisés en CI**. C'est le prochain chantier pour éviter que ces défauts reviennent.

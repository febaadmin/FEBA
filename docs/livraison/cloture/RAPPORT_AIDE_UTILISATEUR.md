# Centre d'aide et guides utilisateur

Date : 04/11/2026. PR #72 (fusionnée). Environnements : tests unitaires, navigateur local (base jetable `seed_demo_data`), CI GitHub Actions.

## 1. Avant

La page Aide contenait trois rubriques : suivi d'un élève, premier examen, glossaire. L'entrée de menu dépendait d'un module optionnel (`suivi_pedagogique` pour le personnel, `evaluations_en_ligne` pour les familles). Conséquence : **une académie sans ces modules n'avait aucune aide**.

## 2. Méthode

1. Inventaire des menus des 5 profils (fichiers `layouts/*Layout.jsx`) et des routes (`router/index.jsx`).
2. Extraction des libellés réels de chaque écran : boutons, champs, messages de réussite et d'erreur. Chaque procédure reprend ces libellés exacts.
3. Vérification des règles côté serveur, par exemple :
   - justification obligatoire pour supprimer une note ;
   - un administrateur ne crée que des enseignants, des parents et des élèves ;
   - pas de « mot de passe oublié » par e-mail dans FEBA.

## 3. Contenu

- **52 articles**, répartis en 9 catégories : prise en main, administration, gestion scolaire, gestion pédagogique, vie scolaire, paiements, documents et fichiers, site vitrine et admissions, espace famille.
- Chaque article indique :
  - le nom et le module ;
  - à quoi sert la fonctionnalité ;
  - qui peut l'utiliser et les prérequis ;
  - où la trouver, avec un lien « Ouvrir » ;
  - les étapes numérotées et les champs importants ;
  - le résultat attendu, les erreurs fréquentes et leurs solutions ;
  - les effets sur les autres modules et les permissions.
- Questions fréquentes (5), dépannage (5) et glossaire (15 termes), filtrés par profil.
- Articles visibles par profil :

| Profil | Articles |
|---|---|
| Super administrateur | 47 |
| Administrateur | 43 |
| Enseignant | 19 |
| Parent | 13 |
| Élève | 13 |

  Un élève ne voit aucune procédure d'administration. L'administration globale (académies, incidents, modules, administrateurs) est réservée au super administrateur.
- Recherche :
  - insensible aux accents et aux majuscules ;
  - dans la langue de l'interface ;
  - tous les mots saisis doivent apparaître ;
  - synonymes (« superadmin », « mdp », « receipt »…).
- Lien direct `?article=` (article ouvert et amené à l'écran) et catégorie dans l'adresse (`?categorie=`).
- Si un module n'est pas activé pour l'académie sélectionnée, l'article le signale et n'affiche pas de lien.
- Bilinguisme : chaque texte est une paire français/anglais, affichée selon la langue de l'interface (`useI18n`), avec bascule immédiate.
- L'entrée « Aide » est toujours présente dans les 5 menus.
- Identité visuelle : cartes, bleu marine FEBA (`feba-navy`), pastilles et typographie existantes.

## 4. Guides

`GUIDE_UTILISATEUR_FEBA_FR.md` et `FEBA_USER_GUIDE_EN.md` sont **générés** depuis la même source (`node frontend/scripts/generer_guides.mjs <dossier>`). Le guide et l'aide intégrée ne peuvent donc pas diverger.

## 5. Tests

| Test | Type | Résultat |
|---|---|---|
| `frontend/src/aide/aide.test.js` (19 tests) | unitaire | 19/19. Couvre : identifiants uniques, catégories et rôles valides, deux langues pour chaque texte, liens vers des routes réelles, **chaque écran de chaque menu documenté**, filtrage par profil, recherche (accents, langue, tous les mots), catégorie, glossaire |
| Scénario E2E `aide` (38 contrôles) | navigateur local, puis CI | 38/38. Couvre : 5 profils (entrée de menu, articles du profil, FAQ, glossaire, article déplié, lien vers le module sans erreur JS ni 5xx), recherche « bulletin » et sans accent, catégorie, anglais (titre, contenu, recherche « receipt »), téléphone 390 px sans débordement, lien direct |
| Vitest complet | unitaire | 500/500 |

## 6. Maintenance

Le contenu est centralisé dans `frontend/src/aide/articles.js`. Le test échoue si :
- un nouvel écran de menu n'a pas d'article ;
- un lien pointe vers une route supprimée ;
- une traduction manque.

## 7. Limites

- Les procédures décrivent les écrans au 04/11/2026. Une évolution d'écran doit être répercutée dans l'article (le test ne vérifie pas le texte des boutons).
- Pas de captures d'écran dans les articles. C'est volontaire : elles vieillissent à chaque évolution graphique.
- La validation du contenu par un utilisateur réel de chaque profil reste à faire (relecture humaine).

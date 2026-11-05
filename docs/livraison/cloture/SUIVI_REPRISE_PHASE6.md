# Point de reprise : phase 6 (05/11/2026)

## État

| Élément | Valeur |
|---|---|
| Dernier commit validé | `d3b8b9b` (main) |
| PR fusionnées en phase 6 | #95 (A à D), #96 (centre de pilotage), #97 (données détachées) ; toutes par **commit de fusion** |
| Production | `d3b8b9b` = main, vérifiée le 05/11 (voir ci-dessous) |
| Tests | backend 2138 OK ; frontend 573 OK ; E2E 330/330 sous CSP de production |

## Terminé

- **Aperçu du bulletin** : dessiné par pdf.js, CSP intacte.
- **Défilement** : corrigé dans les 5 layouts, contrôlé sur toutes les pages.
- **Colonne « Classe »** : corrigée, avec synchronisation et règle unique pour les statistiques de classe.
- **« Non calculable »** : expliqué, avec lien vers « Tarifs et échéances ».
- **Centre de pilotage visuel** : livré.
- **Données détachées par une désinscription** : rattachées automatiquement.
- **E2E** : CSP de production appliquée, pages tirées des menus réels.

## Ce qui attend une personne

1. **Autoriser ou non** les deux corrections de données : simulation d'abord, journal et retour arrière prévus.
   ```bash
   docker exec feba_backend_prod python manage.py completer_classes_inscriptions --appliquer --journal /app/journal_classes.json
   docker exec feba_backend_prod python manage.py rattacher_donnees_inscriptions --appliquer --journal /app/journal_rattachement.json
   ```
   - La première renseigne la classe de 77 inscriptions, à partir de la classe actuelle de la même année.
   - La seconde rattache 15 notes à l'inscription existante de leur élève.
   - L'affichage est déjà correct sans ces opérations.
2. **Vérifier 5 paires de notes identiques** : 292/303, 223/225, 680/690, 927/978, 475/476. S'agit-il de deux évaluations ou d'un doublon ?
3. **Comptes** : profil parent du superadmin 191 (liens 83 et 84) ; compte élève 209 sans fiche.
4. **Saisir les tarifs et échéances** des deux académies.
5. **Root** : éprouver la restauration de la sauvegarde FEBA (voir `SUIVI_REPRISE.md`).

## Prochaine action exacte

Production vérifiée sur `d3b8b9b`. Prochaine étape de l'audit :
- fonctionnalité facultative AF P6-K (nginx `default_server`) ;
- tableau de bord parent (132 requêtes).

# Fiabilisation intégrale de FEBA

**La mission n'est pas terminée :** voir `RAPPORT_AUDIT_GLOBAL.md`.

Niveaux employés : **Production** (déployé et contrôlé), **Déployé** (fichiers en production, comportement non vu connecté), **Local** (Chrome ou PostgreSQL isolés), **Non testé**, **Décision humaine**, **Risque accepté**.

| Commencer par | Pour |
|---|---|
| `RAPPORT_AUDIT_GLOBAL.md` | État de chaque critère |
| `GUIDE_VALIDATION_HUMAINE.md` | Vos actions et décisions |
| `INVENTAIRE_BUGS_ANOMALIES.md` | Défauts et preuves |
| `RAPPORT_DISPONIBILITE_502.md` | Déploiement sans coupure |
| `PROCEDURE_ROLLBACK.md` | Retour arrière |
| `RAPPORT_E2E.md` | Tests navigateur dans la CI (156 contrôles) |
| `MATRICE_MODULES_VALIDES.md` | Ce qui est exercé, module par module |
| `RAPPORT_SECURITE_FINAL.md` | État de sécurité, Gitleaks, images, étude HttpOnly |
| `RAPPORT_DEPLOIEMENT_SANS_INTERRUPTION.md` | Mesures en production pendant 3 déploiements |
| `RAPPORT_PLUGNMEET_CSP.md` | Classes virtuelles et CSP |
| `RAPPORT_RESTAURATION.md` | Sauvegardes et commande Restic |
| `RAPPORT_ARCHIVE_FINALE.md` | Contenu de l'archive |

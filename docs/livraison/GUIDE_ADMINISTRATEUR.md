# Guide administrateur : suivi et examens

## Ouvrir les modules

Réservé au superadministrateur : **Modules pédagogiques**, académie par académie.

| Case | Effet |
|---|---|
| Suivi pédagogique | Ouvert au personnel |
| Examens et évaluations | Ouvert au personnel et aux élèves |
| Accès des élèves et des parents au suivi | **Publie aux familles** le suivi validé et les rapports publiés. À décider par l'établissement |

## Affectations des enseignants

**Enseignants**, icône **Affectations** : cochez les matières réellement enseignées par classe, puis **Enregistrer et confirmer**. Cette grille décide du droit de noter, d'évaluer des compétences et de créer des épreuves. Les lignes « À confirmer » viennent de la reprise automatique.

## Réglages

- **Suivi pédagogique > Référentiels** : référentiels, compétences, libellés des niveaux.
- **Suivi pédagogique > Alertes** : règles et seuils de l'académie.
- Poids de la progression : API `suivi/parametres/modifier/`.

## Règles à connaître

- Le suivi n'écrit jamais dans les notes.
- Seul un transfert explicite crée une note depuis une épreuve, une fois par élève et par épreuve.
- Moyennes, coefficients et bulletins restent gérés par le module de notes.
- Un bulletin déjà généré est signalé « PDF à régénérer » si une note change après sa génération.

Détails : `docs/SUIVI_PEDAGOGIQUE.md`, `docs/EXAMENS_EN_LIGNE.md`, `docs/RAPPORTS_ET_ALERTES.md`.

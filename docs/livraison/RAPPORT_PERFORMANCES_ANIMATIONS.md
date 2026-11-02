# Performances et animations

- **Aucune dépendance ajoutée :** framer-motion et recharts étaient déjà présents.
- **`prefers-reduced-motion` :** `MotionConfig reducedMotion="user"`, et animations des graphiques coupées.
- **Pages en chargement différé**, comme le reste de l'application.

**Non mesuré :** fréquence d'images, temps de rendu sur appareil modeste, poids exact ajouté, charge de 100 élèves simultanés. Aucune saccade n'a été constatée, sans mesure à l'appui.

**Point à surveiller :** la fiche calcule séries et chronologie à chaque ouverture, et la liste d'élèves calcule la progression élève par élève. Cela reste à mesurer sur une classe nombreuse.

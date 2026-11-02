# Sélecteur d'académie

**Cause :** la PR #53 a ajouté `backdrop-blur` à l'en-tête, ce qui crée un contexte d'empilement et un bloc conteneur pour les `fixed`.
- Le voile `fixed inset-0` de fermeture ne couvrait plus que l'en-tête.
- Le menu passait sous le contenu de la page.

**Correction :** `useFermetureExterieure` en phase de capture (clic, toucher, Échap, focus, changement de page). Voile supprimé. Couches : en-tête 15, voile mobile 16, menu 20.

| Scénario | Ordinateur | 390 px |
|---|---|---|
| Menu au-dessus de la page | Oui | Oui |
| Zone vide | Oui | Oui |
| Menu latéral et changement de page | Oui | Non testé : menu latéral fermé sur mobile |
| Autre bouton | Oui | Oui, clic et toucher |
| Échap | Oui | Oui |
| Ouvertures répétées | Oui | Oui |
| Choix d'une académie, fermeture, persistance | Oui | Oui |
| Administrateur : pas de sélecteur | Oui | Non testé |

Bascule côté serveur non modifiée. Les données restent protégées par l'en-tête de portée et le remontage de la page, déjà testés.

Production : déployé, **non vu à l'écran connecté**.

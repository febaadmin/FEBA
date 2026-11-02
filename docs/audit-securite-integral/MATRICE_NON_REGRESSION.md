# Non-régression

Rejoué sur la branche de la PR #57, en local.

| Contrôle | Résultat |
|---|---|
| Balayage des pages | Voir `RAPPORT_DEPLOIEMENT.md` |
| Parcours d'examen | 0 échec |
| Sélecteur | 21 réussis. 1 KO de script : bouton visé caché sous le menu. Refait par clic et toucher sur un bouton visible : réussi |
| Objectifs | Réussi |
| Classe, paiement, reçu, devoir | Réussi |
| Frontend | Voir CI |
| Backend PostgreSQL et SQLite | Voir CI |

Composants partagés modifiés : `EntitySwitcher` (5 profils), `.barre-haute`, `api/index.js` (toutes les lectures), `useFermetureExterieure`.

**Deux régressions m'ont échappé avant cette mission : #49 et #53, toutes deux sur le CSS commun.** Le balayage ne testait pas les interactions, seulement l'ouverture des pages.

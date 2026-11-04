# Tests de bout en bout (E2E)

Date : 04/11/2026.
- Suite : `e2e/ci/`, avec playwright-core et Chromium.
- Exécution : job CI « Parcours navigateur (E2E) », lancé à chaque PR et avant chaque déploiement.
- Données : base PostgreSQL **jetable**, remplie par `seed_demo_data`, avec des mots de passe générés pour chaque exécution et masqués. Aucune donnée de production n'est utilisée et aucune écriture n'est faite en production.

## Résultat de référence

Exécution CI du déploiement `cb47bfd` (après fusion de #72, #73 et #74) : **210 contrôles, 0 échec**.

| Scénario | Contrôles | Durée | Ce qui est vérifié |
|---|---|---|---|
| `connexion` | 31 | 122 s | Première tentative des 5 profils sous 0, 250 et 600 ms de latence ; double clic (une seule requête) ; touche Entrée ; téléphone ; anglais ; mauvais mot de passe ; compte inconnu ; coupures, 429, 502 et 504 ; sessions |
| `comptes` | 16 (17 après #75) | 16 s | Logo de /login vers l'accueil public (ordinateur, tablette, téléphone, anglais, avec session, sans soumission du formulaire) ; réinitialisation du mot de passe d'un superadmin de test (refus si le mot de passe de l'auteur est faux, connexion avec le nouveau mot de passe, changement imposé, auteur toujours connecté) ; refus pour un admin (403) ; écriture refusée avec motif affiché (#75) |
| `aide` | 38 | — | 5 profils : entrée de menu, articles du profil, FAQ, glossaire, article déplié, lien vers le module. Recherche, catégorie, anglais, téléphone, lien direct |
| `selecteur` | 16 | 21 s | Menu d'académie au-dessus de la page ; fermeture par clic dans une zone vide, Échap et choix ; bascule persistée ; ordinateur et téléphone |
| `navigation` | 10 | 199 s | Tous les écrans de `routes.json` pour les 5 profils : aucune erreur JS ni 5xx, aucun débordement mobile |
| `formulaires` | 9 | 27 s | Création, modification, double envoi |
| `messagerie` | 5 | 15 s | Envoi, réponse, destinataires autorisés |
| `donnees` | 33 | 8 s | Notes, suppression justifiée et restauration, bulletins (auteur, doublons), rôles (élévation et refus), isolement entre académies et entre familles |
| `modules` | 25 | 22 s | Site public et préinscription (piège à robots), export CSV neutralisé, relances, transactions par carte, rapports mensuels, admissions FHA |
| `suivi` | 12 | 34 s | Référentiels, évaluation, objectifs, rapports |
| `examens` | 14 | 82 s | Banque, épreuve, publication, passage, clôture, corrigé, résultats |
| `flash` | 1 | 10 s | Aucun flash lumineux lors des changements de page |

## Mutations (le test détecte bien le défaut)

| Défaut réintroduit | Résultat |
|---|---|
| Ancien bogue de connexion (phase 2) | 6 contrôles en échec |
| Gestionnaire d'erreur d'écriture retiré (#75) | « écriture refusée : motif affiché » en échec, aucun message |

## Exécutions locales de cette phase

| Lot | Scénarios | Résultat |
|---|---|---|
| #70 | `comptes`, `connexion` | 47/47 |
| #72 | `aide` | 38/38 |
| #75 | `comptes`, `selecteur`, `formulaires` | 17/17, 25/25 |

## Limites

- Base de démonstration, et non les données réelles. Les parcours avec de vrais comptes en production n'ont pas été rejoués (aucun compte de production créé, aucun mot de passe demandé).
- Pas de salle plugNmeet réelle en CI : le contrôle de santé visio renvoie 503 sans serveur, ce qui est attendu et exclu des erreurs.
- Un seul navigateur (Chromium). Safari et Firefox ne sont pas couverts.

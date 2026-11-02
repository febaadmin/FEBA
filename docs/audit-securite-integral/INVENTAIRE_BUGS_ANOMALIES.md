# Bugs et anomalies

| # | Anomalie | Origine | Détecté | Reproduit | Corrigé | Testé | Local | Production | Humain |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Sélecteur d'académie qui reste ouvert et passe sous la page | **Ma PR #53** | Oui | Oui | Oui | Oui | Oui | Fichiers déployés par #55 | À confirmer à l'œil |
| 2 | Notes supprimées dans les tableaux de bord élève et enseignant | Ancien, le gestionnaire inclut les supprimées | Oui | Non en production | Oui | Oui | Tests | Déployé par #56 | Non |
| 3 | Objectif archivé compté | Mon choix de la PR #50 | Oui | Oui | Oui | Oui | Tests | Déployé par #56 | Non |
| 4 | Faux positif d'isolation | Détecteur | Oui | Oui, sur le mécanisme | Oui | Oui | Oui | Sans objet | Non |
| 5 | Lectures en échec pendant un déploiement | Coupure | Oui | Oui | Atténué | Oui | Oui | Non éprouvé | Non |
| 6 | Ma reprise sur 503 retardait le bandeau visio | **Ma PR #56** | Oui | Oui | PR #57 | Oui | Oui | Après #57 | Non |

## Prouvés sans défaut, en local

Résultat d'examen transféré deux fois (bouton absent sans produit « note », transfert unique couvert par les tests), réponses après coupure, notes partielles.

## Incohérences de données en production

Relevées en lecture seule par `detect_incoherences_parent_eleve`. **Non modifiées.**

| Cas | Risque |
|---|---|
| Compte 191, superadmin avec profil parent (élèves 99, 100) | Rôles mélangés |
| Élève 109, compte 208 de rôle parent | L'élève n'a pas les droits ni les écrans prévus |

## Non vérifiés

Changement d'année scolaire en conditions réelles, opérations concurrentes en dehors des tests existants, gros volumes, exactitude pédagogique des liens parent-élève, arrondis comparés à un calcul indépendant.

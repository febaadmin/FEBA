# Audit global FEBA : état au 02/11/2026

**La mission n'est pas terminée.** Ce document donne l'état réel de chaque critère d'acceptation. Commit en production au moment de la rédaction : `f25868c`.

## Critères d'acceptation

| Critère | État | Preuve ou manque |
|---|---|---|
| Fonctionnalités préservées | Oui, selon les tests | CI verte, parcours rejoués en local. Pas de recette en production |
| Anomalies identifiées corrigées | Partiel | `INVENTAIRE_BUGS_ET_CORRECTIONS.md`. Audit non exhaustif |
| Nouveaux modules sur parcours complets | Local seulement | Parcours en 15 étapes, types, coupure, objectifs, plans, compétences |
| Cinq profils testés | Local seulement | Pages ouvertes pour les 5. Actions complètes surtout admin, enseignant, élève |
| Permissions et cloisonnement | Partiel | Tests verts, mais **un échec isolé inexpliqué de la campagne d'isolation** |
| Données réelles préservées | Oui, contrôle partiel | 935 notes, 233 paiements inchangés. Aucune écriture de ma part |
| Incidents suivis | Partiel | 4 résolus, 4 corrigés à valider par les enseignants |
| Identité graphique cohérente | Partiel | Couche commune appliquée partout. Toutes les pages ne sont pas retravaillées une à une |
| Branding respecté | Oui | Logo et nom inchangés, palette conservée |
| Aucun flash | Oui en local dans Chrome | Mesures image par image. **À confirmer à l'œil en production, votre vidéo étant la référence** |
| CI verte | Oui sur les PR fusionnées | 10 contrôles sur #52 et #53 |
| Absence de nouvelles erreurs 500 | Oui sur 20 min | 0 traceback. 4 réponses 502 au redémarrage |
| Migrations | Oui | 0 en attente |
| Responsive | Partiel | 0 débordement à 390 px. Pas de téléphone réel ni de tablette mesurée |
| Performances contrôlées | Partiel | Poids du code mesuré. Pas de mesure mobile réelle ni de re-rendus |
| Sécurité préservée | Partiel | Voir `RAPPORT_SECURITE.md` |
| Archive vérifiée | Candidate seulement | Tant que les critères ci-dessus restent ouverts |

## Points ouverts

**Techniques**
1. Échec isolé de `test_isolation_2_7_19_academies` : voir l'inventaire, anomalie A1.
2. Coupure d'environ 5 secondes à chaque déploiement (réponses 502 au redémarrage du backend).
3. Revue page par page incomplète : Admissions, Fichiers, Transactions, tableaux larges.
4. Audit action par action non fait : documents officiels, gabarits, emploi du temps, site public, relances.
5. Pages publiques : seul le remplacement de l'attente clignotante les a touchées.
6. Textes et tirets : pas de nouveau passage complet dans le cadre de cette mission.

**Actions humaines**
- Créer des comptes de test en production et faire la recette des 5 profils.
- Scénarios des 4 incidents à valider (voir `RAPPORT_TESTS_PRODUCTION.md`).
- Dix suppressions de notes, en priorité 931 et 741.
- Confirmer les 147 affectations d'enseignants.
- Accord pour étendre le contrôle par affectation aux devoirs et présences.
- Test de restauration en root : `bash scripts/test_restauration_isolee.sh`.
- Décision sur les PDF déjà stockés qui contiennent des tirets longs (226 reçus, 77 bulletins, 4 rapports).
- Accès des familles de l'académie 2.

## Limites de méthode

- Presque toutes les preuves navigateur viennent d'une pile locale sous SQLite, avec des données de démonstration.
- Le balayage prouve qu'une page s'ouvre, pas que ses actions fonctionnent.
- Les planches de photos sont réduites : elles repèrent les défauts grossiers, pas les détails.

# Audit intégral FEBA : état au 02/11/2026

**La mission n'est pas terminée.** Le socle est livré et testé. Les critères de fin ne sont pas tous atteints : voir le tableau ci-dessous.

## Critères de fin

| Critère | État | Preuve ou manque |
|---|---|---|
| Pages inventoriées et examinées | Partiel | Toutes ouvertes en local aux 2 largeurs (`INVENTAIRE_PAGES.md`). Toutes les actions de chaque page n'ont pas été exercées |
| Anomalies corrigées ou documentées | Partiel | `REGISTRE_BUGS_ET_CORRECTIONS.md`. L'audit n'est pas exhaustif |
| Parcours critiques | Partiel | Parcours d'examen en 15 étapes, objectifs, classe, paiement, devoir vérifiés en local. Peu de recette en production |
| 5 profils testés | Local seulement | Balayage local. Pas de compte de test en production : action humaine |
| Suivi et examens validés | Local seulement | Tests automatiques et navigateur. Recette réelle à faire par l'établissement |
| Anciennes fonctions conservées | Oui, selon les tests | Suite backend et frontend vertes en CI. Aucun test désactivé |
| Refonte harmonisée | Partiel | Couche commune appliquée à toutes les pages. Plusieurs pages restent peu retravaillées, voir ci-dessous |
| Animations cohérentes | Partiel | Composants communs. Pas sur toutes les listes et tous les onglets |
| Responsive validé | Partiel | 0 débordement mesuré à 390 px. Pas d'essai sur téléphone réel |
| CI verte, déploiement vérifié | Oui, pour les PR fusionnées | `RAPPORT_DEPLOIEMENT.md` |
| Incidents classés | Partiel | 4 résolus, 4 corrigés à valider par les enseignants concernés |
| Sauvegardes et retour arrière | Partiel | Instantané avant déploiement. **Test de restauration jamais exécuté** : il exige root |

## Ce qui reste à faire

**Par moi, si la mission continue**
- Revue page par page : Admissions, Fichiers, Transactions (grandes zones vides), tableaux larges qui défilent horizontalement sur ordinateur (Élèves, Paiements, Utilisateurs), barre d'outils de la Banque, couleurs des graphiques.
- Audit fonctionnel des modules non parcourus action par action : documents officiels, gabarits, emploi du temps, site public, relances.
- Mesures de performance sur téléphone réel.

**Décisions et actions humaines**
- Comptes de test en production et recette des 5 profils.
- Scénarios des 4 incidents à valider.
- Dix suppressions de notes (notes 931 et 741 en priorité).
- Confirmation des 147 affectations enseignants.
- Accord pour étendre le contrôle croisé aux devoirs et aux présences.
- Test de restauration : `bash scripts/test_restauration_isolee.sh` en root.
- Décision sur les PDF déjà stockés qui contiennent des tirets longs (226 reçus, 77 bulletins, 4 rapports mensuels).
- Accès des familles de l'académie 2, avant l'arrivée de vraies familles.

## Limites de méthode

- L'essentiel des preuves navigateur vient d'une pile locale, avec SQLite et des données de démonstration. Ce n'est pas une preuve de fonctionnement en production.
- Mon automate de remplissage générique n'a pas su choisir les listes à recherche : il ne prouve donc que l'ouverture des formulaires et le refus d'un envoi vide, et certains n'ont été parcourus à la main que pour classe, paiement et devoir.
- Le balayage ne repère pas les erreurs de logique métier.

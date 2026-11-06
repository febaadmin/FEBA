# Point de reprise final

## État réel

| Élément | Corrigé localement | Testé localement | Fusionné dans main | Déployé | Vérifié en production |
|---|---|---|---|---|---|
| Panneau des notifications (fermeture) | oui | oui (unitaires et E2E bureau et mobile) | oui (#108) | oui | bundle déployé ; à confirmer à l'usage avec un compte réel |
| Remises et exonérations (règles, cumul, conditions, justification, annulation) | oui | oui | oui | oui | routes et permissions (200 / 403) ; aucune règle créée |
| Échéanciers personnalisés | oui | oui | oui | oui | routes ; aucun échéancier créé |
| Journal financier (y compris les dispositions) | oui | oui | oui | oui | route ; vide |
| Situation financière (KPI, 3 vues, filtres, graphiques, fiche, export) | oui | oui (navigateur, 4 tailles) | oui | oui | API : non calculable, encaissements réels cohérents avec le tableau de bord |
| Barème officiel : aperçu et import | oui | oui | oui | oui | aperçu vérifié ; **non importé** |
| Correction du réenregistrement des échéances | oui | oui | oui | oui | non exercée (aucun tarif) |
| Classe de l'année dans le tableau de bord | oui | oui | oui | oui | non exercée (aucun tarif) |
| CI : étape LibreOffice robuste | oui | CI verte | oui | sans objet | sans objet |

## Actions humaines nécessaires

1. **Tarifs** : dans « Tarifs et échéances », ouvrir le barème 2026-2027 et vérifier les trois points signalés :
   - jour exact des tranches ;
   - date des frais d'inscription ;
   - mois de garderie.
   
   Ensuite, cocher la vérification et importer. Tant que ce n'est pas fait, la situation financière reste « non calculable » (les encaissements réels restent affichés).
2. **Niveau « MARTERNELLE 2 »** : corriger l'orthographe en « MATERNELLE 2 » (page Niveaux) avant l'import, sinon la scolarité de ce niveau ne sera pas rattachée.
3. **Incidents « corrigés »** (ERR-310AC0, ERR-A036A8, ERR-5D12BE, ERR-FC6DC7, ERR-4744E2) : les valider dans « Incidents techniques ». Les causes sont corrigées et la surveillance est propre.
4. **Valider avec des comptes réels** (cinq profils) : ouvrir et fermer la cloche ; consulter la situation financière ; un parent consulte la fiche de son enfant.
5. **Optionnel** : rejouer une restauration de sauvegarde sur un serveur de test.

## Bloquants

Aucun bloquant technique. Les points ci-dessus sont des décisions ou des validations de l'établissement.

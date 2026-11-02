# Recette des examens en ligne

Parcours exercé en navigateur local, avec données de démonstration et un compte élève de test.

| Vérification | Auto | Navigateur local | Production |
|---|---|---|---|
| 10 types créés, enregistrés, listés | Oui | Oui | Non |
| Modification d'une question, version figée | Oui | Oui | Non |
| Épreuve composée des 10 types, publiée | Oui | Oui | Non |
| Consignes avant le chronomètre | Non | Oui | Non |
| Double clic sur Commencer : une tentative | Oui | Oui | Non |
| Sauvegarde, rechargement, reprise | Oui | Oui | Non |
| Coupure réseau puis retour | Non | Oui | Non |
| Fin du temps : remise automatique | Oui | Oui | Non |
| Double remise | Oui | Oui | Non |
| Tentative supplémentaire refusée | Oui | Non | Non |
| Corrigé jamais envoyé à l'élève | Oui | Oui | Non |
| Points : QCM partiel, trous, associations, numérique | Oui | Oui | Non |
| Correction manuelle, validation | Oui | Oui | Non |
| Transfert unique, répété | Oui | Oui | Non |
| Transfert simultané réel sur PostgreSQL | Non : verrou et contrainte en place, pas de test de charge | Non | Non |
| Expiration de session pendant l'épreuve | Non | Non | Non |
| Média audio ou vidéo | Non | Non | Non |
| Statistiques | Oui | Oui | Non |

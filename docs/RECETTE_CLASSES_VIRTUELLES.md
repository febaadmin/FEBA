# Recette réelle des classes virtuelles FEBA × plugNmeet

À faire avec de **vrais comptes**, sur `https://globalfeba.com`, depuis de vrais appareils. Les tests automatiques utilisent des participants simulés : ils ne remplacent pas cette recette.

**Durée :** 30 minutes. **Personnes :** 1 administrateur, 1 enseignant de la classe, 2 élèves de cette classe, 1 élève d'une autre classe. Si possible : un téléphone, et un élève sur un autre réseau (4G).

Notez pour chaque étape : OK ou KO, l'heure, et une capture en cas de KO. N'utilisez aucune note ni donnée réelle d'élève pour les essais destructifs.

## A. Préparation (administrateur)
| # | Action | Résultat attendu |
|---|---|---|
| A1 | Créer une salle pour la classe, programmée dans 30 minutes, durée 30 min | La salle apparaît dans la liste |
| A2 | Noter le nom de la salle et l'heure | |

## B. Horaires et droits
| # | Qui | Action | Résultat attendu |
|---|---|---|---|
| B1 | Élève 1 | Cliquer « Rejoindre » plus de 15 min avant l'heure | Refus clair, avec l'heure d'ouverture |
| B2 | Enseignant | Cliquer « Rejoindre » à ce moment | Entrée autorisée |
| B3 | Élève d'une autre classe | Chercher la salle | Salle absente de sa liste |
| B4 | Admin d'une autre académie, si disponible | Chercher la salle | Salle absente |

## C. Entrée
| # | Qui | Action | Résultat attendu |
|---|---|---|---|
| C1 | Élèves 1 et 2 | Rejoindre dans les 15 min avant l'heure | Entrée, nom correct, logo FEBA |
| C2 | Tous | Autoriser micro et caméra | Pas d'écran d'erreur |
| C3 | Enseignant | Vérifier la liste des participants | 3 personnes |

## D. Audio et vidéo (à l'oreille et à l'œil)
| # | Action | Résultat attendu |
|---|---|---|
| D1 | L'enseignant parle, les élèves confirment | Son clair, sans écho |
| D2 | Élève 1 parle | Entendu de l'enseignant et de l'élève 2 |
| D3 | Chacun active sa caméra | Tous se voient |
| D4 | Élève 2 refuse le micro dans le navigateur | Message compréhensible, la salle reste utilisable |
| D5 | L'enseignant coupe tous les micros | Micros des élèves coupés |

## E. Partage et tableau blanc
| # | Action | Résultat attendu |
|---|---|---|
| E1 | L'enseignant partage son écran | Visible des deux élèves |
| E2 | Un élève cherche le partage d'écran | Verrouillé |
| E3 | L'enseignant ouvre le tableau blanc et dessine | Visible des élèves |
| E4 | Il charge `French_Greetings_for_Kids.pptx` | Toutes les pages arrivent, l'élève les voit |
| E5 | Il charge `French_Politeness_and_Classroom_Instructions_for_Kids (1).pptx` | Idem ; noter le nombre de pages |

## F. Fonctions pédagogiques
| # | Action | Résultat attendu |
|---|---|---|
| F1 | Chat dans les deux sens | Messages reçus |
| F2 | Élève 1 lève la main | Signalée à l'enseignant |
| F3 | L'enseignant crée un sondage Oui/Non, les élèves votent | Résultat juste |
| F4 | L'enseignant lance une salle de sous-groupe ; les élèves y entrent puis reviennent | Entrée et retour réussis |
| F5 | L'enseignant retire puis laisse revenir un élève | Comportement conforme à ce qu'il attend |

## G. Interruption
| # | Action | Résultat attendu |
|---|---|---|
| G1 | Élève 2 coupe le Wi-Fi 15 s puis le rétablit | Retour automatique, son et image reviennent |
| G2 | Élève 1 recharge la page | Retour possible par « Rejoindre » |
| G3 | Un élève sur téléphone rejoint la salle | Entrée, son et image corrects |

## H. Fin
| # | Action | Résultat attendu |
|---|---|---|
| H1 | L'enseignant termine la réunion | Tous sortent et reviennent vers FEBA |
| H2 | Élève 1 tente de revenir après la fenêtre (15 min après la fin) | Refus clair |
| H3 | L'administrateur consulte les présences de la salle | 3 participants, durées plausibles |

## Après la recette
Dites-moi « recette faite », avec le nom de la salle et l'heure, et transmettez la liste des KO. Je comparerai vos résultats aux journaux. Seules les étapes passées avec de vrais comptes seront déclarées validées.

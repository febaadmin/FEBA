# Matrice de tests par rôle

Niveaux : **A** test automatique, **N** navigateur local avec données de démonstration, **P** production. Rien n'a encore été exercé avec un compte réel enseignant, élève ou parent dans ces modules.

| Parcours | Superadmin | Admin | Enseignant | Élève | Parent |
|---|---|---|---|---|---|
| Ouverture de toutes les pages, bureau et mobile | N | N | N | N | N |
| Activer un module | A N, P par vous | Refusé A | Refusé A | Refusé A | Refusé A |
| Référentiels et compétences | A | A N | A | Lecture A | Lecture A |
| Évaluer, observer, objectif, plan | A | A N | A N | Refusé A | Refusé A |
| Fiche de suivi | P par vous (lecture) | A N | A N | A N | A N |
| Banque, 10 types | A | A | A N | Refusé A | Refusé A |
| Créer et publier une épreuve | A | A | A N | Refusé A | Refusé A |
| Passer une épreuve, reprise, coupure, fin du temps | - | - | - | A N | - |
| Corriger, valider, transférer | A | A | A N | Refusé A | Refusé A |
| Résultats publiés | - | - | - | A N | A |
| Rapports, PDF, publication | A | A N | A | Publié seulement A | Publié seulement A |
| Alertes | A | A N | A | Refusé A | Refusé A |
| Autre académie, autre élève | Refusé A | Refusé A | Refusé A | Refusé A | Refusé A |
| Messagerie, envoi et réception | - | - | N (API) | - | N (API) |
| Lecture API en production, 147 routes | P serveur | P serveur | P serveur | P serveur | P serveur |

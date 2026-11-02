# Tests par rôle

| Parcours | Superadmin | Admin | Enseignant | Élève | Parent | Niveau |
|---|---|---|---|---|---|---|
| Toutes les pages, 2 largeurs | Oui | Oui | Oui | Oui | Oui | Navigateur local |
| Sélecteur d'académie | Oui | Absent, conforme | - | - | - | Navigateur local |
| Formulaires à vide | Oui | Oui | Oui | - | - | Navigateur local, avant #52 |
| Classe, paiement, reçu | - | Oui | - | - | - | Navigateur local |
| Devoir, visible par la classe | - | - | Oui | Oui | - | Navigateur local |
| Examen de bout en bout | - | - | Oui | Oui | Oui | Navigateur local |
| Objectifs, plans | - | - | Oui | - | - | Navigateur local |
| Élévation, comptes, IDOR | - | Oui | Oui | Oui | Oui | Tests PostgreSQL |
| **Tout parcours connecté en production** | **Non** | **Non** | **Non** | **Non** | **Non** | Comptes de test absents |

**Les cinq profils ne sont pas validés de bout en bout.** Non parcourus action par action : documents officiels, gabarits, emploi du temps, messages, rapports mensuels, admissions.

# Inventaire des modules

Mesuré dans le code au 03/11/2026 : 28 applications Django, 148 déclarations de routes API, 176 routes React, 122 pages sondées par profil (superadmin 38, admin 39, enseignant 15, parent 16, élève 14).

| Module | Consultation | Écriture exercée | Niveau |
|---|---|---|---|
| Authentification | Oui | Connexion, déconnexion, session expirée, compte désactivé | Local |
| Utilisateurs | Oui | Création, désactivation | Local, API |
| Élèves | Oui | Recherche, tri, pagination | Local |
| Classes, niveaux | Oui | Création | Local |
| Notes | Oui | Création, modification, droits, suppression justifiée | Local, API |
| Bulletins | Oui | Génération, PDF, sans doublon | Local, API |
| Paiements, reçus | Oui | Création, reçu, droits, suppression | Local, API |
| Suivi, objectifs, plans | Oui | Création, modification, archivage | Local |
| Compétences | Oui | Évaluation d'une classe | Local |
| Examens | Oui | 15 étapes, 10 types, coupure | Local |
| Devoirs, absences, emploi du temps | Oui | Création | Local |
| Messages, annonces | Oui | Aller-retour, diffusion | Local |
| Fichiers | Oui | Dépôt, téléchargement, droits, refus HTML | Local, API |
| Admissions, documents, gabarits, relances, transactions, rapports mensuels | Oui | **Non exercée** | Ouverture seule |
| Site public | Pages principales | **Formulaires non exercés** | Ouverture seule |
| Salles virtuelles | Liste | **Non testé** | Pas de serveur local |

Modifications croisées (changer la classe d'un élève ou le rôle d'un compte et en suivre les effets) : **non testées de bout en bout**.

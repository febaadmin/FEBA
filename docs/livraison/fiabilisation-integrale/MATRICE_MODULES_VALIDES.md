# Modules validés

Niveaux : **CI** (E2E à chaque PR), **local** (navigateur sur pile isolée), **PostgreSQL** (tests automatiques), **lecture seule** (production).

| Module | Écritures exercées | Niveau |
|---|---|---|
| Connexion, sessions | Oui | CI |
| Comptes, rôles | Création, rôle, désactivation | CI |
| Élèves | Recherche, tri, pagination | CI |
| Classes, annonces, paiements | Création, double envoi | CI |
| Notes | Création, modification, suppression justifiée, droits | CI |
| Bulletins | Génération, PDF, sans doublon, auteur | CI, PostgreSQL |
| Paiements, reçus | Création, reçu, suppression, droits | CI |
| Fichiers, avatars | Dépôt, téléchargement, refus HTML et SVG | CI |
| Messagerie | Aller-retour | CI |
| Suivi, compétences, objectifs, plans | Complet | CI |
| Examens | Complet | CI |
| Site public, préinscription | Pages, envoi, export | CI |
| Relances | Lecture et droits | CI. **Envoi réel non testé** |
| Transactions par carte | Lecture et droits | CI. Paiement par carte désactivé |
| Rapports mensuels | Liste et droits | CI. **Production d'un lot et envoi non testés** |
| Admissions FHA | Liste | CI. **Dépôt complet non testé** |
| Documents officiels | Production, numérotation, PDF, anti-IDOR | Local, scénario existant : tout réussi |
| Gabarits | PDF refusé ou accepté, éditeur | Local, partiel : Word sans LibreOffice local |
| Emploi du temps | Création d'un créneau | Local |
| Absences | Création | Local |
| Classes virtuelles | **Non testé** | Voir `RAPPORT_PLUGNMEET_CSP.md` |

**Modifications croisées :**
- Testé : un rôle changé est appliqué sans reconnexion (CI).
- **Non testé** : une classe modifiée dans l'emploi du temps et les espaces élèves, une affectation dans les accès pédagogiques.

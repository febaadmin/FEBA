# Limitations connues — V4 multi-entités

Ce document est délibérément explicite. Le cahier des charges interdit de
déclarer « 100 % fonctionnel » lorsqu'une limitation subsiste. En voici la
liste exhaustive.

---

## 1. Périmètre non livré dans cette itération

Le cahier des charges couvrait 21 priorités. Les priorités **1 à 10** sont
implémentées et testées. Les suivantes le sont **partiellement ou pas du
tout**. Ce qui suit n'existe pas dans le code livré :

| Priorité | État | Détail |
|---|---|---|
| **P11 — Zoom** | **Non implémenté** | Voir §2. |
| **P12 — Espace parent FHA** | Non implémenté | Les espaces parent existants restent ceux de FEBA. Aucun tableau de bord spécifique FHA (prochain cours, échéance, sélecteur d'enfant multi-enfants). |
| **P13 — Espace élève FHA** | Non implémenté | Pas de « My FEBA Passport », badges, bibliothèque, ni adaptation par groupe d'âge. |
| **P14 — Espace enseignant FHA** | Non implémenté | Pas de suivi des dix compétences FHA ni de logique de progression distincte des moyennes FEBA. |
| **P15 — Administration FHA** | **Partiel** | Les dossiers d'inscription, leurs douze états et l'historique sont livrés. Les rôles internes (admissions / finance / support / direction) ne le sont pas : les rôles restent `admin`, `teacher`, `parent`, `student`, `superadmin`. |
| **P16 — Messagerie FHA** | Non implémenté | La messagerie existante n'a pas reçu de séparation par entité ni les garde-fous de protection des mineurs (interdiction des échanges privés adulte-mineur, modération, signalement). |
| **P17 — Fuseaux horaires** | **Partiel** | Les disponibilités familiales sont stockées normalisées avec leur fuseau IANA, et le fuseau est détecté côté navigateur. La conversion d'affichage des emplois du temps et les tests de changement d'heure saisonnier ne sont pas faits. |
| **P18 — Paiements et documents FHA** | **Partiel** | Devise, fuseau et langue sont séparés par entité. Les échéanciers FHA, réductions Early Bird / fratrie, et les modèles de documents FHA (contrat annuel, autorisations, certificats) ne sont pas implémentés. |
| **P19 — Notifications** | **Partiel** | Deux notifications réelles et testées (fiche soumise, changement d'état), bilingues et rattachées à l'entité. Les rappels de cours 24 h / 1 h, échéances de paiement, devoirs et bulletins ne sont pas implémentés. |
| **P20 — Audit de sécurité** | **Partiel** | L'isolation inter-entités, l'anti-IDOR et les téléversements sont audités et testés. Aucun audit n'a été mené sur CORS, cookies, dépendances, ni de test de charge ou de brute force. |
| **P21 — Bilinguisme** | **Partiel** | Le site public FHA, ses deux formulaires et les notifications FHA sont bilingues. L'ERP privé conserve le mécanisme i18n existant, non étendu au contenu FHA. |

### Tests non réalisés

- **Tests end-to-end (Playwright/Cypress)** : aucun. Les vérifications
  navigateur ont été faites par appels HTTP réels sur serveur lancé (voir
  `TEST_REPORT_V4.md` §5), ce qui n'est pas équivalent.
- **Tests visuels multi-résolutions** (320 → 1920 px) : **non réalisés**. Les
  composants sont écrits en mobile-first Tailwind avec grilles responsives,
  mais aucune capture ni vérification de débordement n'a été effectuée.
- **Captures d'écran desktop / tablette / mobile** : **non fournies**.

---

## 2. Visioconférence — Zoom n'est pas intégré

C'est la limitation la plus importante, et elle mérite d'être dite sans détour.

### Ce qui existe

Le projet possède déjà une intégration **Jitsi Meet auto-hébergée**,
fonctionnelle et antérieure à ces travaux : `apps/virtualclass`, avec des
jetons JWT signés côté serveur (`build_jitsi_jwt`), un enregistrement des
présences, et une configuration documentée (`.env.jitsi.example`,
`docker-compose.jitsi.yml`).

En V4, cette intégration a été **conditionnée par entité** : elle est
désormais réservée aux entités de type `online` (FEBA FHA) et refusée à FEBA.

### Ce qui n'existe pas

Les documents de cadrage désignent **Zoom** comme plateforme. **Aucune
intégration Zoom n'a été écrite** : ni OAuth Server-to-Server, ni création de
réunions récurrentes par groupe, ni salle d'attente, ni mot de passe, ni
import des rapports de participation, ni rappels 24 h / 1 h.

**Je n'ai testé aucun identifiant Zoom réel.** Aucune affirmation de
fonctionnement en production ne peut être faite à ce sujet.

### Conséquence pratique

Si FEBA souhaite Zoom plutôt que Jitsi, cela reste **entièrement à
développer**. La matrice de fonctionnalités et le cloisonnement par entité
sont en place pour l'accueillir, mais le connecteur lui-même n'existe pas.

---

## 3. Limitations techniques

### SQLite

`settings/test_sqlite.py` ne fonctionne pas : cinq migrations multi-tenant
antérieures (V29) utilisent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
syntaxe propre à PostgreSQL.

**Ce défaut est antérieur à cette livraison** — vérifié sur le commit de
référence, où la suite SQLite produisait déjà 378 erreurs. Il n'a pas été
corrigé, car réécrire ces migrations historiques présentait un risque de
régression supérieur au bénéfice. PostgreSQL est la cible de test du projet.

### Vue consolidée du superadmin

`StudentViewSet` (et quelques vues antérieures) autorisent un superadmin sans
entité active à voir **toutes** les entités. C'est un comportement préexistant
du rôle plateforme, assumé et couvert par un test explicite plutôt que modifié
— le changer aurait touché des vues hors du périmètre demandé.

Il ne concerne **aucun autre rôle** : un compte non-superadmin sans entité
n'obtient même pas de jeton d'authentification.

### Suppression de l'ancienne page

`OnlinePage.jsx` a été supprimée et remplacée par `FhaPage.jsx`. La route
`/feba-online` redirige de façon permanente vers `/feba-fha` — aucun lien
existant n'est cassé, mais l'ancienne page n'est plus consultable.

---

## 4. Données non validées par la direction

Conformément à l'interdiction d'inventer des données, les informations
suivantes sont **volontairement absentes** et stockées à `null` dans
`School.settings["pending_direction_validation"]` :

- tarif annuel et nombre de versements autorisés ;
- date officielle de rentrée ;
- horaires définitifs des trois groupes ;
- réductions fratrie et Early Bird ;
- politique de remboursement ;
- noms des enseignants ;
- prestataire de paiement retenu ;
- politique d'enregistrement des cours.

Le site affiche à leur place un encart « à confirmer par la direction ». Elles
sont administrables sans modification de code.

Les seules données FHA écrites en base sont celles **confirmées par les deux
documents** : nom, slogan, WhatsApp `+1 (215) 715-5406`, pays cibles, fuseau,
devise et langue par défaut.

---

## 5. Ce qui est réellement vérifié

Pour éviter toute ambiguïté, voici ce qui a été **exécuté**, et non supposé :

- suite backend complète sur PostgreSQL : **481 passed**, 0 échec, 0 ignoré ;
- suite frontend : **75 passed** ; ESLint : **0 erreur** ; build production : **OK** ;
- migration d'une base V3 peuplée vers la V4 : **aucune perte**, comptages
  avant/après identiques ;
- rejeu des migrations de données : **idempotent** ;
- migration sur base vierge : **OK** ;
- serveur Django lancé, endpoints appelés en HTTP réel : soumission de fiche,
  refus de doublon, isolation admin FEBA / admin FHA, refus 403 des salles
  virtuelles, bascule du superadmin et journal d'audit.

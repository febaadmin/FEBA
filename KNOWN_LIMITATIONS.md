# KNOWN_LIMITATIONS — ce qui n'a pas été vérifié

Ce document est délibérément explicite. Un rapport qui tait ses angles morts
est plus dangereux qu'un rapport incomplet.

## 1. Portée réelle de cet audit

La mission demandait dix priorités. Voici ce qui a réellement été fait.

| Priorité | Statut | Preuve |
|---|---|---|
| P1 — dashboard à zéro | **Corrigé** | 10 tests, échec prouvé contre le code d'origine |
| P2 — commande de nettoyage | **Livré** | 26 tests |
| P3 — titres des étapes | **Corrigé** | build + couverture i18n |
| P4 — formules et flyer | **Livré** | migration + empreinte SHA-256 vérifiée |
| P5 — total multidevise | **Déjà implémenté** | 35 tests existants exécutés |
| P6 — parité emploi du temps | **Déjà implémenté** | 32 tests existants exécutés |
| P7 — téléchargement FHA | **Déjà implémenté** | 4 tests existants exécutés |
| P8 — rapport mensuel | **Déjà implémenté** | 65 tests existants exécutés |
| P9 — bouton EN/FR mobile | **Corrigé** | 6 tests, échec prouvé contre le code d'origine |
| P10 — audit global | **Partiel** | voir ci-dessous |

### Sur P5 à P8

Les symptômes décrits ne se reproduisent pas sur l'archive source : les
fonctionnalités y sont implémentées et couvertes par des tests qui passent.
Deux lectures possibles, et il faut le dire franchement :

- soit ces défauts ont été corrigés lors d'un cycle antérieur et la demande
  s'appuyait sur une version plus ancienne de l'application ;
- soit ils persistent en conditions réelles selon un mécanisme que les tests
  automatisés ne capturent pas (cache navigateur, proxy, données de
  production particulières).

Aucune modification n'a été apportée à ce périmètre : réécrire du code dont
les tests passent introduirait un risque sans bénéfice démontrable. Si les
symptômes persistent après déploiement, ils devront être rouverts avec une
observation navigateur, et ce rapport en sera le point de départ.

### Sur P10 — audit global

L'audit exhaustif des 32 domaines listés (authentification, JWT, permissions
objet, élèves, parents, enseignants, admissions, notes, bulletins, absences,
devoirs, messagerie, notifications, documents, rapports, site public,
responsive, Celery, Jitsi, Mailpit, Docker, performances…) **n'a pas été mené
domaine par domaine**. Ce qui a été fait à ce titre :

- l'intégralité des suites de tests a été exécutée (1 112 backend,
  179 frontend), ce qui couvre transversalement une large part de ces
  domaines ;
- `manage.py check` ne signale aucun problème ;
- `makemigrations --check` confirme l'absence de migration manquante ;
- le lint frontend ne remonte aucune erreur ;
- aucun secret ni fichier `.env` réel n'est présent dans l'archive livrée.

En revanche, la recherche systématique de boutons morts, de CRUD incomplets,
de props DOM invalides, de code mort, de dépendances inutilisées et d'URL
codées en dur **n'a pas été conduite**. Les 82 avertissements de lint
préexistants n'ont pas été traités.

## 2. Validations Docker restant à faire

Aucun démon Docker n'était disponible. Non exécutés :

```
docker compose down -v --remove-orphans
make install / seed / seed-check / documents-ready
make branding-check / jitsi-health / celery-health / install-check
```

Les 13 fichiers de tests e2e n'ont pas été exécutés non plus : ils exigent un
navigateur et la pile complète.

### Conséquences par priorité

- **P1** : le scénario `Cmd+R` n'a pas été rejoué dans un navigateur réel. La
  correction est prouvée au niveau composant, avec reproduction du bug
  d'origine. Les statuts Nginx `499` devraient disparaître puisque les
  requêtes annulées au démarrage ne sont plus émises — à confirmer par
  observation.
- **P3** : navigation précédent/suivant, reprise du brouillon, validation
  clavier et rendu mobile/tablette/desktop non observés en navigateur.
- **P4** : téléchargement effectif du flyer (en-têtes HTTP, type MIME servi
  par Nginx) et affichage de la formule dans FHA Admissions non observés.
- **P9** : les largeurs 320 / 375 / 390 / 430 / 768 / 1024 px n'ont pas été
  observées en navigateur. jsdom n'applique pas les media queries Tailwind :
  les tests vérifient la présence dans le DOM et l'absence de classes
  desktop-only, pas le rendu pixel.

## 3. Limites de la commande de nettoyage

- **Jamais exécutée en mode réel sur des données de production.** Uniquement
  sur des bases SQLite de test éphémères.
- `messaging.Conversation` n'a aucun rattachement d'académie : en mode
  `--academy` elle est ignorée, et l'omission est consignée dans les
  anomalies du rapport plutôt que devinée. Elle est nettoyée en mode global.
- La suppression des médias n'a pas été testée sur un volume réel de
  fichiers.
- Le verrou anti-concurrence repose sur `fcntl.flock`, donc sur un système de
  fichiers POSIX local. Il ne protège pas contre deux exécutions depuis deux
  conteneurs distincts sans volume partagé.

## 4. Environnement de test

Les tests backend tournent sous `settings.test_sqlite` (SQLite en mémoire).
Certains comportements — contraintes de concurrence, verrous, types
spécifiques à PostgreSQL — ne s'y observent pas. Un test de concurrence
multi-threads est explicitement ignoré pour cette raison. La validation finale
doit se faire sur PostgreSQL via `settings.test_postgres`.

## 5. Nommage de l'archive

L'archive source s'appelle `…v9…` alors que la mission parle de « V6 ». Le
nom du dossier source a été conservé sans modification. Le dépôt contient des
rapports `KNOWN_LIMITATIONS_V4` à `V9` : le versionnage interne du projet a
dépassé V6. Signalé pour éviter toute ambiguïté sur ce qui a été livré.

# Vérification V7 — sorties brutes

Toutes les commandes ci-dessous ont été exécutées sur le commit livré.
Aucune sortie n'est reconstituée : ce sont les journaux réels.

## 1. Suite backend — PostgreSQL (moteur de production)

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres pytest -q
562 passed, 392 warnings, 60 subtests passed in 36.11s
```

## 2. Suite backend — SQLite (développement local sans PostgreSQL)

```
$ DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite pytest -q
SKIPPED [1] tests/test_parent_student.py:325: Test de concurrence multi-threads : SQLite en mémoire verrouille la table entière (« database table is locked ») — nécessite un vrai serveur de base de données. Exécuté sur PostgreSQL (settings.test_postgres / stack docker).
561 passed, 1 skipped, 391 warnings, 60 subtests passed in 21.62s
```

## 3. Frontend — tests, lint, build

```
$ npx vitest run
 Test Files  13 passed (13)
      Tests  98 passed (98)

$ npx eslint src --ext .js,.jsx
✖ 82 problèmes (0 erreur, 82 avertissements — base historique)

$ npm run build
dist/assets/index-Dvcj-nYp.js                     392.35 kB │ gzip: 128.70 kB
✓ built in 7.72s
```

## 4. Parcours navigateur — académies (`node e2e/academies.mjs`)

```
═══ 1. BASCULE D'ACADÉMIE ═══
  Élèves servis : FEBA=30 → FHA=3 (321 ms) → TOUTES=33 (299 ms) → FEBA=30 (298 ms)
  Badges affichés : FEBA=[] · FHA=[] · TOUTES=["FEBA","FEBA FHA"]
  OK  les données changent réellement entre académies — 30 ≠ 3
  OK  total consolidé = somme des académies — 33 = 30 + 3
  OK  retour sur FEBA : même effectif qu'au départ — 30 = 30
  OK  les deux académies apparaissent en mode consolidé — ["FEBA","FEBA FHA"]
  OK  bascule sous 3 s sans rechargement — max 321 ms
  OK  aucun rechargement complet de page pendant les bascules
  OK  aucune réponse servie sous une portée périmée
  OK  dernières données élèves servies sous la bonne académie — portée=FEBA

═══ 2. MODE « TOUTES LES ACADÉMIES » — IDENTIFICATION ═══
  OK  colonne Académie sur « Élèves » — 15 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Utilisateurs » — 30 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Classes » — 15 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Enseignants » — 6 badge(s) / 6 ligne(s)
  OK  colonne Académie sur « Parents » — 10 badge(s) / 10 ligne(s)
  OK  colonne Académie sur « Niveaux » — 13 badge(s) / 13 ligne(s)
  OK  colonne Académie sur « Notes » — 20 badge(s) / 20 ligne(s)
  OK  colonne Académie sur « Paiements » — 15 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Présences » — 15 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Devoirs » — 10 badge(s) / 10 ligne(s)
  OK  colonne Académie sur « Bulletins » — 15 badge(s) / 15 ligne(s)
  OK  colonne Académie sur « Annonces » — 3 badge(s) / 3 ligne(s)
  OK  les deux académies sont visibles dans la même liste — ["FEBA","FEBA FHA"]

═══ 3. EMPLOIS DU TEMPS SÉPARÉS ═══
  OK  deux onglets nommés FEBA et FEBA FHA — ["FEBA — cours présentiels","FEBA FHA — séances en ligne"]
  OK  onglets nommés en toutes lettres (pas de simple couleur)
  OK  création de créneau proposée sur l'onglet FEBA
  OK  séances en ligne refusées pour une académie présentielle (403 serveur)
  OK  colonne heure UTC sur les séances FEBA FHA — ["GROUP","SUBJECT","DAY (UTC)","UTC TIME","LOCAL TIME","TEACHER","VIRTUAL ROOM","REMINDER",""]
  OK  colonne heure locale
  OK  colonne salle virtuelle
  OK  colonne rappel
  OK  séances en ligne listées — 3 séance(s)
  OK  formulaire d'édition FHA : heure UTC et fuseau
  OK  formulaire d'édition FHA : rappel aux familles
  OK  admin FEBA FHA : uniquement l'onglet des séances en ligne — ["FEBA FHA — online sessions"]

═══ 4. APPLICATION PRIVÉE EN ANGLAIS — TOUS LES PROFILS ═══
  OK  profil superadmin en anglais — 9 vues
  OK  profil admin en anglais — 6 vues
  OK  profil teacher en anglais — 3 vues
  OK  profil parent en anglais — 3 vues
  OK  profil student en anglais — 3 vues

═══ 5. JOURNAL ═══
  OK  aucune erreur console applicative
  489 réponses API observées · 377 portées annoncées

═══ RÉSULTAT : TOUS LES POINTS VÉRIFIÉS ═══
EXIT=0
```

## 5. Parcours navigateur — espaces en anglais (`node e2e/espaces-anglais.mjs`)

```
═══ APPLICATION PRIVÉE EN ANGLAIS ═══
  OK  profil teacher en anglais — 7 vues
  OK  profil parent en anglais — 7 vues
  OK  profil student en anglais — 6 vues
  OK  aucune erreur console applicative

═══ TOUS LES PROFILS VÉRIFIÉS ═══
EXIT=0
```

## 6. Parcours navigateur — site public en anglais (`node e2e/site-public-anglais.mjs`)

```
langue après clic EN : en
OK  Accueil            lang=en 
OK  À propos           lang=en 
OK  Académique         lang=en 
OK  Admissions         lang=en 
OK  Vie scolaire       lang=en 
OK  Campus             lang=en 
OK  Galerie            lang=en 
OK  Actualités         lang=en 
OK  Contact            lang=en 
OK  Mentions légales   lang=en 
OK  Confidentialité    lang=en 
OK  FEBA FHA           lang=en 
OK  404                lang=en 

Bascule EN → FR sans rechargement : "Welcome to FEBA" → "Bienvenue à FEBA" · CONTENU CHANGÉ

Pages avec du français résiduel : 0 / 13
EXIT=0
```

## 7. Jeu de démonstration sur une base neuve

```
$ manage.py migrate && manage.py seed_demo_data && manage.py seed_website
   prof@febafha.org    / Teacher@2024
   parent@febafha.org  / Parent@2024
   eleve1@febafha.org  / Student@2024

$ manage.py seed_check
  ✓ Aucun créneau FEBA reliant deux académies
  ✓ Aucune séance FEBA FHA reliant deux académies

Académies : FEBA=47 compte(s) · FEBA_FHA=6 compte(s)
Élèves    : FEBA=30 · FEBA_FHA=3
Fiches FHA : 1 · Tests : 1
Emplois du temps : FEBA=50 créneau(x) · FEBA_FHA=3 séance(s) en ligne

✓ 20 contrôles passés — isolation intacte.

$ manage.py seed_demo_data && manage.py seed_check   # rejeu : idempotence
Académies : FEBA=47 compte(s) · FEBA_FHA=6 compte(s)
Élèves    : FEBA=30 · FEBA_FHA=3
Fiches FHA : 1 · Tests : 1
Emplois du temps : FEBA=50 créneau(x) · FEBA_FHA=3 séance(s) en ligne

✓ 20 contrôles passés — isolation intacte.
```

## 8. Retest du ZIP livré, extrait dans un dossier neuf

L'archive a été dézippée dans un répertoire vide, hors du dépôt, puis
installée et testée de bout en bout. Aucun fichier du répertoire de
travail n'est intervenu.

```
$ unzip feba_multi_academies_v7.zip && cd feba_multi_academies_v7
$ find . -name node_modules -o -name venv -o -name '*.sqlite3' -o -name .env -o -name '*.pyc'
(aucun résultat — ni dépendances, ni base locale, ni secret, ni cache)
762 fichiers · 27 Mo · .env.example présent

$ python -m venv venv && pip install -r requirements/dev.txt
django (5, 0, 4, 'final', 0)

$ DJANGO_SETTINGS_MODULE=…test_sqlite pytest -q
561 passed, 1 skipped, 60 subtests passed

$ DJANGO_SETTINGS_MODULE=…test_postgres pytest -q
562 passed, 60 subtests passed

$ npm install && npx vitest run
 Test Files  13 passed (13)
      Tests  98 passed (98)

$ npx eslint src --ext .js,.jsx
✖ 82 problèmes (0 erreur, 82 avertissements — base historique)

$ npm run build
✓ built in 9.30s

$ manage.py migrate && manage.py seed_demo_data && manage.py seed_website
$ manage.py seed_check
Académies : FEBA=47 compte(s) · FEBA_FHA=6 compte(s)
Élèves    : FEBA=30 · FEBA_FHA=3
Emplois du temps : FEBA=50 créneau(x) · FEBA_FHA=3 séance(s) en ligne
✓ 20 contrôles passés — isolation intacte.
```

Les trois parcours navigateur ont ensuite été rejoués contre le projet
extrait (backend port 8011, frontend port 5201) :

```
$ node e2e/academies.mjs
═══ RÉSULTAT : TOUS LES POINTS VÉRIFIÉS ═══

$ node e2e/espaces-anglais.mjs
═══ TOUS LES PROFILS VÉRIFIÉS ═══

$ node e2e/site-public-anglais.mjs
Pages avec du français résiduel : 0 / 13

```

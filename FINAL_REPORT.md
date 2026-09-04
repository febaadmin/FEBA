# FEBA — Rapport final

Mission de correction profonde V2 : P0 logique des classes FEBA FHA,
audit de la classe virtuelle Jitsi, audit global.

---

## 1. Résumé

| | |
|---|---|
| Backend PostgreSQL | **1297 passés, 0 échec** |
| Backend SQLite | **1296 passés, 1 ignoré** (documenté) |
| Frontend | **246 passés, 25 fichiers** |
| Parcours navigateur | **11/11** (capture), **17/17** (rôles), **15/15** (non-régression) |
| ESLint | **0 erreur**, 81 avertissements (référence inchangée) |
| Build, migrations, `manage.py check` | **OK** |

**8 anomalies** corrigées et vérifiées. Détail au format §45 dans
`FEBA_FHA_CLASS_VALIDATION_REPORT.md`.

---

## 2. Le bug signalé, et ce qu'il révélait

Une classe francophone affichait « Configuration complète ✓ — 4 matière(s)
FR » puis refusait l'enregistrement : « Sélectionnez au moins une matière
anglaise. »

**Les deux phrases venaient du même composant.** Le bandeau lisait le
parcours de la classe ; la garde de soumission, vingt lignes plus haut,
appliquait encore la règle bilingue écrite en dur. Le lot précédent avait
corrigé l'affichage sans toucher à la garde : exactement la moitié du
travail.

### Ce que l'audit a trouvé en plus, et qui est plus grave

**Le backend ne validait rien.** Les deux chemins d'écriture faisaient
tous deux `Subject.objects.filter(id__in=subject_ids)` — sans règle
métier et sans restriction d'académie. N'importe quel identifiant posté
était accepté, y compris une matière appartenant à l'autre académie.

Autrement dit : le frontend sur-validait, le backend ne validait pas. Le
toast visible était le symptôme le moins dangereux des deux.

---

## 3. La source de vérité (§4)

`backend/apps/classes/subject_rules.py` décide. Les deux chemins
d'écriture y passent, le modèle y délègue, le frontend la reflète.

La décision tient compte de l'**académie** autant que du parcours : Faith
& Excellence Bilingual Academy est bilingue par construction, c'est son
identité. Le drapeau `monolingual_classes`, dans la matrice de
fonctionnalités déjà vérifiée côté serveur, porte cette distinction. Pour
une académie qui l'interdit, le parcours effectif est `BILINGUAL` quelle
que soit la valeur stockée — **la non-régression de FEBA devient
structurelle plutôt que promise.**

Détail complet : `CLASS_TYPE_BUSINESS_RULES_REPORT.md`.

---

## 4. Classe virtuelle et Jitsi

| Point | Statut |
|---|---|
| §12 cycle de vie React, `dispose()` **compté** | **PASS VÉRIFIÉ** — 7 tests tombent si on remet `onClose` en dépendance |
| §14 nouvel onglet, plein écran, aucun layout FEBA | **PASS VÉRIFIÉ** (navigateur) |
| §16 secret backend-only, JWT hors URL | **PASS VÉRIFIÉ** — 0 occurrence dans le bundle |
| §17 join/leave idempotents | **PASS VÉRIFIÉ** |
| §20 accès par classe, refus **expliqué** | **CORRIGÉ ET VÉRIFIÉ** |
| §21 modérateurs par rôle, escalade refusée | **PASS VÉRIFIÉ** |
| §22 émetteur, algorithme, durée, altération | **PASS VÉRIFIÉ** |
| §26 chemins sensibles, en-têtes | **PASS VÉRIFIÉ** (aucune fuite) ; `Referrer-Policy` et CSP → **EXTERNAL ACTION REQUIRED** |
| §29 aucun écran noir silencieux | **PASS VÉRIFIÉ** |
| §34 réseau `feba_jitsi_shared` | **PASS VÉRIFIÉ** — possédé par `docker-compose.yml`, rejoint ailleurs, créé par `jitsi_up.sh` |
| §35 `make jitsi-health` | **CORRIGÉ ET VÉRIFIÉ** — `external_api.js` et `/xmpp-websocket` ajoutés |
| §32/§33 deux participants, 30 minutes | **À TESTER EN ENVIRONNEMENT RÉEL** |
| §25 TURN / Coturn | **À TESTER EN ENVIRONNEMENT RÉEL** — non configuré à ce jour |

Détail : `JITSI_AUDIT_REPORT.md`, `VIRTUAL_CLASS_REPORT.md`.

---

## 5. Ce que les tests n'ont pas vu

Deux tests passaient **pour une mauvaise raison**, et les deux ont été
trouvés autrement que par la suite :

1. une fixture s'activait toute seule depuis un correctif antérieur : le
   test central passait **même avec le défaut d'origine** ;
2. deux tests attendaient un 404 qu'ils recevaient de l'URL absente —
   j'avais inséré un helper entre `@action` et `join`, supprimant la
   route. Ce sont les **parcours navigateur** qui l'ont montré.

1297 tests verts ne remplacent pas un vrai clic. C'est la raison d'être
de §31 et §48, et cette mission l'a démontré deux fois.

---

## 6. Non-régression FEBA (§3)

| Vérification | Résultat |
|---|---|
| Classes FEBA : 17, toutes `BILINGUAL`, inchangées par la migration | **PASS VÉRIFIÉ** |
| Règle bilingue toujours appliquée à FEBA | **PASS VÉRIFIÉ** (cas H) |
| Connexion et écrans FEBA | **PASS VÉRIFIÉ** (navigateur) |
| Bulletin bilingue FEBA inchangé | **PASS VÉRIFIÉ** |
| Enseignants, affectations, salles virtuelles | **PASS VÉRIFIÉ** |

---

## 7. Ce qui reste à faire, et par qui

`MANUAL_PRODUCTION_ACTIONS.md` et `KNOWN_LIMITATIONS.md`. Les points
saillants :

- **vérifier que l'adhésion anonyme est refusée** sur
  `meet.globalfeba.com` — si une salle s'ouvre sans FEBA, n'importe qui
  peut créer des salles sur le serveur ;
- **identifier le proxy réellement en service** : ses en-têtes ne
  correspondent pas au fichier du dépôt, et il ne pose ni
  `Referrer-Policy` ni `frame-ancestors` ;
- **UDP 10000** ouvert et joignable, sans quoi les participants entrent
  et ne se voient pas ;
- **TURN** : à évaluer sérieusement pour une école en ligne destinée à la
  diaspora, dont une partie sera derrière des réseaux bloquant l'UDP.

Aucun déploiement, aucune migration de production, aucune modification
DNS ni pare-feu n'a été effectué.

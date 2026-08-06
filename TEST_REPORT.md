# TEST_REPORT — résultats réellement obtenus

Tous les chiffres ci-dessous proviennent d'exécutions réelles dans
l'environnement de préparation de cette livraison. Aucun résultat n'est
estimé ou reproduit de mémoire.

Environnement : Python 3.11.15, Django 5.0.4, Node 22.22.2, npm 10.9.7.
Réglages backend : `feba_project.settings.test_sqlite` (SQLite en mémoire —
ni PostgreSQL, ni Redis, ni WeasyPrint requis).

## 1. Backend

```
python manage.py check
→ System check identified no issues (0 silenced).

python manage.py makemigrations --check --dry-run
→ No changes detected

python -m pytest -q
→ 1112 passed, 1 skipped, 530 subtests passed in 112.93s
```

**Référence avant modifications : 1 086 passants, 1 ignoré.**
**Après : 1 112 passants, 1 ignoré.** Soit +26, exactement le nombre de tests
ajoutés. Aucune régression.

Le test ignoré est un test de concurrence multi-threads que SQLite en mémoire
ne peut pas exécuter (verrou de table) ; il tourne sur PostgreSQL.

### Tests ajoutés — `tests/test_clean_previous_usage_data.py` (26)

Les 20 scénarios exigés, plus 6 : refus si aucun mode, refus si les deux
modes, académie inconnue refusée, complétude du rapport JSON, absence de fuite
du mot de passe de la base, absence de cascade sur les modèles structurels.

### Suites vérifiées pour les priorités 5 à 8

| Suite | Résultat | Priorité |
|---|---|---|
| `test_multi_currency.py` | 23 passants | P5 |
| `test_payments_summary_consolidation.py` | 12 passants | P5 |
| `test_schedule_separation.py` | 25 passants | P6 |
| `test_online_schedule_conflicts.py` | 7 passants | P6 |
| `test_fha_sheet_download_per_row.py` | 4 passants | P7 |
| `test_monthly_reports.py` | 65 passants | P8 |

Ces fonctionnalités étaient **déjà implémentées et couvertes** dans l'archive
source. Elles ont été vérifiées par exécution, non réimplémentées.

## 2. Frontend

```
npm run lint   → 0 erreur, 82 avertissements
npm test       → 179 tests passants (20 fichiers)
npm run build  → built in 8.21s
```

**Référence avant modifications : 163 passants.**
**Après : 179 passants.** Soit +16, exactement le nombre ajouté.

Les 82 avertissements de lint sont **préexistants** ; le code ajouté n'en
introduit aucun. Un avertissement initialement produit par la nouvelle
version d'`AcademyContext.jsx` (`setState` dans un effet) a été supprimé en
dérivant la portée pendant le rendu — ce qui renforce par ailleurs la
garantie d'ordre.

### Tests ajoutés

**`src/context/academyBoot.test.jsx` — 10 tests (P1)**

Ordre de démarrage ; portée appliquée avant toute requête métier ; chiffres
réels en portées `ALL`, `FEBA` et `FEBA_FHA` ; requête annulée sans affichage
de zéro ; dix actualisations consécutives ; attente explicite tant que la
portée n'est pas prête ; déduplication des appels concurrents ; relance après
résolution.

**`src/site/mobileLangSwitcher.test.jsx` — 6 tests (P9)**

Présence menu fermé ; deux langues étiquetées ; `aria-pressed` correct ;
changement effectif au clic ; pas de doublon menu ouvert ; sélecteur et bouton
menu dans le même conteneur.

## 3. Preuve de reproduction des bugs

Une correction non prouvée n'est qu'une modification. Les nouveaux tests ont
été exécutés **contre le code d'origine** pour vérifier qu'ils échouent bien.

**P1 — tableau de bord à zéro** : garde de portée et gestion des trois états
temporairement retirés → 4 tests sur 10 échouent :

```
× n'appelle pas /auth/users/ tant que /auth/entity-context/ n'a pas répondu
× applique la portée AVANT d'autoriser la requête métier
× reste en attente — sans afficher 0 — quand la requête est annulée
× affiche une attente explicite tant que la portée n'est pas prête
```

**P9 — bouton EN/FR** : sélecteur mobile temporairement retiré →
**6 tests sur 6 échouent**.

Dans les deux cas, le code corrigé a été restauré et l'intégralité des tests
repasse.

## 4. Correspondance avec les tests ciblés demandés

| Test demandé | Couverture |
|---|---|
| academy scope refresh | `academyBoot.test.jsx` (3 portées + 10 actualisations) |
| auth hydration | `academyBoot.test.jsx` (attente de `_hasHydrated`) |
| entity-context deduplication | `academyBoot.test.jsx` (2 tests) |
| stale response protection | `academyScope.test.js` (existant) + génération de portée |
| canceled request retention | `academyBoot.test.jsx` |
| cleanup command dry-run | `test_clean_previous_usage_data.py` n°1 |
| cleanup rollback | n°16 |
| cleanup idempotence | n°17 |
| cleanup per academy | n°18 |
| multi-tenant isolation | n°15 + suites d'isolation existantes |
| multi-currency payments | `test_multi_currency.py` |
| schedule parity | `test_schedule_separation.py` |
| FHA document downloads | `test_fha_sheet_download_per_row.py` |
| monthly report sending | `test_monthly_reports.py` |
| FHA form headings | build + couverture i18n |
| FHA formula selection | migration vérifiée + suite backend |
| flyer download | empreinte SHA-256 vérifiée dans `dist` |
| mobile language switcher | `mobileLangSwitcher.test.jsx` |

## 5. Non exécuté

**VALIDATION DOCKER LOCALE REQUISE.** Aucun démon Docker n'était disponible.
Non exécutés : `docker compose down -v`, `make install`, `make seed`,
`make seed-check`, `make documents-ready`, `make branding-check`,
`make jitsi-health`, `make celery-health`, `make install-check`, ainsi que les
tests e2e (13 fichiers) qui exigent un navigateur et la pile complète.

La commande réelle de nettoyage (`--execute`) **n'a jamais été exécutée sur
des données de production**.

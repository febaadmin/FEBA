# MONTHLY_REPORTS_FIX — envoi du rapport mensuel

**Priorité n°8.** Page : `/superadmin/monthly-reports`.
Statut : **déjà implémenté dans l'archive source — vérifié par exécution, aucune correction nécessaire.**

## Constat

L'archive source contient une implémentation complète du parcours d'envoi,
avec deux modèles dédiés (`MonthlyStudentReport`, `MonthlyReportAttempt`) —
le second existant précisément pour historiser chaque tentative, permettre
une nouvelle tentative et empêcher le double envoi.

`backend/tests/test_monthly_reports.py` — **65 tests, tous passants**

## Vérification effectuée

**EXÉCUTION** :

```
pytest tests/test_monthly_reports.py -q
→ 65 passed
```

La présence de `MonthlyReportAttempt` et le volume de la suite couvrent les
exigences d'historisation, de reprise et d'idempotence formulées dans la
demande.

## Ce qui n'a pas été fait

Aucune modification n'a été apportée.

**VALIDATION DOCKER LOCALE REQUISE** — les scénarios de bout en bout suivants
n'ont pas été rejoués contre la pile Docker : envoi réel via Mailpit en
développement, SMTP en erreur, Celery indisponible, pièce jointe manquante,
destinataire absent. Ils supposent les services `mailpit`, `redis` et
`celery-worker` démarrés, ce qui n'était pas possible dans cet environnement.
La suite de tests s'exécute avec le backend e-mail de test de Django, qui
vérifie la logique d'envoi mais pas la remise effective.

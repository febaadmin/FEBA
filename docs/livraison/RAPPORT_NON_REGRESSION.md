# Non-régression

| Contrôle | Résultat |
|---|---|
| CI PostgreSQL de la PR #44 | 2199 réussis, 3 ignorés, 0 échec |
| Migrations | Additives ; aucune sur `grades`, `bulletins` ou `payments` |
| Calcul des moyennes et bulletins | Code inchangé |
| Paiements | Seul changement : nouvelle référence retirée au sort si déjà prise |

## Échec CI n° 101 (PR #44)

Pas un ancien commit : les runs n° 101 et 102 ont testé le même commit `43b6429`. `test_seed_demo_data_complet` a échoué par collision de `reference_number` : le suffixe de 6 caractères n'était pas vérifié avant écriture. Le n° 102 est passé par hasard. Défaut réel, corrigé avec un test.

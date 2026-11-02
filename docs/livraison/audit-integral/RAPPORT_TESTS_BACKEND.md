# Tests backend

| Suite | Résultat, PR 53 |
|---|---|
| PostgreSQL | 2227 réussis, 3 ignorés, 0 échec |
| SQLite | 2219 réussis, 11 ignorés, 0 échec |
| Bulletin une page | 24 réussis |

**Échec à signaler :** run 41466038561, 1 échec sur `test_isolation_2_7_19_academies`, cause inconnue (anomalie A1). Aucun test n'a été désactivé ni affaibli.

Échec antérieur corrigé : collision de référence de paiement (CI 101, `_nouvelle_reference`).

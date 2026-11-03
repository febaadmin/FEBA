# Intégrité des données

Lecture seule, sauf la copie jetable décrite plus bas.

| Donnée | Relevé précédent | 03/11 | Explication |
|---|---|---|---|
| Notes | 935, dont 10 supprimées | 935, dont 10 | Inchangé |
| Paiements | 233 | 233 | Inchangé |
| Bulletins | 68 | 69 | Voir plus bas |
| Comptes | - | 164 | - |

## Bulletins

**Écart expliqué : génération manuelle, pas d'anomalie.**

| Bulletin | Date UTC | Académie | Élève | Origine au journal nginx |
|---|---|---|---|---|
| 87 | 02/11 22:49:59 | FEBA | 65 | `POST /api/bulletins/generate/` 201, après aperçu et commentaire, adresse 185.107.80.87 |
| 88 | 02/11 23:04:26 | FEBA | 116 | Idem |

- Aucune tâche planifiée pour les bulletins. Opérations de lot : les 2 dernières datent du 29/10.
- 0 doublon, contrainte d'unicité élève, année, période.
- Identifiants jusqu'à 88 pour 69 bulletins : des bulletins ont donc été supprimés par le passé. Non daté.
- **Limite :** le compte auteur n'est pas conservé pour ces deux bulletins. Il est journalisé désormais.

## Doublons

Paiements, annonces, devoirs et notes identiques créés à moins de 15 s : **0**.

## Restauration

**Logique, réussie :** `pg_dump` en lecture seule vers un PostgreSQL jetable sans réseau, sans fichier, supprimé ensuite. 5 s, 0 erreur, 118 tables.

| Table | Production | Copie |
|---|---|---|
| Notes | 935 | 935 |
| Paiements | 233 | 233 |
| Bulletins | 69 | 69 |
| Comptes | 164 | 164 |
| Élèves | 84 | 84 |
| Migrations | 178 | 178 |

**Restic, non testée :** root requis, non contourné.

## Incohérences à arbitrer

Voir `GUIDE_VALIDATION_HUMAINE.md`.

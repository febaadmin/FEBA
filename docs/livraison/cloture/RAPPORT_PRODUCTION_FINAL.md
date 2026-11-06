# Rapport de production (6 novembre 2026)

Toutes les vérifications sont en **lecture seule** (ou dans une transaction annulée). Aucune donnée réelle n'a été créée, modifiée ou supprimée.

## 1. Dépôt et déploiement

| Élément | État |
|---|---|
| PR #107 (phase 9) | fusionnée ; déployée (e460538). Une exécution CI de #107 avait échoué sur l'étape apt « LibreOffice » (délai dépassé, exécution parallèle verte) ; cause corrigée dans #108 |
| PR #108 (clôture) | CI verte sur a3c4d57 (2 exécutions, 12 contrôles, y compris l'E2E et l'étape LibreOffice) ; **fusionnée avec autorisation explicite** |
| Commit déployé | **1d11e67** (fusion de #108) ; déploiement 42200322787 réussi |
| Bundle servi | nouvel `index-*.js` (200), il contient les nouveaux écrans |

## 2. Services

`feba_backend_prod`, `feba_celery_prod`, `feba_celery_beat` (sains, redémarrés par le déploiement), `feba_frontend_prod`, `feba_nginx_prod`, `feba_postgres_prod` et `feba_redis_prod` (sains). Le bot OKX n'a pas été touché.

## 3. Migrations

- `payments 0018_remises_exonerations_echeanciers` est **appliquée** ; aucune migration n'est en attente.
- Elle est additive. Après déploiement : 0 règle, 0 échéancier personnel, 0 entrée de journal, 0 tarif, 247 paiements, tous inchangés.

## 4. Sauvegardes et certificat

- `feba-backup.timer` (restic) quotidien : dernière exécution réussie. La restauration n'a pas été rejouée dans cette mission.
- Le certificat TLS de globalfeba.com est valide jusqu'au **7 décembre 2026**. Certbot renouvelle automatiquement et la surveillance alerte sous le seuil.
- Disque : 36 %.

## 5. Contrôles après déploiement

| Contrôle | Résultat |
|---|---|
| Erreurs 5xx et traces d'exception depuis le redémarrage | 0 |
| Routes nouvelles sans session | 401, comme attendu (routes présentes) |
| Super administrateur et administrateur FEBA : situation, remises, barèmes, journal, échéanciers | 200 sur les 5 routes |
| Enseignant, parent, élève : mêmes routes | 403 sur les 5 routes |
| Situation FEBA | « non calculable » (aucun tarif). Total encaissé réel : **11 645 440 FCFA**, sur 4 mois, 79 élèves : **identique** au tableau de bord des paiements |
| Barème 2026-2027 (aperçu) | 9 tarifs à créer, 3 points à confirmer ; niveaux non reconnus : **GARDERIE** (service par abonnement, attendu) et **« MARTERNELLE 2 »** (faute de frappe dans le nom du niveau en production) |
| Surveillance de la plateforme (Celery) | aucun constat |

## 6. Ce qui n'a pas été fait en production (volontairement)

- Aucun barème importé, aucune remise ni exonération ou échéancier créé : ce sont des décisions de l'administration.
- Le niveau « MARTERNELLE 2 » n'a pas été renommé, car c'est une donnée réelle (voir SUIVI_REPRISE_FINAL.md).
- Aucun e-mail ni paiement réel.

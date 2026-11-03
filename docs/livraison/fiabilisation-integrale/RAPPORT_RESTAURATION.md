# Restauration

| Contrôle | Résultat | Niveau |
|---|---|---|
| Instantané Restic à chaque déploiement | Avant et après, dans le journal de déploiement | Production |
| Restauration logique | `pg_dump` en lecture seule vers un PostgreSQL jetable sans réseau ni fichier, puis supprimé : 0 erreur, 118 tables, comptes identiques sur 6 tables | Production, lecture seule |
| Restauration Restic | **Non testée** : root requis, non contourné | Décision humaine |

**Droits disponibles pour le compte de déploiement :** démarrage et état du service `feba-backup`, liste des instantanés Restic. Pas de restauration.

## Commande à lancer, en root, sur le serveur FEBA

```bash
cd /opt/feba/app/FEBA && bash scripts/test_restauration_isolee.sh
```

**Ce que fait le script :**
1. Contrôle de 5 % des données du dépôt.
2. Restauration du dernier instantané dans `/var/tmp/feba-restauration-*` (10 Go libres requis).
3. Chargement du dump dans un PostgreSQL jetable sans réseau.
4. Comparaison des comptes avec la production, par simple lecture.
5. Nettoyage.
6. Rapport dans `/root/feba-restauration-*.txt`.

**Il n'écrit jamais en production.**

**Non couvert :** restauration des fichiers médias, politique de rétention, copie hors serveur. À vérifier dans `/opt/feba/scripts/backup-local-restic.sh` avec les droits root.

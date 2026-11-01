# Test de restauration FEBA en environnement isolé

**Objectif :** prouver que la dernière sauvegarde Restic se recharge, sans toucher à la production.

## Ce que fait le script
1. Vérifie le dépôt Restic (5 % des données relues).
2. Restaure le dernier instantané dans `/var/tmp/feba-restauration-*`.
3. Charge le dump dans un conteneur PostgreSQL neuf, de même image, **sans réseau** (`--network none`).
4. Compare le nombre de lignes par table avec la production, par simples `SELECT count(*)`.
5. Compte les fichiers de médias de l'instantané et de la production.
6. Supprime le dossier et le conteneur, et garde un rapport dans `/root/`.

Il n'écrit rien dans la base de production, n'arrête aucun service et ne lance aucun `prune`. Il charge la machine le temps de la restauration : à lancer hors des heures de cours.

## Droits nécessaires
Une seule session root ponctuelle : la clé du dépôt et le script de sauvegarde sont réservés à root. Le compte `deploy` ne peut que lister les instantanés, et il ne faut pas élargir ses droits durablement.

## Commandes (sur 62.238.38.111, en root)
```bash
cd /opt/feba/app/FEBA && git pull --ff-only
```
```bash
bash /opt/feba/app/FEBA/scripts/test_restauration_isolee.sh
```

## Après l'exécution
Transmettez le contenu de `/root/feba-restauration-*.txt`. Il ne contient aucun secret ni donnée d'élève, seulement des comptages et des noms de tables.

**Réussite :** aucune erreur de chargement, mêmes tables, comptages égaux ou écarts expliqués par les écritures depuis la sauvegarde.

**Limite :** le script n'a jamais tourné sur le serveur réel. Si le dépôt ou le dump ne sont pas trouvés, il s'arrête sans rien modifier et liste ce qu'il voit.

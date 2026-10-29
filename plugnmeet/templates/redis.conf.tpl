# Redis de plugNmeet — généré par scripts/plugnmeet_setup.sh. Ne pas éditer.
# Le mot de passe est ICI et non dans la ligne de commande : un argument de
# processus est lisible par tout compte de l'hôte (ps, /proc/<pid>/cmdline).
requirepass ${PNM_REDIS_PASSWORD}
appendonly yes
dir /data

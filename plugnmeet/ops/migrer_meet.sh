#!/usr/bin/env bash
# Bascule de meet.globalfeba.com de Jitsi vers plugNmeet, ou retour.
# À lancer depuis le poste d'administration (accès SSH aux deux serveurs),
# APRÈS « meet_plugnmeet.sh preparer » sur le serveur vidéo.
#
#   migrer_meet.sh basculer   aiguilleur meet → plugNmeet, puis FEBA → plugNmeet
#   migrer_meet.sh retour     aiguilleur meet → Jitsi, puis FEBA → Jitsi
#
# Entre les deux étapes (quelques secondes), FEBA et meet ne désignent pas
# le même service : à faire hors des heures de cours.
set -uo pipefail

ICI=$(cd "$(dirname "$0")" && pwd)
VIDEO="ssh -o BatchMode=yes -i ${VIDEO_KEY:-$HOME/.ssh/feba_jitsi_prod} root@89.167.63.1"
SRV=/opt/feba/pnm/FEBA/plugnmeet/ops/meet_plugnmeet.sh
export PNM_URL=https://meet.globalfeba.com

case "${1:-}" in
basculer)
  $VIDEO "$SRV aiguilleur plugnmeet" </dev/null || { echo "ARRÊT : aiguilleur inchangé, FEBA inchangé"; exit 1; }
  sortie=$("$ICI/basculer_feba.sh" executer 2>&1); echo "$sortie"
  if echo "$sortie" | grep -q 'fournisseur : plugnmeet'; then
    echo "BASCULE TERMINÉE : meet.globalfeba.com sert plugNmeet, FEBA utilise plugNmeet"
    exit 0
  fi
  echo "ÉCHEC côté FEBA : retour arrière"
  # .env.prod n'est restauré que si cette bascule l'a modifié (sauvegarde faite).
  echo "$sortie" | grep -q 'sauvegarde de .env.prod' && "$ICI/basculer_feba.sh" retour
  $VIDEO "$SRV aiguilleur jitsi" </dev/null
  exit 1
  ;;
retour)
  $VIDEO "$SRV aiguilleur jitsi" </dev/null || echo "ATTENTION : aiguilleur non rétabli (voir ci-dessus)"
  "$ICI/basculer_feba.sh" retour
  ;;
*) echo "usage : $0 basculer | retour"; exit 2 ;;
esac

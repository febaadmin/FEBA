#!/bin/bash
# Ancien point d'entrée du déploiement : conservé pour les habitudes, il
# délègue à scripts/deploy_feba.sh (sauvegarde vérifiée, contrôle de
# pré-démarrage, tests de fumée, retour arrière automatique). L'ancienne
# version reconstruisait sans cache, arrêtait tout (« down ») et ne passait
# pas --env-file.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
git pull origin main
exec bash scripts/deploy_feba.sh "$@"

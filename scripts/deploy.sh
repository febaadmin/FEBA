#!/bin/bash
# Script de déploiement production FEBA v29
set -e

echo "🚀 Déploiement FEBA School Management..."

# Pull dernières modifications
git pull origin main

# Rebuild et redémarrage des conteneurs
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# NOTE: entrypoint.prod.py exécute désormais automatiquement, à chaque
# démarrage du conteneur backend-prod : manage.py check, migrate, puis
# collectstatic — dans cet ordre, avec arrêt explicite et message clair
# si l'une de ces étapes échoue. Il n'est donc plus nécessaire de les
# relancer manuellement ici.

echo "⏳ En attente que le backend soit opérationnel (healthcheck)..."
for i in $(seq 1 30); do
    status=$(docker inspect feba_backend_prod --format '{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    if [ "$status" = "healthy" ]; then
        echo "✅ Backend opérationnel."
        break
    fi
    if [ "$status" = "unhealthy" ]; then
        echo "❌ Le backend est en échec (unhealthy). Voir les logs :"
        docker compose -f docker-compose.prod.yml logs --tail=100 backend-prod
        exit 1
    fi
    sleep 3
done

echo "✅ Déploiement terminé !"
echo "📊 État des conteneurs :"
docker compose -f docker-compose.prod.yml ps

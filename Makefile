# FEBA School Management — Makefile
#
# Raccourcis pour éviter les erreurs de frappe sur les commandes Docker
# (flag -f oublié, mauvais nom de service, etc.). Utilisation :
#
#   make dev          → démarre l'environnement de développement
#   make migrate       → applique les migrations
#   make superuser      → crée un compte superadmin
#   make seed            → charge les données de démonstration
#   make logs              → logs du backend en temps réel
#   make logs-all            → logs de tous les conteneurs
#   make ps                    → état des conteneurs
#   make down                    → arrête l'environnement (garde les données)
#   make reset                     → arrête ET supprime les données (repart de zéro)
#   make test                        → lance la suite de tests
#   make shell                         → shell Django (manage.py shell)
#   make diagnose                        → diagnostic en cas de problème
#   make prod                              → démarre l'environnement de production

.PHONY: dev migrate superuser seed jitsi-up jitsi-down logs logs-all ps down reset test shell diagnose prod prod-down prod-logs help

help:
	@echo "Commandes disponibles :"
	@echo "  make dev         - Démarre l'environnement de développement (build + up -d)"
	@echo "  make migrate     - Applique les migrations Django"
	@echo "  make superuser   - Crée un compte superadmin"
	@echo "  make seed        - Charge les données de démonstration"
	@echo "  make logs        - Logs du backend en temps réel"
	@echo "  make logs-all    - Logs de tous les conteneurs"
	@echo "  make ps          - État des conteneurs"
	@echo "  make down        - Arrête l'environnement (conserve les données)"
	@echo "  make reset       - Arrête ET supprime les données (repart de zéro)"
	@echo "  make test        - Lance la suite de tests backend"
	@echo "  make shell       - Ouvre un shell Django (manage.py shell)"
	@echo "  make diagnose    - Affiche un diagnostic complet en cas de problème"
	@echo "  make prod        - Démarre l'environnement de production"
	@echo "  make prod-logs   - Logs du backend de production"
	@echo "  make prod-down   - Arrête l'environnement de production"

dev:
	docker compose up --build -d
	@echo ""
	@echo "Démarrage en cours. Suivre la progression : make logs"
	@echo "Une fois prêt : http://localhost:5173 (frontend) — http://localhost:8000/api/ (API)"

migrate:
	docker compose exec backend-dev python manage.py migrate

superuser:
	docker compose exec backend-dev python manage.py createsuperuser

seed:
	docker compose exec backend-dev python manage.py seed_demo_data

# ── Pile Jitsi auto-hébergée (visioconférence JWT) ──────────────────────
jitsi-up:
	@test -f .env.jitsi || (echo "⚠ Copiez d'abord .env.jitsi.example en .env.jitsi et renseignez les secrets (openssl rand -hex 32)"; exit 1)
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi up -d
	@echo "✅ Jitsi : http://localhost:8443 — configurez côté FEBA : JITSI_DOMAIN=localhost:8443 + JITSI_APP_ID/SECRET identiques à .env.jitsi"

jitsi-down:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi down

logs:
	docker compose logs -f backend-dev

logs-all:
	docker compose logs -f

ps:
	docker compose ps -a

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up --build -d

test:
	docker compose exec backend-dev python manage.py test tests/

shell:
	docker compose exec backend-dev python manage.py shell

diagnose:
	bash scripts/diagnose.sh

prod:
	docker compose -f docker-compose.prod.yml up --build -d

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f backend-prod

prod-down:
	docker compose -f docker-compose.prod.yml down

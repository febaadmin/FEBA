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

.PHONY: install bootstrap dev migrate superuser seed seed-reset seed-check init-academies \
        test-sqlite test-postgres test-frontend test-e2e \
        payments-setup payments-check payments-test payments-webhook-check \
        documents-check documents-install documents-ready documents-calibrate documents-compare \
        branding-check \
        jitsi-up jitsi-down jitsi-logs jitsi-health health logs logs-all ps down reset \
        test shell diagnose prod prod-down prod-logs help

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
	@echo ""
	@echo "  Paiement par carte :"
	@echo "  make payments-setup         - Configure les clés du prestataire (guidé)"
	@echo "  make payments-check         - Vérifie configuration et identifiants"
	@echo "  make payments-test          - Lance la suite de tests du paiement"
	@echo "  make payments-webhook-check - Diagnostique la réception des événements"
	@echo ""
	@echo "  Documents officiels :"
	@echo "  make documents-check        - État des gabarits (fond, empreinte, calibrage)"
	@echo "  make documents-ready        - Les documents sont-ils produisibles MAINTENANT ?"
	@echo "  make documents-install      - Répare un fond neutralisé absent ou altéré"
	@echo "  make branding-check         - Identité visuelle de chaque académie"
	@echo "  make documents-calibrate    - Planche de calibrage millimétrée"
	@echo "  make documents-compare      - Comparaison pixel à pixel du fond"
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

# Réinitialise puis regénère les données de démonstration.
# Refusé si l'environnement est marqué production (garde-fou dans la commande).
seed-reset:
	docker compose exec backend-dev python manage.py seed_demo_data --reset

# Contrôle d'intégrité : aucune relation inter-académie, aucun objet orphelin.
seed-check:
	docker compose exec -T backend-dev python manage.py seed_check

# ── Pile Jitsi auto-hébergée (visioconférence JWT) ──────────────────────
# Installation complète en une commande : prérequis, secrets générés,
# services, Jitsi auto-hébergé, migrations, académies, health checks.
install: bootstrap
bootstrap:
	@bash scripts/bootstrap.sh

# Démarre l'instance Jitsi AUTO-HÉBERGÉE. Les secrets manquants sont
# générés automatiquement : plus aucune étape manuelle, et surtout aucun
# repli vers une instance publique.
jitsi-up:
	@bash scripts/jitsi_up.sh

jitsi-down:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi down

jitsi-logs:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi logs -f

# Vérifie l'instance : configuration, signature de jeton, joignabilité.
# Code de sortie non nul si l'instance n'est pas opérationnelle.
jitsi-health:
	docker compose exec -T backend-dev python manage.py jitsi_health

health: jitsi-health
	@docker compose exec -T backend-dev python manage.py check --deploy 2>/dev/null || true
	@echo "✅ Vérifications de santé terminées"

init-academies:
	docker compose exec -T backend-dev python manage.py init_academies

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

# Suite backend sur les DEUX moteurs. SQLite sert au développement local
# sans PostgreSQL ; PostgreSQL est le moteur de production et fait foi.
test-sqlite:
	cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite python -m pytest -q

test-postgres:
	cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_postgres python -m pytest -q

test-frontend:
	cd frontend && npx vitest run && npx eslint src --ext .js,.jsx && npm run build

# Parcours navigateur réels — voir e2e/README.md (backend + frontend démarrés).
test-e2e:
	node e2e/academies.mjs
	node e2e/espaces-anglais.mjs
	node e2e/site-public-anglais.mjs

# ── Paiement par carte ────────────────────────────────────────────────
# Aucune de ces cibles n'invente de clé : les identifiants viennent du
# tableau de bord du prestataire. Sans compte marchand valide, aucun
# encaissement réel n'est possible.

payments-setup:
	cd backend && python manage.py payments_setup --env-file ../.env

payments-check:
	cd backend && python manage.py payments_check

payments-test:
	cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
		python -m pytest tests/test_card_payments.py tests/test_multi_currency.py -q

payments-webhook-check:
	cd backend && python manage.py payments_webhook_check

# ── Documents officiels ───────────────────────────────────────────────
# Les fonds (Diplôme FEBA(2).png, Certificat FEBA(2).png) ne sont pas
# versionnés : ce sont des documents de l'établissement. Ils s'installent
# avec « manage.py install_document_template », qui vérifie dimensions et
# empreinte avant de copier quoi que ce soit.

documents-check:
	cd backend && python manage.py document_templates_check

# P7 — Le diplôme doit être utilisable DÈS L'INSTALLATION.
#
# Le fond neutralisé est versionné avec le projet : il arrive avec
# l'archive, son empreinte est déclarée dans le gabarit, et
# « documents-ready » la vérifie. Personne n'a plus à lancer
# « document_neutralize » pour obtenir un diplôme.
#
# Cette cible reste utile dans un seul cas : réparer une installation dont
# le fichier a été supprimé ou altéré. La régénération est déterministe —
# elle rend exactement la même empreinte.
documents-install:
	cd backend && python manage.py document_neutralize --template diploma_feba
	cd backend && python manage.py document_neutralize --template certificate_feba
	cd backend && python manage.py document_templates_check
	cd backend && python manage.py documents_ready

# Réponse en une commande : les documents officiels sortent-ils, ici,
# maintenant ? Sort en erreur sinon — c'est ce qui en fait une étape
# d'installation, et non un diagnostic qu'on pense à lancer trop tard.
documents-ready:
	cd backend && python manage.py documents_ready

branding-check:
	cd backend && python manage.py branding_check

documents-calibrate:
	cd backend && python manage.py document_calibrate --template diploma_feba
	cd backend && python manage.py document_calibrate --template certificate_feba

documents-compare:
	cd backend && python manage.py document_compare --template diploma_feba
	cd backend && python manage.py document_compare --template certificate_feba

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

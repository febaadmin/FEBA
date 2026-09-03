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

.PHONY: install bootstrap dev migrate migrations-plan superuser seed seed-reset seed-check init-academies \
        test-sqlite test-postgres test-frontend test-e2e test-install \
        payments-setup payments-check payments-test payments-webhook-check \
        documents-check documents-install documents-ready documents-calibrate documents-compare \
        branding-check \
        jitsi-up jitsi-down jitsi-restart jitsi-logs jitsi-health jitsi-config-check \
        jitsi-prod-up jitsi-prod-down jitsi-prod-logs \
        jitsi-proxy-up jitsi-proxy-down jitsi-proxy-logs \
        health logs logs-all ps down reset \
        test shell diagnose doctor install-check repair prod prod-down prod-logs help

# P6 — Point de passage UNIQUE vers Django : toujours à travers le
# conteneur backend-dev, jamais un `python` local. Sur macOS sans Python
# installé, `cd backend && python manage.py ...` échouait avec
# « python: command not found » ; ces cibles ne dépendent plus que de
# Docker, déjà requis par tout le reste du projet.
COMPOSE := docker compose
MANAGE  := $(COMPOSE) exec -T backend-dev python manage.py

help:
	@echo "Commandes disponibles :"
	@echo "  make dev         - Démarre l'environnement de développement (build + up -d)"
	@echo "  make install     - Installation complète depuis un poste vierge"
	@echo "  make doctor      - Vérifie prérequis et .env.dev AVANT de démarrer quoi que ce soit"
	@echo "  make install-check - Vérifie qu'une installation a RÉELLEMENT réussi"
	@echo "  make repair      - Répare une installation démarrée mais en échec"
	@echo "  make migrate     - Applique les migrations Django"
	@echo "  make migrations-plan - Migrations en attente (doit afficher : aucune)"
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
	$(MANAGE) migrate --noinput

# P5 — Ce que « make install » doit afficher après coup :
# « No planned migration operations. » Sinon, une migration a été
# oubliée ou deux processus de migration ont divergé.
migrations-plan:
	$(MANAGE) migrate --plan

superuser:
	$(COMPOSE) exec backend-dev python manage.py createsuperuser

seed:
	$(MANAGE) seed_demo_data

# Réinitialise puis regénère les données de démonstration.
# Refusé si l'environnement est marqué production (garde-fou dans la commande).
seed-reset:
	$(MANAGE) seed_demo_data --reset

# Contrôle d'intégrité : aucune relation inter-académie, aucun objet orphelin.
seed-check:
	$(MANAGE) seed_check

# ── Pile Jitsi auto-hébergée (visioconférence JWT) ──────────────────────
# Installation complète en une commande : prérequis, secrets générés,
# services, Jitsi auto-hébergé, migrations, académies, health checks.
# P9 — Installation en étapes contrôlées : doctor (prérequis + .env.dev)
# puis le pipeline complet de scripts/bootstrap.sh (secrets, services,
# migrations via le service dédié, académies, documents, Jitsi), puis
# une vérification complète pour confirmer que ça a RÉELLEMENT marché.
install: bootstrap
bootstrap:
	@bash scripts/doctor.sh || true
	@bash scripts/bootstrap.sh
	@echo ""
	@bash scripts/install_check.sh || \
		echo "⚠ Certains contrôles post-installation ont échoué — voir ci-dessus, ou « make repair »."

# Démarre l'instance Jitsi AUTO-HÉBERGÉE. Les secrets manquants sont
# générés automatiquement : plus aucune étape manuelle, et surtout aucun
# repli vers une instance publique.
jitsi-up:
	@bash scripts/jitsi_up.sh

jitsi-down:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi down

# Redémarre la pile sans régénérer les secrets : les jetons déjà émis
# restent valides, les cours en séance ne sont pas invalidés.
jitsi-restart:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi restart
	@echo "Instance redémarrée — vérifiez avec « make jitsi-health »."

jitsi-logs:
	docker compose -f docker-compose.jitsi.yml --env-file .env.jitsi logs -f

# Vérifie l'instance : configuration, signature de jeton, DNS, TLS, HTTP,
# page Jitsi. Code de sortie non nul si l'instance n'est pas opérationnelle.
#
# JITSI_TARGET permet de contrôler une instance PRÉCISE, en particulier
# celle de production, sans déployer de configuration :
#     make jitsi-health JITSI_TARGET=meet.globalfeba.com
#
# Le contrôle passe par le conteneur backend quand il tourne, sinon par un
# Python local : « make jitsi-health » ne doit pas être indisponible juste
# parce que la pile de développement est arrêtée — c'est précisément quand
# quelque chose ne va pas qu'on en a besoin.
JITSI_TARGET ?=
JITSI_HEALTH_ARGS = $(if $(JITSI_TARGET),--domain $(JITSI_TARGET),)

jitsi-health:
	@if docker compose ps --status running backend-dev 2>/dev/null | grep -q backend-dev; then \
		docker compose exec -T backend-dev python manage.py jitsi_health $(JITSI_HEALTH_ARGS); \
	else \
		echo "(conteneur backend-dev arrêté — contrôle depuis l'hôte)"; \
		cd backend && python3 manage.py jitsi_health $(JITSI_HEALTH_ARGS); \
	fi

# ── Production : meet.globalfeba.com ─────────────────────────────────
# La surcouche ajoute TLS Let's Encrypt, les ports 80/443 et l'IP publique
# annoncée par le pont vidéo. Elle ne remplace pas la pile de base : les
# deux fichiers sont passés ensemble, sinon la configuration diverge à la
# première correction faite d'un seul côté.
JITSI_PROD_COMPOSE = -f docker-compose.jitsi.yml -f docker-compose.jitsi.prod.yml --env-file .env.jitsi

# ── Topologie « MÊME SERVEUR que FEBA » ──────────────────────────────
# Jitsi n'écoute que sur la boucle locale ; c'est le nginx de FEBA qui
# termine TLS et sert meet.globalfeba.com. À utiliser dès lors que le
# serveur héberge DÉJÀ globalfeba.com : la surcouche `prod` ci-dessous
# publierait 80 et 443, que nginx-prod occupe déjà.
JITSI_PROXY_COMPOSE = -f docker-compose.jitsi.yml -f docker-compose.jitsi.behind-proxy.yml --env-file .env.jitsi

jitsi-proxy-up:
	@bash scripts/jitsi_config_check.sh || echo "⚠ Configuration incohérente — voir ci-dessus."
	docker compose $(JITSI_PROXY_COMPOSE) up -d
	@echo ""
	@echo "Jitsi écoute sur 127.0.0.1:$${JITSI_PROXY_PORT:-8443} — inaccessible de l'extérieur."
	@echo "Activez ensuite le vhost côté FEBA :"
	@echo "  cp nginx/sites-available/meet.globalfeba.com.conf nginx/sites-enabled/"
	@echo "  docker compose -f docker-compose.prod.yml exec nginx-prod nginx -t   # AVANT de recharger"
	@echo "  docker compose -f docker-compose.prod.yml exec nginx-prod nginx -s reload"

jitsi-proxy-down:
	docker compose $(JITSI_PROXY_COMPOSE) down

jitsi-proxy-logs:
	docker compose $(JITSI_PROXY_COMPOSE) logs -f

jitsi-prod-up:
	@bash scripts/jitsi_config_check.sh || echo "⚠ Configuration incohérente — voir ci-dessus."
	docker compose $(JITSI_PROD_COMPOSE) up -d
	@echo "Instance démarrée. Vérifiez : make jitsi-health JITSI_TARGET=$${JITSI_DOMAIN:-meet.globalfeba.com}"

jitsi-prod-down:
	docker compose $(JITSI_PROD_COMPOSE) down

jitsi-prod-logs:
	docker compose $(JITSI_PROD_COMPOSE) logs -f

# Contrôle de COHÉRENCE de la configuration, sans réseau : ce que les
# fichiers déclarent, avant même de savoir si l'instance répond. Utilisable
# en CI, où meet.globalfeba.com n'est de toute façon pas joignable.
jitsi-config-check:
	@bash scripts/jitsi_config_check.sh

health: jitsi-health
	@docker compose exec -T backend-dev python manage.py check --deploy 2>/dev/null || true
	@echo "✅ Vérifications de santé terminées"

init-academies:
	$(MANAGE) init_academies

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

# P10 — Installation propre depuis zéro, sur CETTE machine (Linux x86_64,
# ARM64, ou macOS Apple Silicon avec Docker Desktop : le même script vaut
# pour les trois, voir l'en-tête du script). Détruit et recrée
# l'environnement Docker local.
test-install:
	bash tests/installation/test_clean_docker_install.sh --in-place

# ── Paiement par carte ────────────────────────────────────────────────
# Aucune de ces cibles n'invente de clé : les identifiants viennent du
# tableau de bord du prestataire. Sans compte marchand valide, aucun
# encaissement réel n'est possible.

# payments-setup EST DIFFÉRENT des autres cibles ci-dessous : c'est un
# outil interactif qui ÉCRIT sur le poste hôte (le fichier .env.dev n'est
# PAS monté dans le conteneur backend-dev, volontairement — un secret de
# paiement n'a rien à faire dans une image Docker). Il a donc besoin d'un
# Python local. S'il est absent, le message ci-dessous le dit clairement
# plutôt que de laisser échouer avec « command not found ».
payments-setup:
	@command -v python3 >/dev/null 2>&1 || { \
		echo "✗ python3 est requis pour cette commande (elle écrit directement sur votre poste, hors Docker)."; \
		echo "  Installez Python 3, ou éditez .env.dev à la main (voir .env.dev.example)."; \
		exit 1; \
	}
	cd backend && python3 manage.py payments_setup --env-file ../.env.dev

payments-check:
	$(MANAGE) payments_check

payments-test:
	cd backend && DJANGO_SETTINGS_MODULE=feba_project.settings.test_sqlite \
		python -m pytest tests/test_card_payments.py tests/test_multi_currency.py tests/test_payments_summary_consolidation.py -q

payments-webhook-check:
	$(MANAGE) payments_webhook_check

# ── Documents officiels ───────────────────────────────────────────────
# Les fonds (Diplôme FEBA(2).png, Certificat FEBA(2).png) ne sont pas
# versionnés : ce sont des documents de l'établissement. Ils s'installent
# avec « manage.py install_document_template », qui vérifie dimensions et
# empreinte avant de copier quoi que ce soit.

documents-check:
	$(MANAGE) document_templates_check

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
	$(MANAGE) document_neutralize --template diploma_feba
	$(MANAGE) document_neutralize --template certificate_feba
	$(MANAGE) document_templates_check
	$(MANAGE) documents_ready

# Réponse en une commande : les documents officiels sortent-ils, ici,
# maintenant ? Sort en erreur sinon — c'est ce qui en fait une étape
# d'installation, et non un diagnostic qu'on pense à lancer trop tard.
documents-ready:
	$(MANAGE) documents_ready

branding-check:
	$(MANAGE) branding_check

documents-calibrate:
	$(MANAGE) document_calibrate --template diploma_feba
	$(MANAGE) document_calibrate --template certificate_feba

documents-compare:
	$(MANAGE) document_compare --template diploma_feba
	$(MANAGE) document_compare --template certificate_feba

shell:
	docker compose exec backend-dev python manage.py shell

diagnose:
	bash scripts/diagnose.sh

doctor:
	bash scripts/doctor.sh

install-check:
	bash scripts/install_check.sh

repair:
	bash scripts/repair.sh

prod:
	docker compose -f docker-compose.prod.yml up --build -d

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f backend-prod

prod-down:
	docker compose -f docker-compose.prod.yml down

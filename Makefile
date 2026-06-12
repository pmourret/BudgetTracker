# Makefile — BudgetTracker
# Usage : make <cible>   (ex. make up, make logs, make migrate)

# --- Configuration ---
COMPOSE_PROD := docker compose -f docker-compose.prod.yml --env-file .env.prod
COMPOSE_DEV  := docker compose -f docker-compose.yml --env-file .env
BACKEND_PROD := $(COMPOSE_PROD) exec backend python manage.py
BACKEND_DEV  := $(COMPOSE_DEV) exec backend python manage.py

.DEFAULT_GOAL := help

# ==========================================================
# PRODUCTION
# ==========================================================

.PHONY: up
up: ## Lance la stack prod en arrière-plan
	$(COMPOSE_PROD) up -d

.PHONY: build
build: ## Rebuild les images prod
	$(COMPOSE_PROD) build

.PHONY: rebuild
rebuild: ## Rebuild sans cache puis relance
	$(COMPOSE_PROD) build --no-cache
	$(COMPOSE_PROD) up -d

.PHONY: down
down: ## Stoppe la stack prod (garde les volumes)
	$(COMPOSE_PROD) down

.PHONY: restart
restart: ## Redémarre tous les services prod
	$(COMPOSE_PROD) restart

.PHONY: ps
ps: ## État des conteneurs prod
	$(COMPOSE_PROD) ps

.PHONY: logs
logs: ## Suit les logs de tous les services (Ctrl+C pour quitter)
	$(COMPOSE_PROD) logs -f

.PHONY: logs-backend
logs-backend: ## Suit les logs du backend
	$(COMPOSE_PROD) logs -f backend

.PHONY: logs-db
logs-db: ## Suit les logs de la base
	$(COMPOSE_PROD) logs -f db

# ==========================================================
# DJANGO (prod)
# ==========================================================

.PHONY: migrate
migrate: ## Applique les migrations
	$(BACKEND_PROD) migrate

.PHONY: makemigrations
makemigrations: ## Génère les migrations (make makemigrations app=flux)
	$(BACKEND_PROD) makemigrations $(app)

.PHONY: check
check: ## manage.py check
	$(BACKEND_PROD) check

.PHONY: seed
seed: ## Charge les données de démo
	$(BACKEND_PROD) seed_demo

.PHONY: test
test: ## Lance les tests (make test app=analytics pour cibler)
	$(BACKEND_PROD) test $(app)

.PHONY: superuser
superuser: ## Crée un superutilisateur Django
	$(BACKEND_PROD) createsuperuser

.PHONY: shell
shell: ## Ouvre un shell Django
	$(BACKEND_PROD) shell

.PHONY: bash
bash: ## Ouvre un bash dans le conteneur backend
	$(COMPOSE_PROD) exec backend bash

# ==========================================================
# INITIALISATION
# ==========================================================

.PHONY: init
init: up ## Première mise en route : up + migrate + seed
	@echo "Attente de la base..."
	@sleep 5
	$(BACKEND_PROD) migrate
	$(BACKEND_PROD) seed_demo
	@echo "Initialisation terminée."

.PHONY: reset-db
reset-db: ## ⚠️  DÉTRUIT la base (volume pgdata) puis réinitialise
	$(COMPOSE_PROD) down
	sudo rm -rf /var/lib/docker/hiatus/budgets/pgdata
	$(MAKE) init

# ==========================================================
# DEV (local)
# ==========================================================

.PHONY: dev-up
dev-up: ## Lance la stack de dev
	$(COMPOSE_DEV) up -d

.PHONY: dev-down
dev-down: ## Stoppe la stack de dev
	$(COMPOSE_DEV) down

.PHONY: dev-logs
dev-logs: ## Logs de la stack de dev
	$(COMPOSE_DEV) logs -f

# ==========================================================
# AIDE
# ==========================================================

.PHONY: help
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
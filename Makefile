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
seed: ## Charge les référentiels structurels (prod, idempotent — PAS de données de démo)
	$(BACKEND_PROD) seed_referentiels

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
init: up ## Première mise en route : up + migrate + référentiels structurels (PAS de démo)
	@echo "Attente de la base..."
	@sleep 5
	$(BACKEND_PROD) migrate
	$(BACKEND_PROD) seed_referentiels
	@echo "Initialisation terminée."

.PHONY: reset-db
reset-db: ## ⚠️  DÉTRUIT la base (volume pgdata) puis réinitialise
	@echo "⚠️  Cette opération DÉTRUIT TOUTES les données (volume pgdata)."
	@read -p "Taper 'CONFIRMER' pour continuer : " ans; [ "$$ans" = "CONFIRMER" ] || { echo "Annulé."; exit 1; }
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

.PHONY: dev-seed
dev-seed: ## Charge les données de démo (DEV uniquement — compte + catégories de démo)
	$(BACKEND_DEV) seed_demo

# ==========================================================
# AIDE
# ==========================================================

.PHONY: help
help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ==========================================================
# MISE À JOUR / DÉPLOIEMENT
# ==========================================================

.PHONY: pull
pull: ## Récupère les derniers commits (git pull)
	git pull --ff-only

.PHONY: deploy
deploy: ## Montée de version standard : pull + build + up + migrate + collectstatic
	$(MAKE) backup
	git pull --ff-only
	$(COMPOSE_PROD) build
	$(COMPOSE_PROD) up -d
	@echo "Attente du backend..."
	@sleep 5
	$(BACKEND_PROD) migrate
	$(BACKEND_PROD) collectstatic --noinput
	$(BACKEND_PROD) check
	@echo "Déploiement terminé."

.PHONY: deploy-front
deploy-front: ## Montée de version frontend uniquement (rebuild image front + nginx)
	git pull --ff-only
	$(COMPOSE_PROD) build frontend
	$(COMPOSE_PROD) up -d frontend

.PHONY: backup
backup: ## Dump SQL horodaté de la base (avant migration)
	@mkdir -p backups
	$(COMPOSE_PROD) exec -T db pg_dump -U $${POSTGRES_USER:-budget} $${POSTGRES_DB:-budgettracker} \
		> backups/budgettracker_$$(date +%Y%m%d_%H%M%S).sql
	@echo "Backup créé dans ./backups/"

.PHONY: restore
restore: ## Restaure un dump : make restore file=backups/xxx.sql
	@test -n "$(file)" || { echo "Usage : make restore file=backups/xxx.sql"; exit 1; }
	cat $(file) | $(COMPOSE_PROD) exec -T db psql -U $${POSTGRES_USER:-budget} $${POSTGRES_DB:-budgettracker}
	@echo "Restauration depuis $(file) terminée."
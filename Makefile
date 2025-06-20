# ABOUTME: Makefile for Reddit Technical Watcher development and deployment tasks
# ABOUTME: Provides convenient targets for Docker operations, testing, and development

.PHONY: help dev build up down logs clean test lint format migrate

# Default target
help: ## Show this help message
	@echo "Reddit Technical Watcher - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development
dev: ## Start development stack with all services
	docker-compose up --build -d
	@echo "Development stack started. Services available at:"
	@echo "  Coordinator Agent: http://localhost:8000"
	@echo "  Retrieval Agent:   http://localhost:8001"
	@echo "  Filter Agent:      http://localhost:8002"
	@echo "  Summarise Agent:   http://localhost:8003"
	@echo "  Alert Agent:       http://localhost:8004"
	@echo "  PostgreSQL:        localhost:5432"
	@echo "  Redis:             localhost:6379"

# Docker operations
build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

clean: ## Clean up Docker resources
	docker-compose down -v --remove-orphans
	docker system prune -f

# Development tools
test: ## Run tests
	uv run pytest

lint: ## Run linting
	uv run ruff check .

format: ## Format code
	uv run ruff format .

fix: ## Fix linting issues
	uv run ruff check --fix .

# Database operations
migrate: ## Run database migrations
	uv run alembic upgrade head

# Local development
install: ## Install dependencies
	uv sync

pre-commit: ## Install pre-commit hooks
	uv run pre-commit install

# Service management
ps: ## Show running services
	docker-compose ps

restart: ## Restart all services
	docker-compose restart

# Logs for specific services
logs-coordinator: ## Show coordinator agent logs
	docker-compose logs -f coordinator-agent

logs-retrieval: ## Show retrieval agent logs
	docker-compose logs -f retrieval-agent

logs-filter: ## Show filter agent logs
	docker-compose logs -f filter-agent

logs-summarise: ## Show summarise agent logs
	docker-compose logs -f summarise-agent

logs-alert: ## Show alert agent logs
	docker-compose logs -f alert-agent

logs-db: ## Show database logs
	docker-compose logs -f db

logs-redis: ## Show Redis logs
	docker-compose logs -f redis

# ABOUTME: Makefile for Reddit Technical Watcher development and deployment tasks
# ABOUTME: Provides convenient targets for Docker operations, testing, and development

.PHONY: help dev build up down logs clean test lint format migrate test-integration test-smoke test-setup test-cleanup test-logs

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

# Integration Testing
test-integration: ## Run full integration tests
	python run_integration_tests.py

test-smoke: ## Run smoke tests only (fast subset)
	python run_integration_tests.py --smoke

test-fast: ## Run integration tests excluding slow tests
	python run_integration_tests.py --fast

test-setup: ## Setup integration test environment only
	python run_integration_tests.py --setup-only

test-cleanup: ## Cleanup integration test environment
	python run_integration_tests.py --cleanup-only

test-logs: ## Show logs from integration test services
	python run_integration_tests.py --logs

test-logs-coordinator: ## Show coordinator agent logs from test environment
	python run_integration_tests.py --logs test-coordinator-agent

test-logs-retrieval: ## Show retrieval agent logs from test environment
	python run_integration_tests.py --logs test-retrieval-agent

test-logs-filter: ## Show filter agent logs from test environment
	python run_integration_tests.py --logs test-filter-agent

test-logs-summarise: ## Show summarise agent logs from test environment
	python run_integration_tests.py --logs test-summarise-agent

test-logs-alert: ## Show alert agent logs from test environment
	python run_integration_tests.py --logs test-alert-agent

test-all: ## Run both unit and integration tests
	@echo "Running unit tests..."
	uv run pytest tests/unit/
	@echo "Running integration tests..."
	python run_integration_tests.py

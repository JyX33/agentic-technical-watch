#!/bin/bash
# ABOUTME: Production deployment automation script for Reddit Technical Watcher
# ABOUTME: Handles zero-downtime deployment, database migrations, health checks, and rollback procedures

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="reddit-watcher"
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
BACKUP_DIR="./database_backups"
LOG_FILE="./deployment.log"
HEALTH_CHECK_TIMEOUT=300
ROLLBACK_TIMEOUT=180

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "${LOG_FILE}"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1" | tee -a "${LOG_FILE}"
}

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" | tee -a "${LOG_FILE}"
}

# Error handling
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Deployment failed with exit code $exit_code"
        log "Starting cleanup procedures..."

        # Attempt to restore previous state if deployment failed
        if [ "${DEPLOYMENT_PHASE:-}" = "deployment" ]; then
            log_warning "Deployment phase failed, initiating automatic rollback..."
            rollback_deployment
        fi
    fi
    exit $exit_code
}

trap cleanup EXIT

# Utility functions
check_dependencies() {
    log "Checking deployment dependencies..."

    local missing_deps=()

    command -v docker >/dev/null 2>&1 || missing_deps+=("docker")
    command -v docker-compose >/dev/null 2>&1 || missing_deps+=("docker-compose")
    command -v curl >/dev/null 2>&1 || missing_deps+=("curl")
    command -v jq >/dev/null 2>&1 || missing_deps+=("jq")
    command -v uv >/dev/null 2>&1 || missing_deps+=("uv")

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log "Please install the missing dependencies and try again."
        exit 1
    fi

    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    log_success "All dependencies are available"
}

validate_environment() {
    log "Validating environment configuration..."

    if [ ! -f "${ENV_FILE}" ]; then
        log_error "Environment file ${ENV_FILE} not found"
        log "Please create ${ENV_FILE} with production configuration"
        exit 1
    fi

    # Source environment file
    set -a
    source "${ENV_FILE}"
    set +a

    # Check required environment variables
    local required_vars=(
        "DB_PASSWORD"
        "REDIS_PASSWORD"
        "A2A_API_KEY"
        "REDDIT_CLIENT_ID"
        "REDDIT_CLIENT_SECRET"
        "GEMINI_API_KEY"
        "GRAFANA_ADMIN_PASSWORD"
        "ALERTMANAGER_WEBHOOK_TOKEN"
        "ACME_EMAIL"
    )

    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var:-}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "Missing required environment variables: ${missing_vars[*]}"
        exit 1
    fi

    log_success "Environment validation completed"
}

create_data_directories() {
    log "Creating data directories..."

    local data_dirs=(
        "${DATA_PATH:-./data}/postgres"
        "${DATA_PATH:-./data}/redis"
        "${DATA_PATH:-./data}/prometheus"
        "${DATA_PATH:-./data}/grafana"
        "${DATA_PATH:-./data}/alertmanager"
        "${DATA_PATH:-./data}/traefik"
        "${BACKUP_DIR}"
    )

    for dir in "${data_dirs[@]}"; do
        mkdir -p "$dir"
        # Set appropriate permissions
        if [[ "$dir" == *"postgres"* ]]; then
            chmod 700 "$dir"
        elif [[ "$dir" == *"grafana"* ]]; then
            chmod 755 "$dir"
            # Grafana runs as user 472
            chown -R 472:472 "$dir" 2>/dev/null || log_warning "Could not set grafana ownership for $dir"
        else
            chmod 755 "$dir"
        fi
    done

    log_success "Data directories created"
}

backup_database() {
    log "Creating database backup..."

    local backup_timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_file="${BACKUP_DIR}/reddit_watcher_backup_${backup_timestamp}.sql"

    # Check if database is running
    if docker-compose -f "${COMPOSE_FILE}" ps db | grep -q "Up"; then
        log "Database is running, creating backup..."

        docker-compose -f "${COMPOSE_FILE}" exec -T db pg_dump \
            -U "${DB_USER:-reddit_watcher_user}" \
            -d "${DB_NAME:-reddit_watcher}" \
            --clean --if-exists --create --verbose \
            > "${backup_file}" 2>>"${LOG_FILE}"

        if [ $? -eq 0 ]; then
            log_success "Database backup created: ${backup_file}"
            # Compress backup
            gzip "${backup_file}"
            log_success "Backup compressed: ${backup_file}.gz"
        else
            log_error "Database backup failed"
            exit 1
        fi
    else
        log_warning "Database is not running, skipping backup"
    fi
}

run_database_migrations() {
    log "Running database migrations..."

    # Wait for database to be ready
    log "Waiting for database to be ready..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "${COMPOSE_FILE}" exec -T db pg_isready \
            -U "${DB_USER:-reddit_watcher_user}" \
            -d "${DB_NAME:-reddit_watcher}" >/dev/null 2>&1; then
            log_success "Database is ready"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            log_error "Database did not become ready within timeout"
            exit 1
        fi

        log "Database not ready, attempt $attempt/$max_attempts"
        sleep 5
        ((attempt++))
    done

    # Run Alembic migrations
    log "Running Alembic migrations..."

    # Create temporary container for migrations
    docker-compose -f "${COMPOSE_FILE}" run --rm \
        -e DATABASE_URL="postgresql://${DB_USER:-reddit_watcher_user}:${DB_PASSWORD}@db:5432/${DB_NAME:-reddit_watcher}" \
        coordinator-agent \
        uv run alembic upgrade head

    if [ $? -eq 0 ]; then
        log_success "Database migrations completed successfully"
    else
        log_error "Database migrations failed"
        exit 1
    fi
}

build_images() {
    log "Building Docker images..."

    # Build images with build args for optimization
    docker-compose -f "${COMPOSE_FILE}" build \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --parallel

    if [ $? -eq 0 ]; then
        log_success "Docker images built successfully"
    else
        log_error "Docker image build failed"
        exit 1
    fi
}

start_infrastructure() {
    log "Starting infrastructure services..."

    # Start database and Redis first
    docker-compose -f "${COMPOSE_FILE}" up -d db redis

    # Wait for infrastructure to be healthy
    log "Waiting for infrastructure services to be healthy..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        local db_healthy=$(docker-compose -f "${COMPOSE_FILE}" ps -q db | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null)
        local redis_healthy=$(docker-compose -f "${COMPOSE_FILE}" ps -q redis | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null)

        if [ "$db_healthy" = "healthy" ] && [ "$redis_healthy" = "healthy" ]; then
            log_success "Infrastructure services are healthy"
            break
        fi

        if [ $attempt -eq $max_attempts ]; then
            log_error "Infrastructure services did not become healthy within timeout"
            exit 1
        fi

        log "Infrastructure not ready, attempt $attempt/$max_attempts (DB: $db_healthy, Redis: $redis_healthy)"
        sleep 10
        ((attempt++))
    done
}

deploy_agents() {
    log "Deploying agent services..."

    DEPLOYMENT_PHASE="deployment"

    # Deploy agents in dependency order
    local agents=("retrieval-agent" "filter-agent" "summarise-agent" "alert-agent" "coordinator-agent")

    for agent in "${agents[@]}"; do
        log "Deploying $agent..."

        # Start the agent
        docker-compose -f "${COMPOSE_FILE}" up -d "$agent"

        # Wait for agent to be healthy
        wait_for_service_health "$agent" 60

        log_success "$agent deployed successfully"
    done

    log_success "All agents deployed successfully"
}

deploy_monitoring() {
    log "Deploying monitoring stack..."

    # Deploy monitoring services
    local monitoring_services=("prometheus" "grafana" "alertmanager" "node-exporter")

    for service in "${monitoring_services[@]}"; do
        log "Deploying $service..."
        docker-compose -f "${COMPOSE_FILE}" up -d "$service"
        sleep 5
    done

    # Deploy Traefik last for load balancing
    log "Deploying Traefik reverse proxy..."
    docker-compose -f "${COMPOSE_FILE}" up -d traefik

    log_success "Monitoring stack deployed successfully"
}

wait_for_service_health() {
    local service_name="$1"
    local timeout="${2:-60}"
    local attempt=1
    local max_attempts=$((timeout / 5))

    log "Waiting for $service_name to be healthy..."

    while [ $attempt -le $max_attempts ]; do
        local health_status=$(docker-compose -f "${COMPOSE_FILE}" ps -q "$service_name" | xargs docker inspect --format='{{.State.Health.Status}}' 2>/dev/null)

        if [ "$health_status" = "healthy" ]; then
            log_success "$service_name is healthy"
            return 0
        fi

        if [ $attempt -eq $max_attempts ]; then
            log_error "$service_name did not become healthy within timeout ($timeout seconds)"
            return 1
        fi

        log "$service_name health status: $health_status (attempt $attempt/$max_attempts)"
        sleep 5
        ((attempt++))
    done
}

validate_deployment() {
    log "Validating deployment..."

    # Check all services are running
    local services=("db" "redis" "coordinator-agent" "retrieval-agent" "filter-agent" "summarise-agent" "alert-agent" "prometheus" "grafana" "alertmanager")
    local failed_services=()

    for service in "${services[@]}"; do
        local status=$(docker-compose -f "${COMPOSE_FILE}" ps -q "$service" | xargs docker inspect --format='{{.State.Status}}' 2>/dev/null)
        if [ "$status" != "running" ]; then
            failed_services+=("$service")
        fi
    done

    if [ ${#failed_services[@]} -ne 0 ]; then
        log_error "Some services are not running: ${failed_services[*]}"
        return 1
    fi

    # Test health endpoints
    log "Testing service health endpoints..."
    local health_endpoints=(
        "http://localhost:${COORDINATOR_PORT:-8000}/health"
        "http://localhost:${RETRIEVAL_PORT:-8001}/health"
        "http://localhost:${FILTER_PORT:-8002}/health"
        "http://localhost:${SUMMARISE_PORT:-8003}/health"
        "http://localhost:${ALERT_PORT:-8004}/health"
        "http://localhost:${PROMETHEUS_PORT:-9090}/-/healthy"
        "http://localhost:${GRAFANA_PORT:-3000}/api/health"
    )

    local failed_endpoints=()
    for endpoint in "${health_endpoints[@]}"; do
        if ! curl -f -s --max-time 10 "$endpoint" >/dev/null 2>&1; then
            failed_endpoints+=("$endpoint")
        fi
    done

    if [ ${#failed_endpoints[@]} -ne 0 ]; then
        log_error "Some health endpoints are not responding: ${failed_endpoints[*]}"
        return 1
    fi

    # Test A2A communication
    log "Testing A2A communication..."
    local coordinator_url="http://localhost:${COORDINATOR_PORT:-8000}"

    # Test agent card endpoint
    if ! curl -f -s --max-time 10 "$coordinator_url/.well-known/agent.json" | jq -e '.name' >/dev/null 2>&1; then
        log_error "Coordinator agent card endpoint is not responding properly"
        return 1
    fi

    # Test service discovery
    if ! curl -f -s --max-time 10 "$coordinator_url/discover" | jq -e '.agents' >/dev/null 2>&1; then
        log_error "Service discovery endpoint is not responding properly"
        return 1
    fi

    log_success "Deployment validation completed successfully"
    return 0
}

rollback_deployment() {
    log "Initiating deployment rollback..."

    # Stop current services
    log "Stopping current services..."
    docker-compose -f "${COMPOSE_FILE}" down --remove-orphans

    # Restore database backup if available
    local latest_backup=$(ls -t "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | head -n1)
    if [ -n "$latest_backup" ]; then
        log "Restoring database from backup: $latest_backup"

        # Start only database for restore
        docker-compose -f "${COMPOSE_FILE}" up -d db

        # Wait for database
        sleep 30

        # Restore backup
        gunzip -c "$latest_backup" | docker-compose -f "${COMPOSE_FILE}" exec -T db psql \
            -U "${DB_USER:-reddit_watcher_user}" \
            -d postgres

        log_success "Database restored from backup"
    else
        log_warning "No database backup available for rollback"
    fi

    # Restart previous version (this would typically involve git checkout to previous tag)
    log "Restarting services with previous configuration..."
    docker-compose -f "${COMPOSE_FILE}" up -d

    # Wait for services to be healthy
    sleep 60

    if validate_deployment; then
        log_success "Rollback completed successfully"
    else
        log_error "Rollback validation failed"
        exit 1
    fi
}

cleanup_old_resources() {
    log "Cleaning up old Docker resources..."

    # Remove unused images
    docker image prune -f --filter "until=24h"

    # Remove unused volumes (be careful here)
    docker volume prune -f --filter "label!=keep"

    # Remove old backups (keep last 10)
    if [ -d "${BACKUP_DIR}" ]; then
        ls -t "${BACKUP_DIR}"/*.sql.gz 2>/dev/null | tail -n +11 | xargs rm -f
    fi

    log_success "Cleanup completed"
}

display_deployment_info() {
    log_success "=== DEPLOYMENT COMPLETED SUCCESSFULLY ==="
    log ""
    log "Service URLs:"
    log "  Coordinator Agent: http://localhost:${COORDINATOR_PORT:-8000}"
    log "  Grafana Dashboard: http://localhost:${GRAFANA_PORT:-3000}"
    log "  Prometheus: http://localhost:${PROMETHEUS_PORT:-9090}"
    log "  Alertmanager: http://localhost:${ALERTMANAGER_PORT:-9093}"
    log ""
    log "Default Credentials:"
    log "  Grafana: admin / \$GRAFANA_ADMIN_PASSWORD"
    log ""
    log "Health Check URLs:"
    for port in 8000 8001 8002 8003 8004; do
        log "  http://localhost:$port/health"
    done
    log ""
    log "Service Discovery:"
    log "  http://localhost:${COORDINATOR_PORT:-8000}/discover"
    log ""
    log "Logs:"
    log "  docker-compose -f ${COMPOSE_FILE} logs -f [service_name]"
    log ""
    log "To stop all services:"
    log "  docker-compose -f ${COMPOSE_FILE} down"
    log ""
    log_success "=== DEPLOYMENT INFORMATION ==="
}

# Main deployment function
main() {
    local action="${1:-deploy}"

    log "Starting Reddit Technical Watcher production deployment..."
    log "Action: $action"
    log "Timestamp: $(date)"
    log "Script: $0"
    log "Working directory: $(pwd)"

    case "$action" in
        "deploy")
            check_dependencies
            validate_environment
            create_data_directories
            backup_database
            build_images
            start_infrastructure
            run_database_migrations
            deploy_agents
            deploy_monitoring

            if validate_deployment; then
                cleanup_old_resources
                display_deployment_info
                log_success "Production deployment completed successfully!"
            else
                log_error "Deployment validation failed"
                exit 1
            fi
            ;;
        "rollback")
            rollback_deployment
            ;;
        "validate")
            validate_deployment
            ;;
        "backup")
            backup_database
            ;;
        "logs")
            docker-compose -f "${COMPOSE_FILE}" logs -f "${2:-}"
            ;;
        "status")
            docker-compose -f "${COMPOSE_FILE}" ps
            ;;
        "stop")
            log "Stopping all services..."
            docker-compose -f "${COMPOSE_FILE}" down
            log_success "All services stopped"
            ;;
        *)
            echo "Usage: $0 {deploy|rollback|validate|backup|logs|status|stop}"
            echo ""
            echo "Commands:"
            echo "  deploy   - Full production deployment"
            echo "  rollback - Rollback to previous version"
            echo "  validate - Validate current deployment"
            echo "  backup   - Create database backup"
            echo "  logs     - View service logs"
            echo "  status   - Show service status"
            echo "  stop     - Stop all services"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"

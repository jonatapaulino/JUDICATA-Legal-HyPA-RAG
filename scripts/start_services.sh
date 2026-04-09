#!/bin/bash
# Start required services for judicial LLM system
# Usage: sudo ./scripts/start_services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DOCKER_COMPOSE_FILE="$PROJECT_DIR/docker/docker-compose.yml"

echo "Starting Judicial LLM services..."
echo "Project directory: $PROJECT_DIR"

# Start core services
docker compose -f "$DOCKER_COMPOSE_FILE" up -d qdrant neo4j redis

echo ""
echo "Waiting for services to be healthy..."

# Wait for Qdrant
echo -n "Qdrant: "
for i in {1..30}; do
    if curl -s http://localhost:6333/health > /dev/null 2>&1; then
        echo "UP"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for Neo4j
echo -n "Neo4j: "
for i in {1..30}; do
    if curl -s http://localhost:7474 > /dev/null 2>&1; then
        echo "UP"
        break
    fi
    echo -n "."
    sleep 2
done

# Check Redis
echo -n "Redis: "
if redis-cli ping > /dev/null 2>&1; then
    echo "UP"
else
    echo "DOWN"
fi

echo ""
echo "Services started. Run ingestion with:"
echo "  cd $PROJECT_DIR && python scripts/ingest_full_legislation.py --all"

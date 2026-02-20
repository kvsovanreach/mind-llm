#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Rebuild & Restart Platform"
echo "=========================================="
echo ""

# Parse arguments
NO_CACHE=false
SERVICE=""
KEEP_MODELS=false
CLEAR_DATASTORE=false
ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache|-n)
            NO_CACHE=true
            shift
            ;;
        --orchestrator|-o)
            SERVICE="orchestrator"
            shift
            ;;
        --frontend|-f)
            SERVICE="frontend"
            shift
            ;;
        --keep-models|-k)
            KEEP_MODELS=true
            shift
            ;;
        --clear-datastore|-c)
            CLEAR_DATASTORE=true
            shift
            ;;
        --all|-a)
            ALL=true
            NO_CACHE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -n, --no-cache       Build without using cache"
            echo "  -o, --orchestrator   Rebuild only the orchestrator"
            echo "  -f, --frontend       Rebuild only the frontend"
            echo "  -k, --keep-models    Keep running model containers"
            echo "  -c, --clear-datastore Clear Redis data and start fresh"
            echo "  -a, --all            Full rebuild without cache (same as --no-cache)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                   # Rebuild and restart everything"
            echo "  $0 --frontend        # Rebuild only frontend"
            echo "  $0 --no-cache        # Full rebuild without cache"
            echo "  $0 --all             # Full rebuild with all changes applied"
            echo "  $0 --clear-datastore # Clear all data and restart fresh"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check for Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed.${NC}"
    exit 1
fi

# Save running models if needed
RUNNING_MODELS=""
if [ "$KEEP_MODELS" = true ]; then
    echo "Checking for running models..."
    RUNNING_MODELS=$(docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" || true)
    if [ -n "$RUNNING_MODELS" ]; then
        echo -e "${YELLOW}Found running models:${NC}"
        echo "$RUNNING_MODELS"
        echo "These will be preserved during rebuild."
        echo ""
    fi
fi

# Clear datastore if requested
if [ "$CLEAR_DATASTORE" = true ]; then
    echo -e "${YELLOW}Clearing Redis datastore...${NC}"

    # Check if Redis is running and flush it
    if docker ps | grep -q "MIND_REDIS_STORE"; then
        docker exec MIND_REDIS_STORE redis-cli FLUSHALL 2>/dev/null || true
        echo -e "${GREEN}✓ Redis data cleared${NC}"
    fi

    # Also stop all model containers since they won't be in Redis anymore
    echo "Stopping all model containers..."
    docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" | xargs -r docker stop 2>/dev/null || true
    docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" | xargs -r docker rm 2>/dev/null || true

    # Clear the nginx model routes
    echo "Clearing nginx model routes..."
    cat > ./nginx/conf.d/model_routes.conf << EOF
# Auto-generated model routing configuration
# This file will be populated when models are deployed
EOF
    echo -e "${GREEN}✓ All data cleared - starting fresh${NC}"
    echo ""
fi

# Stop services before rebuilding
if [ -n "$SERVICE" ]; then
    echo -e "${BLUE}Stopping $SERVICE...${NC}"
    docker compose stop $SERVICE
else
    echo -e "${BLUE}Stopping all services...${NC}"
    if [ "$KEEP_MODELS" = true ] && [ "$CLEAR_DATASTORE" != true ]; then
        # Stop only platform services, not model containers
        docker compose stop
    else
        # Stop everything including models
        docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" | xargs -r docker stop 2>/dev/null || true
        docker compose stop
    fi
fi

# Build services
BUILD_ARGS=""
if [ "$NO_CACHE" = true ]; then
    BUILD_ARGS="--no-cache"
    echo -e "${YELLOW}Building without cache (this will take longer)...${NC}"
fi

if [ -n "$SERVICE" ]; then
    echo ""
    echo -e "${CYAN}Building $SERVICE...${NC}"
    docker compose build $BUILD_ARGS $SERVICE

    # Special handling for frontend
    if [ "$SERVICE" = "frontend" ]; then
        echo -e "${CYAN}Building frontend assets...${NC}"
        if [ -f "frontend/package.json" ]; then
            cd frontend
            npm install
            npm run build
            cd ..
            echo -e "${GREEN}✓ Frontend assets built${NC}"
        fi
    fi
else
    echo ""
    echo -e "${CYAN}Building all services...${NC}"
    docker compose build $BUILD_ARGS

    # Also build frontend assets if directory exists
    if [ -f "frontend/package.json" ]; then
        echo -e "${CYAN}Building frontend assets...${NC}"
        cd frontend
        npm install
        npm run build
        cd ..
        echo -e "${GREEN}✓ Frontend assets built with latest models.json${NC}"
    fi
fi

# Clean model routes if needed (prevents nginx startup failure)
if [ "$SERVICE" = "nginx" ] || [ -z "$SERVICE" ]; then
    echo "Checking nginx routes..."
    MODEL_ROUTES_FILE="./nginx/conf.d/model_routes.conf"
    RUNNING_MODELS=$(docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" || true)

    if [ -z "$RUNNING_MODELS" ] && [ -f "$MODEL_ROUTES_FILE" ]; then
        echo "No models running, clearing nginx routes..."
        cat > "$MODEL_ROUTES_FILE" << EOF
# Auto-generated model routing configuration
# This file will be populated when models are deployed
EOF
        echo -e "${GREEN}✓ Nginx routes cleaned${NC}"
    fi
fi

# Start services
echo ""
if [ -n "$SERVICE" ]; then
    echo -e "${BLUE}Starting $SERVICE...${NC}"
    docker compose up -d $SERVICE
else
    echo -e "${BLUE}Starting all services...${NC}"
    docker compose up -d
fi

# Wait for services
echo ""
echo "Waiting for services to be ready..."
sleep 8

# Check service health
echo "Checking service status..."
if [ -n "$SERVICE" ]; then
    docker compose ps $SERVICE
else
    docker compose ps
fi

# Sync container state with Redis after rebuild
echo ""
if [ -x "./sync_redis.sh" ]; then
    ./sync_redis.sh
else
    echo -e "${YELLOW}Warning: sync_redis.sh not found or not executable${NC}"
fi

# Ensure configuration changes are applied
echo ""
echo -e "${CYAN}Ensuring all configuration changes are applied...${NC}"

# Check if .env changes need orchestrator restart
if [ "$SERVICE" = "orchestrator" ] || [ -z "$SERVICE" ]; then
    echo "Restarting orchestrator to apply .env changes..."
    docker compose restart orchestrator
    echo -e "${GREEN}✓ Orchestrator restarted with latest .env settings${NC}"
fi

# Update frontend if models.json was changed and not already rebuilt
if [ "$SERVICE" != "frontend" ] && [ -f "frontend/src/models.json" ]; then
    echo "Copying frontend assets to ensure models.json changes are live..."
    if [ -d "frontend/dist" ]; then
        docker cp frontend/dist/. MIND_ADMIN_UI:/usr/share/nginx/html/ 2>/dev/null || true
        echo -e "${GREEN}✓ Frontend updated with latest models.json${NC}"
    fi
fi

# Check if models need attention
if [ "$KEEP_MODELS" = true ] && [ -n "$RUNNING_MODELS" ]; then
    echo ""
    echo "Checking preserved model containers..."
    for model in $RUNNING_MODELS; do
        if docker ps | grep -q "$model"; then
            echo -e "  ${GREEN}✓${NC} $model is still running"
        else
            echo -e "  ${YELLOW}⚠${NC} $model may need to be restarted"
        fi
    done
fi

# Get the machine's IP
IP=$(hostname -I | awk '{print $1}')
if [ -z "$IP" ]; then
    IP="localhost"
fi

echo ""
echo -e "${GREEN}✅ Platform rebuilt and restarted successfully!${NC}"
echo ""
echo "Access Points:"
echo "  📊 Admin Dashboard:  http://$IP:9020"
echo "  🔌 API Endpoint:     http://$IP:9020/api/v1/{model}/"
echo ""

if [ -n "$SERVICE" ]; then
    echo -e "${CYAN}Only $SERVICE was rebuilt and restarted.${NC}"
else
    echo -e "${CYAN}All services were rebuilt and restarted.${NC}"
fi

if [ "$NO_CACHE" = true ]; then
    echo -e "${YELLOW}Built without cache - all images are fresh.${NC}"
fi
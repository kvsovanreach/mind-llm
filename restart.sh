#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Restarting Multi-Model LLM Platform"
echo "=========================================="
echo ""

# Parse arguments
SERVICE=""
QUICK=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --orchestrator|-o)
            SERVICE="orchestrator"
            shift
            ;;
        --frontend|-f)
            SERVICE="frontend"
            shift
            ;;
        --nginx|-n)
            SERVICE="nginx"
            shift
            ;;
        --redis|-r)
            SERVICE="redis"
            shift
            ;;
        --quick|-q)
            QUICK=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS] [SERVICE]"
            echo ""
            echo "Options:"
            echo "  -o, --orchestrator   Restart only the orchestrator service"
            echo "  -f, --frontend       Restart only the frontend service"
            echo "  -n, --nginx          Restart only the nginx service"
            echo "  -r, --redis          Restart only the redis service"
            echo "  -q, --quick          Quick restart (no health checks)"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                   # Restart all services"
            echo "  $0 --orchestrator    # Restart only orchestrator"
            echo "  $0 --quick           # Quick restart all services"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if platform is running
if ! docker compose ps --quiet 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}Platform is not running. Starting it instead...${NC}"
    ./start.sh
    exit 0
fi

# Restart specific service or all
if [ -n "$SERVICE" ]; then
    echo -e "${BLUE}Restarting $SERVICE...${NC}"
    docker compose restart $SERVICE
else
    echo -e "${BLUE}Restarting all platform services...${NC}"

    # Save running model information
    echo "Saving model states..."
    RUNNING_MODELS=$(docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" || true)

    # Restart core services
    docker compose restart

    if [ "$QUICK" != "true" ]; then
        echo ""
        echo "Waiting for services to be ready..."
        sleep 5

        # Check service health
        echo "Checking service status..."
        docker compose ps

        # Sync container state with Redis
        echo ""
        if [ -x "./sync_redis.sh" ]; then
            ./sync_redis.sh
        else
            echo -e "${YELLOW}Warning: sync_redis.sh not found or not executable${NC}"
        fi

        # Check if models are still running
        if [ -n "$RUNNING_MODELS" ]; then
            echo ""
            echo "Checking model containers..."
            for model in $RUNNING_MODELS; do
                if docker ps | grep -q "$model"; then
                    echo -e "  ${GREEN}✓${NC} $model is running"
                else
                    echo -e "  ${RED}✗${NC} $model needs to be redeployed"
                fi
            done
        fi
    fi
fi

# Get the machine's IP
IP=$(hostname -I | awk '{print $1}')
if [ -z "$IP" ]; then
    IP="localhost"
fi

echo ""
echo -e "${GREEN}✅ Platform restarted successfully!${NC}"
echo ""
echo "Access Points:"
echo "  📊 Admin Dashboard:  http://$IP:9020"
echo "  🔌 API Endpoint:     http://$IP:9020/api/v1/{model}/"
echo ""

if [ "$SERVICE" = "orchestrator" ]; then
    echo -e "${YELLOW}Note: Model containers were not affected by orchestrator restart.${NC}"
    echo "They should continue running normally."
fi
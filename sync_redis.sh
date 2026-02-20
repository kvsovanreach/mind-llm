#!/bin/bash

# Sync running model containers with Redis datastore
# This ensures Redis reflects the actual state of containers

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MODELS_JSON="${SCRIPT_DIR}/frontend/src/models.json"
# Fallback to alternate location
if [ ! -f "$MODELS_JSON" ]; then
    MODELS_JSON="${SCRIPT_DIR}/src/models.json"
fi
NGINX_CONF_DIR="${SCRIPT_DIR}/nginx/conf.d"

echo -e "${CYAN}Syncing container state with Redis...${NC}"

# Get all running model containers
RUNNING_MODELS=$(docker ps --format "{{.Names}}" | grep "^MIND_MODEL_" || true)

if [ -z "$RUNNING_MODELS" ]; then
    echo "No model containers currently running"

    # Clear any stale entries in Redis
    docker exec MIND_REDIS_STORE redis-cli --scan --pattern "model:*" | while read key; do
        docker exec MIND_REDIS_STORE redis-cli DEL "$key" > /dev/null
    done
    echo -e "${GREEN}✓ Redis cleaned of stale entries${NC}"
else
    echo "Found running model containers:"

    # Process each running container
    for container in $RUNNING_MODELS; do
        # Extract model abbreviation from container name (MIND_MODEL_qwen1.5b -> qwen1.5b)
        MODEL_ABBR=${container#MIND_MODEL_}

        # Get container details
        CONTAINER_INFO=$(docker inspect "$container" 2>/dev/null)

        if [ $? -eq 0 ]; then
            # Extract GPU assignment
            GPU_DEVICE=$(echo "$CONTAINER_INFO" | python3 -c "
import json, sys
data = json.load(sys.stdin)[0]
env_vars = data.get('Config', {}).get('Env', [])
for var in env_vars:
    if var.startswith('CUDA_VISIBLE_DEVICES='):
        print(var.split('=', 1)[1])
        break
else:
    print('0')  # Default to GPU 0 if not specified
" 2>/dev/null || echo "0")

            # Get container status
            STATUS=$(docker inspect "$container" --format '{{.State.Status}}' 2>/dev/null)

            if [ "$STATUS" = "running" ]; then
                echo -e "  ${GREEN}✓${NC} $container (GPU: $GPU_DEVICE)"

                # Extract model name and type from container command
                MODEL_NAME=$(docker inspect "$container" 2>/dev/null | python3 -c "
import json, sys
data = json.load(sys.stdin)[0]
args = data.get('Args', [])
for i, arg in enumerate(args):
    if arg == '--model' and i+1 < len(args):
        print(args[i+1])
        break
" 2>/dev/null)

                # Always look up model details from models.json
                if [ -f "$MODELS_JSON" ]; then
                    MODEL_INFO=$(python3 -c "
import json
import sys
with open('$MODELS_JSON', 'r') as f:
    config = json.load(f)
    for model in config.get('predefined_models', []):
        if model['abbr'] == '$MODEL_ABBR':
            # Use name from container if available, otherwise from models.json
            name = '$MODEL_NAME' if '$MODEL_NAME' else model['name']
            print(f\"{name}|{model['type']}\")
            sys.exit(0)
        # Also check by model name if abbreviation doesn't match
        elif '$MODEL_NAME' and model['name'] == '$MODEL_NAME':
            print(f\"{model['name']}|{model['type']}\")
            sys.exit(0)
# Model not found in models.json
print('$MODEL_NAME|unknown')
" 2>/dev/null)
                    MODEL_NAME=$(echo "$MODEL_INFO" | cut -d'|' -f1)
                    MODEL_TYPE=$(echo "$MODEL_INFO" | cut -d'|' -f2)

                    # If model not found in models.json, skip it
                    if [ "$MODEL_TYPE" = "unknown" ]; then
                        echo -e "  ${YELLOW}⚠${NC} Model $MODEL_ABBR not found in models.json, skipping type update"
                        continue
                    fi
                else
                    echo -e "  ${RED}✗${NC} models.json not found at $MODELS_JSON"
                    echo "     Cannot determine model type for $MODEL_ABBR"
                    continue
                fi

                # Get container port (usually 8000 for vLLM)
                CONTAINER_PORT="8000"

                # Update Redis with container info
                docker exec MIND_REDIS_STORE redis-cli HSET "model:$MODEL_ABBR" \
                    "abbr" "$MODEL_ABBR" \
                    "name" "$MODEL_NAME" \
                    "type" "$MODEL_TYPE" \
                    "status" "running" \
                    "container_name" "$container" \
                    "container_id" "$container" \
                    "gpu_device" "$GPU_DEVICE" \
                    "port" "$CONTAINER_PORT" \
                    "endpoint" "/api/v1/$MODEL_ABBR" > /dev/null 2>&1

                # Also set GPU assignment
                docker exec MIND_REDIS_STORE redis-cli SET "gpu_assignment:$MODEL_ABBR" "$GPU_DEVICE" > /dev/null 2>&1
            else
                echo -e "  ${YELLOW}⚠${NC} $container is $STATUS"
            fi
        else
            echo -e "  ${RED}✗${NC} Could not inspect $container"
        fi
    done

    # Remove Redis entries for non-running containers
    echo ""
    echo "Cleaning stale Redis entries..."

    docker exec MIND_REDIS_STORE redis-cli --scan --pattern "model:*" 2>/dev/null | while read key; do
        MODEL_ABBR=${key#model:}
        CONTAINER_NAME="MIND_MODEL_$MODEL_ABBR"

        # Check if this container is actually running
        if ! echo "$RUNNING_MODELS" | grep -q "^$CONTAINER_NAME$"; then
            docker exec MIND_REDIS_STORE redis-cli DEL "$key" > /dev/null 2>&1
            docker exec MIND_REDIS_STORE redis-cli DEL "gpu_assignment:$MODEL_ABBR" > /dev/null 2>&1
            echo -e "  ${YELLOW}Removed stale entry:${NC} $MODEL_ABBR"
        fi
    done

    echo -e "${GREEN}✓ Redis synchronized with container state${NC}"

    # Regenerate nginx routes for running models
    echo ""
    echo "Regenerating nginx routes..."

    # Trigger route regeneration through orchestrator API
    if curl -s http://localhost:8001/health >/dev/null 2>&1; then
        # Try to trigger update-nginx-routes endpoint if it exists
        # For now, manually generate the routes
        cat > "${NGINX_CONF_DIR}/model_routes.conf" << 'NGINX_EOF'

# Auto-generated model routing configuration
NGINX_EOF

        for container in $RUNNING_MODELS; do
            MODEL_ABBR=${container#MIND_MODEL_}

            # Check if this is an embedding model
            MODEL_TYPE=$(docker exec MIND_REDIS_STORE redis-cli HGET "model:$MODEL_ABBR" "type" 2>/dev/null)

            cat >> "${NGINX_CONF_DIR}/model_routes.conf" << NGINX_EOF

# Model: $MODEL_ABBR (OpenAI-compatible API)

# Route chat/completions through orchestrator for smart context management
location = /api/v1/$MODEL_ABBR/chat/completions {
    proxy_pass http://orchestrator/api/v1/$MODEL_ABBR/chat/completions;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

    # CORS headers for browser access
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key' always;

    # Handle preflight requests
    if (\$request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }

    # SSE support for streaming
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}

# Route all other endpoints directly to model
location /api/v1/$MODEL_ABBR/ {
    proxy_pass http://$container:8000/v1/;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

    # CORS headers for browser access
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key' always;

    # Handle preflight requests
    if (\$request_method = 'OPTIONS') {
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type, X-API-Key';
        add_header 'Access-Control-Max-Age' 1728000;
        add_header 'Content-Type' 'text/plain; charset=utf-8';
        add_header 'Content-Length' 0;
        return 204;
    }

    # SSE support for streaming
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
}
NGINX_EOF
        done

        # Reload nginx if routes were generated
        if [ -n "$RUNNING_MODELS" ]; then
            docker exec MIND_API_GATEWAY nginx -s reload 2>/dev/null && \
                echo -e "${GREEN}✓ Nginx routes regenerated${NC}" || \
                echo -e "${YELLOW}⚠ Could not reload nginx${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Orchestrator not available, skipping route generation${NC}"
    fi
fi

# Verify sync by showing Redis state
echo ""
echo "Current Redis state:"
MODEL_COUNT=$(docker exec MIND_REDIS_STORE redis-cli --scan --pattern "model:*" | wc -l)

if [ "$MODEL_COUNT" -gt 0 ]; then
    docker exec MIND_REDIS_STORE redis-cli --scan --pattern "model:*" | while read key; do
        MODEL_ABBR=${key#model:}
        STATUS=$(docker exec MIND_REDIS_STORE redis-cli HGET "$key" "status" 2>/dev/null)
        GPU=$(docker exec MIND_REDIS_STORE redis-cli HGET "$key" "gpu_device" 2>/dev/null)
        echo -e "  ${CYAN}$MODEL_ABBR${NC}: status=$STATUS, gpu=$GPU"
    done
else
    echo "  No models in Redis"
fi

echo ""
echo -e "${GREEN}✅ Sync complete${NC}"
#!/bin/bash
# Privileged Music Player Service Restart Helper
# This script is called by the web process (via sudo) to restart systemd services
# Usage: ./music-player-restart.sh [restart|status|check-health]

set -e

ACTION="${1:-status}"
SERVICE_NAME="music-player"
TIMEOUT=30
HEALTH_CHECK_URL="http://localhost:5000/api/health"

restart_service() {
    echo "Restarting $SERVICE_NAME service..."
    systemctl restart "$SERVICE_NAME" || {
        echo "ERROR: Failed to restart $SERVICE_NAME"
        return 1
    }
    echo "✓ Service restart issued"
}

check_service_status() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "✓ Service is running"
        return 0
    else
        echo "✗ Service is not running"
        return 1
    fi
}

check_service_health() {
    echo "Checking service health (timeout: ${TIMEOUT}s)..."
    
    local elapsed=0
    while [ $elapsed -lt $TIMEOUT ]; do
        if curl -s -f "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
            echo "✓ Health check passed"
            return 0
        fi
        
        elapsed=$((elapsed + 1))
        sleep 1
    done
    
    echo "✗ Health check timed out or failed"
    return 1
}

case "$ACTION" in
    restart)
        restart_service
        ;;
    status)
        check_service_status
        ;;
    check-health)
        # Give service time to start before checking
        sleep 2
        check_service_health
        ;;
    *)
        echo "Usage: $0 [restart|status|check-health]"
        exit 1
        ;;
esac

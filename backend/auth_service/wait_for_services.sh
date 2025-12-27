#!/bin/sh

WAIT_FOR=${WAIT_FOR:-http://db_ops:8001/health}
WAIT_TIMEOUT=${WAIT_TIMEOUT:-60}

echo "Waiting for $WAIT_FOR (timeout ${WAIT_TIMEOUT}s)"

counter=0
while [ $counter -lt $WAIT_TIMEOUT ]; do
    if curl -f "$WAIT_FOR" >/dev/null 2>&1; then
        echo "Service $WAIT_FOR is available"
        break
    fi
    echo "Waiting for service... ($counter/$WAIT_TIMEOUT)"
    counter=$((counter + 2))
    sleep 2
done

if [ $counter -ge $WAIT_TIMEOUT ]; then
    echo "Timeout waiting for $WAIT_FOR, continuing anyway"
fi

echo "Starting auth service..."
exec "$@"

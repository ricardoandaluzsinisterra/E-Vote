#!/bin/sh
set -eu

# Wait-for script for auth service. Uses Python's urllib to hit an HTTP health endpoint.
# Environment:
#  WAIT_FOR - full URL to poll (default: http://db_ops:8001/health)
#  WAIT_TIMEOUT - seconds to wait before giving up (default: 60)

WAIT_FOR=${WAIT_FOR:-http://db_ops:8001/health}
WAIT_TIMEOUT=${WAIT_TIMEOUT:-60}

echo "wait-for: waiting for ${WAIT_FOR} (timeout ${WAIT_TIMEOUT}s)"

# Use POSIX-compatible time arithmetic (date +%s) instead of Bash-only SECONDS
end=$(( $(date +%s) + WAIT_TIMEOUT ))
while [ $(date +%s) -lt $end ]; do
  # Run a tiny Python check; shell will expand $WAIT_FOR into the heredoc
  python - <<PY >/dev/null 2>&1
import urllib.request, sys
try:
    with urllib.request.urlopen("${WAIT_FOR}", timeout=3) as r:
        if r.status == 200:
            sys.exit(0)
except Exception:
    sys.exit(1)
PY
  status=$?
  if [ "$status" -eq 0 ]; then
    echo "wait-for: ${WAIT_FOR} is available"
    exec "$@"
  fi
  sleep 2
done


echo "wait-for: timeout waiting for ${WAIT_FOR} after ${WAIT_TIMEOUT}s, continuing to start service" >&2
exec "$@"

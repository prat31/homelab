#!/bin/sh
echo "Adding homelab CA to trusted certificates..."
update-ca-certificates --fresh 2>/dev/null || true
echo "Done."

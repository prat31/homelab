#!/bin/sh
set -e

# ---------------------------------------------------------------------------
# Kopia entrypoint
# - Connects to (or creates) the Cloudflare R2 (S3-compatible) repository.
# - Configures a global daily snapshot schedule + sensible retention.
# - Configures the /data source to snapshot daily.
# - Starts the KopiaUI server (web UI + built-in scheduler).
#
# All operations are idempotent: safe to re-run on every container start.
# ---------------------------------------------------------------------------

CONFIG_FILE="/app/config/repository.config"

# Make the repository password available to every kopia subcommand
# (policy set, snapshot, server start) so none of them prompt interactively.
export KOPIA_PASSWORD="${KOPIA_REPOSITORY_PASSWORD}"

echo "[kopia-entrypoint] Ensuring repository connection to R2..."

# Try to connect to an existing repository first. If that fails (repo not yet
# created), create it. Both use the same encryption password.
if ! kopia repository connect s3 \
      --bucket="${KOPIA_R2_BUCKET}" \
      --endpoint="${KOPIA_R2_ENDPOINT}" \
      --access-key="${KOPIA_R2_ACCESS_KEY_ID}" \
      --secret-access-key="${KOPIA_R2_SECRET_ACCESS_KEY}" \
      --password="${KOPIA_REPOSITORY_PASSWORD}" \
      --config-file="${CONFIG_FILE}" 2>/dev/null; then
  echo "[kopia-entrypoint] No existing repository found, creating a new one..."
  kopia repository create s3 \
      --bucket="${KOPIA_R2_BUCKET}" \
      --endpoint="${KOPIA_R2_ENDPOINT}" \
      --access-key="${KOPIA_R2_ACCESS_KEY_ID}" \
      --secret-access-key="${KOPIA_R2_SECRET_ACCESS_KEY}" \
      --password="${KOPIA_REPOSITORY_PASSWORD}" \
      --config-file="${CONFIG_FILE}"
else
  echo "[kopia-entrypoint] Connected to existing repository."
fi

# ---------------------------------------------------------------------------
# Global policy: daily schedule at 03:00 + retention.
# ---------------------------------------------------------------------------
echo "[kopia-entrypoint] Applying global daily snapshot policy..."
kopia policy set --global \
  --snapshot-time=03:00 \
  --keep-latest=7 \
  --keep-daily=14 \
  --keep-weekly=8 \
  --keep-monthly=12 \
  --keep-annual=3 \
  --config-file="${CONFIG_FILE}"

# ---------------------------------------------------------------------------
# Per-source policy for /data so it runs on the daily schedule.
# Exclude the media/ folder (large, reproducible media files not worth backing
# up to R2). Uses --set-ignore so this is idempotent on every container start.
# ---------------------------------------------------------------------------
echo "[kopia-entrypoint] Applying /data source policy (excluding media/)..."
# Set schedule + clear ignores first, then add the media/ exclusion in a
# separate call (clear and add in the same command don't compose).
kopia policy set /data \
  --snapshot-time=03:00 \
  --clear-ignore \
  --config-file="${CONFIG_FILE}"
kopia policy set /data \
  --add-ignore="media/" \
  --config-file="${CONFIG_FILE}"

echo "[kopia-entrypoint] Starting KopiaUI server..."
# TLS is terminated by Traefik, so run the server over plain HTTP (--insecure).
# The web UI is protected by HTTP basic auth using the server credentials.
exec kopia server start \
  --config-file="${CONFIG_FILE}" \
  --address=0.0.0.0:51515 \
  --insecure \
  --server-username="${KOPIA_SERVER_USERNAME}" \
  --server-password="${KOPIA_SERVER_PASSWORD}"

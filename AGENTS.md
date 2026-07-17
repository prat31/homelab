# Homelab Setup Rules

When adding a new service, follow these conventions strictly:

## 1. Environment Variables
- All API keys, passwords, tokens, and configurable values go in `.env` at repo root.
- Every key in `.env` MUST also exist in `.env.example` (with placeholder values).
- `.env` is in `.gitignore` — never commit it.
- Services read env vars via Docker Compose `environment:` or `env_file:`.

## 2. Dockerization
- Every service runs in a container.
- Use official images where possible.
- Pin versions, never use `:latest`.

## 3. Service Directory Structure
```
services/<service-name>/
├── Dockerfile              # (optional, only if custom build needed)
├── config/                 # config files mounted into container
│   └── ...
└── (any service-specific files)
```

## 4. Global Docker Compose
- A single `docker-compose.yml` at repo root.
- Every service gets a top-level `services:` entry.
- Run everything with: `docker compose up -d`
- Container names follow the pattern `homelab-<service>`.
- If a service has a dependent service (e.g., Redis for an app), name it `homelab-<app>-<dependency>` (e.g., `homelab-myapp-redis`).

## 5. Persistent Data
```
data/<service-name>/
└── .gitkeep
```
- Mount `./data/<service-name>/` into the container for any persistent storage.
- All DB data, uploads, certs, logs, etc. go here.
- Never store persistent data inside the container.

## 6. Shared Dependencies (DBs, Queues, etc.)
- Before adding a DB (Postgres, Redis, etc.), check if one is already deployed.
- If a compatible instance exists, reuse it (add a new database/namespace).
- Document shared services in this file.

### Currently Deployed Shared Services
- **Gluetun** (`homelab-gluetun`) — VPN tunnel via PIA, exposes HTTP proxy at `homelab-gluetun:8888`. Used by qBittorrent (network mode) and Prowlarr (HTTP proxy for indexer queries).
- **Uptime Kuma** (`homelab-uptime-kuma`) — Service monitoring at `https://uptime.homelab.pratcode.dev`. Every publicly-accessible service must have an HTTP monitor added. Credentials in `.env` (`UPTIME_KUMA_USERNAME`, `UPTIME_KUMA_PASSWORD`, `UPTIME_KUMA_API_KEY`).

## 7. Service Integrations
- When adding a new service, configure all possible integrations with existing services automatically (e.g., Traefik labels, DB connections, monitoring).
- **Always try to integrate programmatically first** — investigate all available options (env vars, config files, APIs, DB queries, CLI commands) to wire up integrations without manual steps.
- Only if programmatic integration is impossible (no supported API, env var, or config hook), ask the user to complete it manually and provide exact step-by-step instructions.
- Suggest additional integrations that couldn't be automated.

## 8. Networking
- All services join the `homelab` Docker network (defined in root `docker-compose.yml`).
- Traefik auto-discovers services on this network.
- Services reach each other by container name on the `homelab` network.

## 9. Domain Convention
- Every publicly-accessible service is available at `https://<service>.homelab.pratcode.dev`.
- Traefik labels handle routing and TLS.
- Internal/backend services don't need domain labels.

## 10. Adding a Service Checklist
When asked to add a new service:
1. Check if `.env.example` needs new keys — add them if so. Also, just add the key in `.env`, user will add the value.
2. Create `services/<name>/` with config files.
3. Add service definition to root `docker-compose.yml`.
4. Create `data/<name>/` with `.gitkeep` if persistent storage needed.
5. Add Traefik labels for public services (`Host(<service>.homelab.pratcode.dev)`).
6. Reuse any existing shared DB/queue services instead of creating new ones.
7. Add Traefik middleware labels for auth if needed.
8. Wire up integrations programmatically (env vars, config files, APIs, DB queries — exhaust all options before asking the user).
9. **Add an Uptime Kuma HTTP monitor** for the service (see section 12).
10. Suggest remaining manual steps to the user.

## 11. Git
- Never commit. Ever.

## 12. Uptime Kuma Monitors
- **Every publicly-accessible service** at `https://<service>.homelab.pratcode.dev` must have an HTTP monitor in Uptime Kuma.
- Uptime Kuma stores data in SQLite at `./data/uptime-kuma/kuma.db`.
- To add a monitor programmatically, insert directly into the `monitor` table:
  ```sql
  INSERT INTO monitor (name, type, url, interval, active, user_id)
  VALUES ('Service Name', 'http', 'https://<service>.homelab.pratcode.dev', 60, 1, 1);
  ```
- For services behind basic auth (e.g., Traefik dashboard), set `accepted_statuscodes_json` to include 401:
  ```sql
  UPDATE monitor SET accepted_statuscodes_json = '["401","200-299"]' WHERE name = 'Service Name';
  ```
- Restart the Uptime Kuma container after DB changes: `docker compose restart uptime-kuma`

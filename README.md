# Homelab

Docker Compose configurations for my homelab running on Mac Mini M4 (ARM64).

## Structure

```
homelab/
├── .env                    # Secrets (not committed)
├── .env.example            # Example secrets template
├── docker-compose.yml      # Master compose (includes all modules)
├── networking/             # Traefik reverse proxy
│   ├── docker-compose.yml
│   └── traefik/
│       ├── traefik.yml     # Static configuration
│       └── dynamic/        # Dynamic configuration
├── monitoring/             # Prometheus + Grafana stack
│   ├── docker-compose.yml
│   ├── prometheus/
│   └── grafana/
└── scripts/                # Setup scripts
    └── install-node-exporter.sh
```

## Quick Start

### 1. Configure Secrets

```bash
cp .env.example .env
# Edit .env with your actual values
```

Required variables for Traefik:
- `DOMAIN_BASE` - Your base domain (e.g., `homelab.pratcode.dev`)
- `ACME_EMAIL` - Email for Let's Encrypt notifications
- `CLOUDFLARE_EMAIL` - Your Cloudflare account email
- `CLOUDFLARE_DNS_API_TOKEN` - API token with Zone:DNS:Edit permission
- `TRAEFIK_DASHBOARD_AUTH` - Basic auth for Traefik dashboard

### 2. Install Node Exporter (Native)

Node Exporter runs natively on macOS for better hardware metrics access. Docker on Mac runs a lightweight Linux VM. If node-exporter is run in docker, it will expose metrics of the VM and not the Mac.

```bash
chmod +x scripts/install-node-exporter.sh
./scripts/install-node-exporter.sh
```

Verify it's running:
```bash
curl http://localhost:9100/metrics | head
```

### 3. Start All Services

```bash
# From repo root - starts all modules
docker compose up -d

# Or start a specific module only
cd monitoring && docker compose up -d
```

### 4. Access Services

All services are accessible via HTTPS through Traefik with automatic Let's Encrypt certificates.

| Service    | URL                                      | Credentials         |
|------------|------------------------------------------|---------------------|
| Traefik    | https://traefik.homelab.pratcode.dev     | See TRAEFIK_DASHBOARD_AUTH |
| Grafana    | https://grafana.homelab.pratcode.dev     | See .env file       |
| Prometheus | https://prometheus.homelab.pratcode.dev  | -                   |

## Services

### Networking (`networking/`)

- **Traefik**: Reverse proxy with automatic TLS via Let's Encrypt
  - Wildcard certificate for `*.homelab.pratcode.dev`
  - Cloudflare DNS challenge for certificate validation
  - Label-based service discovery
  - HTTP to HTTPS redirect

### Monitoring (`monitoring/`)

- **Prometheus**: Metrics collection and storage (30-day retention)
- **Grafana**: Metrics visualization with auto-provisioned Prometheus datasource
- **Node Exporter**: System metrics (runs natively, not in Docker)

#### Recommended Grafana Dashboards

Import these from [grafana.com/dashboards](https://grafana.com/grafana/dashboards/):
- Node Exporter Full: ID `1860`

## Architecture Notes

- All Docker images use `platform: linux/arm64` for Apple Silicon
- All containers share a single `homelab` network
- Traefik handles TLS termination and routing via container labels
- Node Exporter runs natively for full hardware access
- Prometheus connects to Node Exporter via `host.docker.internal`
- Named volumes for data persistence

## Adding New Services

1. Create a new directory with its own `docker-compose.yml`
2. Connect to the `homelab` network (external)
3. Add Traefik labels for automatic discovery:

```yaml
services:
  myservice:
    image: myimage:latest
    networks:
      - homelab
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.myservice.rule=Host(`myservice.${DOMAIN_BASE}`)"
      - "traefik.http.routers.myservice.entrypoints=websecure"
      - "traefik.http.routers.myservice.tls=true"
      - "traefik.http.routers.myservice.tls.certresolver=letsencrypt"
      - "traefik.http.services.myservice.loadbalancer.server.port=8080"

networks:
  homelab:
    external: true
```

4. Include in root `docker-compose.yml`
5. Add any secrets to `.env` and `.env.example`

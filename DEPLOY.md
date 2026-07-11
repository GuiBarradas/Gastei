# Deploy — Fly.io (free tier)

Guide for deploying Gastei on Fly.io for free (up to ~3 small apps, plenty for this).

## Why Fly.io

- Generous free tier (3 `shared-cpu-1x` VMs, 256MB RAM each — fits api+streamlit)
- Native Docker support, no buildpack needed
- **Persistent volumes** (SQLite survives deploys)
- BR region available (`gru` — Guarulhos)
- No card needed to start (free trial; free tier afterwards)

## Prerequisites

```bash
# Install flyctl
# Windows (PowerShell):
iwr https://fly.io/install.ps1 -useb | iex

# Login (opens browser)
fly auth login
```

## 1. Initialize the app

From the repo root:

```bash
fly launch --no-deploy --copy-config --name gastei-api
```

When prompted:
- **Region**: `gru` (Guarulhos)
- **Postgres/Redis**: `No` (we use SQLite via volume)
- **Deploy now**: `No`

This generates `fly.toml`. Edit it to point to the `Dockerfile`.

## 2. Recommended `fly.toml`

Replace the generated one with:

```toml
app = "gastei-api"          # must be globally unique — pick another name
primary_region = "gru"

[build]
  dockerfile = "Dockerfile"

[env]
  APP_ENV = "production"
  DATABASE_URL = "sqlite:////data/gastei.db"   # volume mounted at /data
  ENABLE_SCHEDULER = "true"
  SYNC_INTERVAL_HOURS = "6"

[[mounts]]
  source = "gastei_data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0   # save credits: VM sleeps when nobody uses it

  [http_service.concurrency]
    type = "requests"
    soft_limit = 20
    hard_limit = 30

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

## 3. Create volume and secrets

```bash
# SQLite volume (1 GB free)
fly volumes create gastei_data --region gru --size 1

# Secrets (NEVER commit these — Fly encrypts them)
fly secrets set \
  LLM_PROVIDER=gemini \
  GOOGLE_API_KEY=AIza... \
  SECRET_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Optional: Pluggy
fly secrets set \
  PLUGGY_CLIENT_ID=... \
  PLUGGY_CLIENT_SECRET=...
```

## 4. Deploy

```bash
fly deploy
```

Tail the logs:

```bash
fly logs
```

Once you see `Uvicorn running on http://0.0.0.0:8000`, open the app:

```bash
fly open
```

## 5. Streamlit (second app)

Streamlit runs on a 2nd VM (same Dockerfile, different command). Create another `fly.toml`:

```bash
mkdir gastei-ui
cd gastei-ui
```

Create `gastei-ui/fly.toml`:

```toml
app = "gastei-ui"
primary_region = "gru"

[build]
  dockerfile = "../Dockerfile"

[env]
  GASTEI_API_URL = "https://gastei-api.fly.dev"

[processes]
  app = "uv run streamlit run streamlit_app/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true"

[http_service]
  internal_port = 8501
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

Deploy:

```bash
cd gastei-ui
fly deploy
```

Now `https://gastei-ui.fly.dev` is live, hitting the API at the URL configured above.

## 6. Secure access (optional)

Single-user means you should not expose this publicly. Options:

- **Tailscale**: `fly secrets set FLY_PROCESS_GROUP=...` + Tailscale on Fly. Only your own devices can reach it.
- **Cloudflare Tunnel**: zero-trust, free tier.
- **Basic auth**: a small FastAPI middleware that validates an `X-API-Token` header (~10 lines).

## Expected cost

- 2 `shared-cpu-1x 512MB` VMs: within the free tier as long as both auto-sleep (`min_machines_running=0`)
- 1 GB volume: free
- Egress: ~10 GB/month free
- LLM: $0 if Gemini Flash; ~$0.10/month if Anthropic Haiku for personal use

**Total: $0/month** for personal use within the free tier.

## Troubleshooting

**App fails to start:**
```bash
fly logs
fly status
fly ssh console     # SSH into the VM
```

**Volume not mounted:**
```bash
fly volumes list
fly volumes show <id>
```

**Migrations not running:**
```bash
fly ssh console
cd /app && uv run alembic current
```

## Alternatives

- **Railway.app** — similar UX, no permanent free tier (one-time $5 trial)
- **Render** — free tier but sleeps after 15 min, slow restart
- **Hetzner CX11** — €4/month, dedicated VPS, more control
- **Local + Cloudflare Tunnel** — runs on your machine, exposed via free tunnel

# Deploying the School Management System (host-agnostic)

The app ships with a `Dockerfile`, a full `docker-compose.yml`
(Django + PostgreSQL + Caddy with automatic HTTPS) and Cloudflare R2 for
media. The same image runs on a VPS, Fly.io, Koyeb, Render, or Oracle
Cloud — so you are never locked to one host again.

---

## Why not Cloudflare (free tier)?

Cloudflare Workers/Pages run JavaScript/WASM at the edge — **they cannot run
Django, WeasyPrint or PostgreSQL**. What Cloudflare gives you for free and
this project *does* use:

- **R2** for media storage (10 GB free, zero egress) — set `USE_S3=true`.
- **Cloudflare Tunnel** (`cloudflared`) to expose a server running anywhere
  (home PC, school laptop, VPS) with a public HTTPS URL, no open ports.
- DNS / SSL / CDN in front of whatever host you choose.

---

## Option A — Cheap VPS (recommended, ~$5/mo, full control)

Best value and WeasyPrint just works. Two vCPU / 2–4 GB RAM is plenty for
several schools.

| Host | Plan | Price | Notes |
|---|---|---|---|
| **Hetzner** | CX22 (2 vCPU, 4 GB) | ~€4.50/mo | Best price/perf |
| **DigitalOcean** | Basic (2 vCPU, 2 GB) | $6/mo | Accepts PayPal |
| **Contabo** | VPS S (4 GB) | ~$5/mo | Cheap RAM |

Steps on a fresh Ubuntu 22.04/24.04 server:

```bash
curl -fsSL https://get.docker.com | sh

# copy the project onto the server, then:
cp .env.example .env
nano .env        # fill in ALL of these:
#   DJANGO_SECRET_KEY=<long random string>
#   LICENSE_SECRET_KEY=<your production signing key — same one used to
#                       generate product keys, do NOT change once in use>
#   ALLOWED_HOSTS=yourschool.example.com
#   POSTGRES_PASSWORD=<long random string>
#   USE_S3=true  + the AWS_* R2 values
nano Caddyfile   # replace your-school-domain.com with your domain

docker compose up -d --build
```

Point your domain's A record at the server IP first — Caddy fetches the
TLS certificate automatically. Create the platform superuser once:

```bash
docker compose exec web python manage.py createsuperuser
```

Update later with: `git pull && docker compose up -d --build`.

Daily backups: the app already archives to R2 (`USE_S3=true`), and
`docker compose exec web python manage.py create_backup --notes daily`
can be cron-scheduled.

---

## Option B — Oracle Cloud Always Free (genuinely $0)

ARM VM, 4 cores / 24 GB RAM — more than enough, and WeasyPrint runs fine
because you control the OS. Caveats: signup can be finicky (card
verification) and free ARM capacity comes and goes.

1. Create an *Always Free* Ampere A1 instance (Ubuntu 24.04 ARM).
2. Open ports 80/443 in the security list.
3. Follow the exact same Docker steps as Option A.

---

## Option C — Managed Docker hosts (no server admin)

- **Fly.io** — deploy with `fly launch` (it reads the Dockerfile), add
  `fly postgres create`. Usage-based, a few dollars a month at this scale.
  `fly secrets set DJANGO_SECRET_KEY=... LICENSE_SECRET_KEY=... USE_S3=true ...`
- **Koyeb** — free tier includes one small web service; deploy the repo
  (Docker build) and attach a managed Postgres.
- **Render** — Docker web service; note the free tier sleeps and its free
  Postgres is time-limited, so budget ~$7/mo for the smallest paid pair.

For Fly/Koyeb set `PORT` (they inject it) and keep `ALLOWED_HOSTS` at your
`*.fly.dev` / `*.koyeb.app` hostname.

---

## Option D — No cloud at all (the offline/hotspot edition)

The app was designed to run on one school laptop with no internet
(`setup.bat` / `start_server.bat` / `wifi_hotspot.bat`). If you also want
parents or remote staff to reach it, run the laptop as the server and put
**Cloudflare Tunnel** in front of it — public HTTPS URL, no port forwarding,
free.

---

## Environment variables (all deployments)

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | **yes** (hosted) | long random string; the server refuses to boot without it |
| `LICENSE_SECRET_KEY` | **yes** (hosted) | signs every product key; never rotate casually |
| `ALLOWED_HOSTS` | **yes** (hosted) | comma-separated hostnames |
| `DJANGO_DEBUG` | no | defaults to `False` |
| `DATABASE_URL` | no | set → Postgres; unset → SQLite (offline) |
| `POSTGRES_PASSWORD` | **yes** (compose) | for the bundled Postgres |
| `USE_S3` + `AWS_*` | recommended | Cloudflare R2 for media + offsite backups |
| `GUNICORN_WORKERS` | no | default 2 (compose uses 3) |

---

## Moving existing data off Railway

1. On Railway: **Settings → Data → Download** the Postgres dump, or use
   `railway run pg_dump $DATABASE_URL > backup.sql`.
2. On the new host, after migrations:
   `docker compose exec -T db psql -U schoolms schoolms < backup.sql`
3. Or use the app's own **Settings → Data Export / Import** (moves one
   school cleanly between deployments).

Media already lives in R2 (if `USE_S3=true`), so it moves with you
automatically.
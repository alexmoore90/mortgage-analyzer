# 🏠 Mortgage & Rental Analyzer

An interactive Streamlit app for comparing 15-year vs 30-year mortgage strategies
with a full rental cash-flow overlay. Built with `uv` for reproducible environments
and Docker for easy deployment.

---

## What It Does

- **Amortization tables** — monthly or yearly, for both loan terms
- **Rental cash-flow overlay** — every row shows net cash flow after mortgage,
  taxes, insurance, management fees, and maintenance
- **Extra principal payments** — sliders + lump-sum support for the 30-yr
- **Side-by-side comparison** — interest saved, payoff dates, equity milestones,
  break-even rent
- **Charts** — equity % over time, cash-flow bars, cost breakdown

---

## Quickstart — Local with `uv`

### 1. Install `uv` (if you don't have it)

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and run

```bash
git clone https://github.com/YOUR_USERNAME/mortgage-analyzer.git
cd mortgage-analyzer

# Install dependencies and run in one command
uv run streamlit run app.py
```

`uv` will automatically create a virtual environment, install all pinned
dependencies from `uv.lock`, and launch the app. Open
[http://localhost:8501](http://localhost:8501) in your browser.

> **No manual `pip install` needed.** `uv` handles everything.

---

## Docker Deployment

Docker lets you run the app anywhere — your laptop, a server, or a cloud VM —
with zero environment setup.

### Build and run with Docker Compose (recommended)

```bash
# Build the image and start the container
docker compose up --build

# Run in background
docker compose up --build -d

# Stop
docker compose down
```

Open [http://localhost:8501](http://localhost:8501).

### Build and run with plain Docker

```bash
# Build
docker build -t mortgage-analyzer .

# Run
docker run -p 8501:8501 mortgage-analyzer
```

### Deploy to a cloud VM (e.g. DigitalOcean, AWS EC2, Hetzner)

```bash
# On the server — install Docker, then:
git clone https://github.com/YOUR_USERNAME/mortgage-analyzer.git
cd mortgage-analyzer
docker compose up --build -d
```

The app will be accessible at `http://YOUR_SERVER_IP:8501`.
To add HTTPS, put Nginx or Caddy in front of it.

---

## Publishing to GitHub

```bash
# First time
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mortgage-analyzer.git
git push -u origin main

# Subsequent updates
git add .
git commit -m "your message"
git push
```

---

## Project Structure

```
mortgage-analyzer/
├── app.py                  # Streamlit UI — all pages and charts
├── mortgage_engine.py      # Pure-Python calculation engine (no Streamlit)
├── pyproject.toml          # uv project manifest + dependencies
├── uv.lock                 # Pinned lockfile (commit this!)
├── Dockerfile              # Container definition
├── docker-compose.yml      # Local dev + deploy helper
├── .streamlit/
│   └── config.toml         # Theme and server settings
├── .dockerignore
└── .gitignore
```

### Key design decisions

| Decision | Reason |
|---|---|
| `mortgage_engine.py` has no Streamlit imports | Logic is fully testable without the UI |
| `uv.lock` is committed | Guarantees identical installs everywhere |
| `uv sync --frozen` in Docker | Docker always uses exact pinned versions |
| `@st.cache_data` on schedule builder | Prevents recalculation on every widget interaction |

---

## Updating Dependencies

```bash
# Add a new package
uv add some-package

# Upgrade all packages
uv lock --upgrade

# Re-sync environment after lockfile changes
uv sync
```

Always commit `uv.lock` after any dependency changes.

---

## Customizing Defaults

All loan defaults are set via sidebar widgets in `app.py`. To change the
starting values, search for `value=` in the sidebar section and update them.

---

## License

MIT — do whatever you want with it.

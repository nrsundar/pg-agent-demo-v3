# Setup Guide

## Option A: Docker (recommended for demos and workshops)

The fastest way to get a fully configured PostgreSQL instance with `pgvector` pre-installed.

### 1. Start the database

```bash
docker-compose up -d
```

This starts `pgvector/pgvector:pg16` and automatically runs `db/schema.sql` and `db/seed.sql` on first boot.

Wait for the health check to pass:

```bash
docker-compose ps   # STATUS should show "healthy"
```

### 2. Set the connection string

**macOS / Linux:**
```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pg_agent_demo
```

**Windows (PowerShell):**
```powershell
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pg_agent_demo"
```

### 3. Create a virtual environment and install dependencies

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 4. Run the demo

```bash
python demo/run_demo.py
```

Or run a specific query:

```bash
python app/main.py --query "Show me the strongest sales region"
```

---

## Option B: Existing PostgreSQL instance

Use this if you already have PostgreSQL running locally.

### 1. Enable the pgvector extension

Connect to your target database and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

> The `pgvector/pgvector` Docker image includes this automatically. If you installed
> PostgreSQL from a package manager, install the extension first:
> - **Ubuntu/Debian:** `sudo apt install postgresql-16-pgvector`
> - **macOS (Homebrew):** `brew install pgvector`
> - **Windows:** download from https://github.com/pgvector/pgvector/releases

### 2. Apply schema and seed data

```bash
psql "$DATABASE_URL" -f db/schema.sql
psql "$DATABASE_URL" -f db/seed.sql
```

### 3. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the demo

```bash
python demo/run_demo.py
```

---

## Option C: No PostgreSQL (in-memory fallback)

If `DATABASE_URL` is not set, the application automatically falls back to an in-memory repository that mirrors the seeded demo data. No database setup required.

```bash
pip install -r requirements.txt
python demo/run_demo.py
```

This is the safest option for conference environments where network or AV issues can occur. See the startup output — it will clearly state which mode is active.

---

## Running the tests

The test suite always uses the in-memory adapter so no database is required:

```bash
pytest
```

<div align="center">

<img src="https://i.ibb.co/ftzHwQB/logo.png" alt="IPL 2026 API" width="120" />

# IPL 2026 Cricket API

A free, open-source REST API that scrapes live IPL 2026 data (schedule, points table, squads, winners and three independent live-score sources) and serves clean JSON.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-21.x-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge)](#contributing)

</div>

## Table of Contents

1. [Features](#features)
2. [Endpoints](#endpoints)
3. [Sample Response](#sample-response)
4. [Local Setup](#local-setup)
5. [Deployment Guide](#deployment-guide)
6. [Vercel Deployment](#vercel-deployment)
7. [Contributing](#contributing)
8. [License](#license)

## Features

- Live IPL 2026 schedule with venue, date and team details
- Real-time points table with NRR, wins, losses and form
- Three independent live-score sources for redundancy (Sportskeeda, Crex, Cricbuzz)
- Squad lookup for every franchise by short code
- Historical winners list since IPL 2008
- Graceful error handling, every endpoint returns JSON (never crashes)
- Lightweight footprint, no database required

> [!NOTE]
> Data is scraped on-demand from public sources. There is no caching layer, so each request hits the upstream site. For heavy production use you should add a cache (Redis, in-memory, or a CDN) in front of these endpoints.

## Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| `GET` | `/` | HTML documentation page |
| `GET` | `/health` | Service health probe |
| `GET` | `/ipl-2026-schedule` | Full season fixture list |
| `GET` | `/ipl-2026-points-table` | Live points table |
| `GET` | `/ipl-2026-live-score` | Live scores from Sportskeeda |
| `GET` | `/ipl-2026-live-score-s2` | Live scores from Crex |
| `GET` | `/ipl-2026-live-score-s3` | Live scores from Cricbuzz |
| `GET` | `/squad/<code>` | Squad of a franchise |
| `GET` | `/ipl-winners` | Past IPL winners |

**Squad codes:** `mi`, `csk`, `rcb`, `kkr`, `srh`, `dc`, `pbks`, `rr`, `gt`, `lsg`

> [!TIP]
> Every live-score route also has a season-less alias (e.g. `/ipl-live-score`) that always points at the current season constant inside `app.py`.

## Sample Response

`GET /ipl-2026-live-score-s3`

```json
{
  "status_code": 200,
  "season": "2026",
  "source": "cricbuzz",
  "status": "Live",
  "live_count": 1,
  "matches": {
    "Match 1": {
      "status": "Live",
      "title": "Sunrisers Hyderabad vs Kolkata Knight Riders, 45th Match",
      "team_1": "Sunrisers Hyderabad",
      "score_1": "106-2 (9.2)",
      "team_2": "Kolkata Knight Riders",
      "score_2": "N.A",
      "status_text": "Sunrisers Hyderabad opt to bat"
    }
  }
}
```

## Local Setup

### Prerequisites
- Python 3.11 or newer
- pip and virtualenv

### Steps

```bash
git clone https://github.com/cu-sanjay/IPL-2026-API-Free.git
cd IPL-2026-API-Free

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

The API will be live on `http://localhost:5000`.

For production-like serving locally:

```bash
gunicorn -b 0.0.0.0:5000 -w 2 -t 60 app:app
```

> [!IMPORTANT]
> Always run with `gunicorn` (or another WSGI server) in production. Flask's built-in dev server is single-threaded and not safe for public traffic.

## Deployment Guide

This app is a standard long-running Flask service, so any platform that runs Python web workers will host it.

### Render (recommended, free tier available, sleeps on inactivity)

1. Push the project to GitHub.
2. Go to [render.com](https://render.com) and click **New > Web Service**.
3. Connect your repo.
4. Fill in:
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`
5. Click **Create Web Service**. Done.

### Railway

1. Go to [railway.app](https://railway.app) and create a new project from your GitHub repo.
2. Railway auto-detects Python and reads the `Procfile`.
3. Click **Deploy**.

### Heroku (Not Free Anymore)

```bash
heroku login
heroku create ipl-2026-api
git push heroku main
heroku open
```

The included `Procfile` and `app.json` are already configured.

### Fly.io

```bash
fly launch                        # answer the prompts, decline a database
fly deploy
```

### Docker (any VPS)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-b", "0.0.0.0:5000", "-w", "2", "-t", "60", "app:app"]
```

Then:

```bash
docker build -t ipl-2026-api .
docker run -p 5000:5000 ipl-2026-api
```

## Vercel Deployment

> [!WARNING]
> Vercel is built for serverless functions, not long-running web servers. A traditional Flask + gunicorn setup will **not** work directly. You can still run this project on Vercel by adapting it to their Python serverless runtime.

### Steps to make it Vercel-compatible

1. Create a folder called `api/` in the project root.
2. Move `app.py` into `api/index.py` (or create `api/index.py` that imports `app`):

   ```python
   from app import app
   ```

3. Add a `vercel.json` at the project root:

   ```json
   {
     "version": 2,
     "builds": [
       { "src": "api/index.py", "use": "@vercel/python" }
     ],
     "routes": [
       { "src": "/(.*)", "dest": "api/index.py" }
     ]
   }
   ```

4. Push to GitHub.
5. Import the repo on [vercel.com](https://vercel.com), framework preset **Other**.
6. Click **Deploy**.

> [!CAUTION]
> Vercel free-tier serverless functions have a 10-second execution limit. Some scraped pages (especially Cricbuzz) can take longer than that under load and your endpoint will time out. For a reliable deployment, prefer **Render**, **Railway**, **Fly.io** or a small VPS.

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you would like to change.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "feat: my feature"`
4. Push the branch: `git push origin feature/my-feature`
5. Open a Pull Request

## License

Released under the [MIT License](LICENSE).

> [!NOTE]
> This project is for educational purposes. All cricket data belongs to its respective owners (Sportskeeda, Crex, Cricbuzz). Please respect their terms of service and add appropriate caching when using this API in production.

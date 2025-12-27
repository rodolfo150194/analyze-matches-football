# Deployment Guide - Dokploy

This guide explains how to deploy the Football Prediction Django app to Dokploy.

## Prerequisites

1. **Dokploy account** with access to your dashboard
2. **GitHub repository** already set up (https://github.com/rodolfo150194/analyze-matches-football)
3. **API keys** for external services

## Quick Deployment to Dokploy

### Step 1: Create New Project in Dokploy

1. Log in to your Dokploy dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub"**
4. Connect your GitHub account if not already connected
5. Select repository: `rodolfo150194/analyze-matches-football`
6. Select branch: `main`

### Step 2: Configure Build Settings

Dokploy will automatically detect the `Dockerfile` in your repository.

**Build Configuration:**
- **Build Method**: Dockerfile
- **Dockerfile Path**: `./Dockerfile`
- **Port**: 8000

### Step 3: Set Environment Variables

In Dokploy, go to **Settings → Environment Variables** and add:

#### Required Variables:

```bash
# Django Security
SECRET_KEY=generate-a-strong-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-dokploy-domain.com

# API Keys (get from your providers)
API_KEY_FOOTBALL_DATA=your_football_data_api_key
API_KEY_ODDS=your_odds_api_key
API_KEY_FOOTBALL=your_football_api_key
```

#### PostgreSQL Database (Recommended):

Use your Dokploy PostgreSQL service:

```bash
DATABASE_URL=postgresql://futbol-db:futbol.db@futbol-db-uhnlos:5432/futbol-db
```

**Database Details:**
- User: `futbol-db`
- Password: `futbol.db`
- Database: `futbol-db`
- Internal Host: `futbol-db-uhnlos`
- Port: `5432`

**Note**: The app will automatically use PostgreSQL if `DATABASE_URL` is set, otherwise it falls back to SQLite.

### Step 4: Deploy

1. Click **"Deploy"** button
2. Dokploy will:
   - Pull code from GitHub
   - Build Docker image using your Dockerfile
   - Run migrations automatically
   - Collect static files
   - Start gunicorn server with 4 workers
3. Wait for deployment to complete (5-10 minutes first time)

### Step 5: Access Your Application

Once deployed:
- **Web interface**: `https://your-project.dokploy.app/matches/`
- **Admin panel**: `https://your-project.dokploy.app/admin/`

### Step 6: Create Admin User

After first deployment, access the Dokploy console and run:

```bash
python manage.py createsuperuser
```

Follow prompts to create admin credentials.

## Post-Deployment Tasks

### Import Data

Use the console or SSH into your container:

```bash
# Import historical data
python manage.py import_sofascore_complete --competitions PL,PD,BL1,SA,FL1 --seasons 2024,2023 --all-data

# Consolidate duplicate teams
python manage.py consolidate_teams_fuzzy --threshold 95

# Calculate statistics
python manage.py calculate_stats --competitions PL,PD,BL1,SA,FL1 --force

# Train ML models
python manage.py train_models --competitions PL,PD,BL1,SA,FL1 --seasons 2023,2024

# Generate predictions
python manage.py predict --days 7 --competitions PL,PD,BL1,SA,FL1
```

## Database Options

### Option 1: SQLite (Default)

- ✅ Easy to set up
- ✅ No extra configuration needed
- ⚠️ Limited scalability
- ⚠️ Data lost on container restart (unless volume mounted)

**Recommended for**: Testing, small deployments

### Option 2: PostgreSQL (Recommended for Production)

1. Create PostgreSQL service in Dokploy
2. Update environment variables with `DATABASE_URL`
3. Update `settings.py` to use PostgreSQL:

```python
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'
    )
}
```

4. Add to `requirements.txt`: `dj-database-url>=2.1.0`

## Troubleshooting

### Deployment Fails

**Check logs in Dokploy console:**
```bash
# View application logs
dokploy logs --tail 100

# Check build logs
dokploy build logs
```

### Static Files Not Loading

Ensure `collectstatic` ran during build:
```bash
python manage.py collectstatic --noinput
```

This is already in the `Dockerfile` but can be run manually if needed.

### Playwright/Browser Issues

Playwright is installed in the Dockerfile for SofaScore scraping. If you encounter issues:

1. Check Chromium installation in logs
2. May need to increase memory limits in Dokploy settings
3. Alternative: Disable Playwright and use CSV imports only

### API Rate Limits

- **SofaScore**: May return 403 if over-scraped. Use delays.
- **The Odds API**: 500 requests/month on free tier
- **Football-Data.org**: 10 requests/minute

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ Yes | - | Django secret key (generate new one) |
| `DEBUG` | No | `False` | Enable debug mode (use False in production) |
| `ALLOWED_HOSTS` | ✅ Yes | `*` | Comma-separated domains |
| `API_KEY_FOOTBALL_DATA` | No | - | Football-Data.org API key |
| `API_KEY_ODDS` | No | - | The Odds API key |
| `API_KEY_FOOTBALL` | No | - | Football API key |
| `DATABASE_URL` | No | SQLite | PostgreSQL connection string |

## Generating SECRET_KEY

In Python:
```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

Or online: https://djecrety.ir/

## Local Testing with Docker

Before deploying to Dokploy, test locally:

```bash
# Build image
docker build -t football-django .

# Run container
docker run -p 8000:8000 \
  -e SECRET_KEY=your-secret-key \
  -e DEBUG=False \
  -e ALLOWED_HOSTS=localhost \
  football-django

# Or use docker-compose
docker-compose up
```

Access at: http://localhost:8000

## Continuous Deployment

Dokploy automatically redeploys on git push to `main` branch:

```bash
git add .
git commit -m "Update feature"
git push origin main
```

Dokploy will detect the push and rebuild/redeploy automatically.

## Scaling

In Dokploy dashboard:
- **Horizontal scaling**: Increase number of replicas
- **Vertical scaling**: Increase CPU/Memory per container
- **Database**: Use managed PostgreSQL for better performance

## Monitoring

Dokploy provides:
- **Application logs**: Real-time streaming
- **Resource usage**: CPU, Memory, Network
- **Uptime monitoring**: Health checks every 30s
- **Alerts**: Email/Slack notifications on failures

## Cost Optimization

To reduce costs:
1. Use SQLite instead of managed PostgreSQL for small apps
2. Reduce number of gunicorn workers (2 instead of 4)
3. Import data less frequently
4. Cache ML model predictions

## Support

- **Dokploy Docs**: https://docs.dokploy.com
- **Project Issues**: https://github.com/rodolfo150194/analyze-matches-football/issues
- **Django Deployment**: https://docs.djangoproject.com/en/stable/howto/deployment/

---

**Ready to deploy?** Follow Step 1 above and you'll be live in minutes!

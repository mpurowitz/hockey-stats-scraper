# 🏒 Quick Start: Deploy Hockey Scraper to Render

## What You Get

✅ **Automated weekly scraping** - Runs every Sunday at 2 AM UTC  
✅ **Web dashboard** - Access stats anytime at your Render URL  
✅ **Data storage** - Saves JSON + Excel files to persistent disk  
✅ **API endpoints** - Download latest data programmatically  
✅ **100% FREE** - Using Render's free tier  

---

## 5-Minute Setup

### 1. Push to GitHub

```bash
cd /path/to/your/scraper/folder
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/hockey-scraper.git
git push -u origin main
```

### 2. Connect to Render

1. Go to https://dashboard.render.com
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Select the repo
5. Click "Apply"

### 3. Wait for Deployment

- Takes 5-10 minutes first time
- Watch the logs for progress
- You'll get 2 services:
  - `hockey-stats-dashboard` (web)
  - `hockey-stats-scraper-job` (cron)

### 4. Access Your Dashboard

Visit: `https://hockey-stats-dashboard.onrender.com`

---

## Files You Need

Make sure these are in your GitHub repo:

```
✅ enhanced_scraper_2025-2026.py
✅ enhanced_dashboard.html
✅ web_server.py
✅ scheduled_scraper.py
✅ requirements.txt
✅ render.yaml
✅ Dockerfile
```

---

## How It Works

### Web Service (24/7):
- Hosts your dashboard
- Serves latest scraped data
- Provides download links
- URL: `https://YOUR-APP.onrender.com`

### Cron Job (Weekly):
- Runs every Sunday 2 AM UTC
- Scrapes all configured leagues
- Saves to `/data` disk
- Takes ~30-60 min per run

### Data Storage:
- Persistent disk mounted at `/data`
- Stores JSON + Excel files
- 1 GB storage (free)
- Shared between web service and cron job

---

## API Endpoints

After deployment, you can access:

```
Dashboard:
https://YOUR-APP.onrender.com/

Latest Excel:
https://YOUR-APP.onrender.com/api/latest-excel

Latest JSON:
https://YOUR-APP.onrender.com/api/latest-data

File List:
https://YOUR-APP.onrender.com/api/data-info

Health Check:
https://YOUR-APP.onrender.com/health
```

---

## Customize Schedule

Edit `render.yaml` to change when scraper runs:

```yaml
schedule: "0 2 * * 0"   # Sunday 2 AM UTC
schedule: "0 3 * * *"   # Every day 3 AM UTC
schedule: "0 1 * * 1,5" # Monday & Friday 1 AM UTC
```

---

## Customize Leagues

Edit `scheduled_scraper.py`:

```python
LEAGUES_TO_SCRAPE = [
    {
        'name': 'NA3HL',
        'url': 'https://www.eliteprospects.com/league/na3hl',
        'max_teams': None  # None = all teams, or set number like 10
    },
    # Add more leagues...
]
```

---

## Test Manually

1. Go to Render dashboard
2. Click on `hockey-stats-scraper-job`
3. Click "Trigger Run" (top right)
4. Watch the logs

---

## Download Data

### Via Browser:
Visit `https://YOUR-APP.onrender.com/api/latest-excel`

### Via Command Line:
```bash
curl https://YOUR-APP.onrender.com/api/latest-excel -o stats.xlsx
```

### Via Python:
```python
import requests

url = 'https://YOUR-APP.onrender.com/api/latest-data'
data = requests.get(url).json()
print(f"Leagues: {list(data.keys())}")
```

---

## Costs

**FREE TIER:**
- Web service: Free (750 hours/month)
- Cron job: Free (400 build hours/month)
- 1 GB disk: Free
- **Total: $0/month**

**Limitations:**
- Web sleeps after 15 min (wakes on access)
- Plenty for weekly scraping

**Upgrade if needed:**
- $7/month for always-on web service
- $0.25/GB/month for more storage

---

## Troubleshooting

### Web service shows 404:
- Wait for first scrape to complete
- Or manually trigger cron job

### Cron job fails:
- Check logs in Render dashboard
- May need to reduce leagues or max_teams

### Need help?
- Check full guide: `RENDER_DEPLOYMENT_GUIDE.md`
- Render docs: https://render.com/docs

---

## Next Steps

1. ✅ Deploy to Render
2. ✅ Trigger first scrape manually
3. ✅ Verify data saved
4. ✅ Access dashboard
5. 📊 Download weekly Excel files
6. 📈 Track player stats over time

---

**You're all set! 🏒 Your scraper will now run every Sunday automatically.**

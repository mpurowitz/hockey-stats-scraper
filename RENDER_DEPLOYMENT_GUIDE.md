# 🏒 Render Deployment Guide - Hockey Stats Scraper

## Overview

This guide will help you deploy the hockey stats scraper to Render with:
- **Web Service**: Hosts dashboard 24/7, serves latest data
- **Cron Job**: Runs scraper automatically every Sunday at 2 AM UTC
- **Persistent Storage**: Saves data between runs

---

## Prerequisites

1. **Render Account**: Sign up at https://render.com (free tier works)
2. **GitHub Repository**: Push your scraper code to GitHub
3. **Files Required**:
   - `enhanced_scraper_2025-2026.py`
   - `enhanced_dashboard.html`
   - `web_server.py`
   - `scheduled_scraper.py`
   - `requirements.txt`
   - `render.yaml`

---

## Step 1: Prepare Your Repository

### Create GitHub Repository

```bash
cd /path/to/Recruiting_Scraper
git init
git add .
git commit -m "Initial commit - Hockey stats scraper"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hockey-stats-scraper.git
git push -u origin main
```

### Required Files

Ensure these files are in your repo:

```
hockey-stats-scraper/
├── enhanced_scraper_2025-2026.py    # Main scraper
├── enhanced_dashboard.html          # Dashboard UI
├── web_server.py                    # Web server
├── scheduled_scraper.py             # Cron job script
├── requirements.txt                 # Python dependencies
└── render.yaml                      # Render configuration
```

---

## Step 2: Update requirements.txt

Ensure your `requirements.txt` includes Chrome dependencies for Render:

```txt
selenium==4.15.2
webdriver-manager==4.0.1
openpyxl==3.1.2
python-docx==1.1.0
flask==3.0.0
flask-cors==4.0.0
beautifulsoup4==4.12.2
lxml==4.9.3
requests==2.31.0
```

---

## Step 3: Deploy to Render

### Option A: Using render.yaml (Recommended)

1. **Push to GitHub**:
   ```bash
   git add render.yaml
   git commit -m "Add Render configuration"
   git push
   ```

2. **Go to Render Dashboard**:
   - Visit https://dashboard.render.com

3. **New Blueprint**:
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Render will detect `render.yaml` automatically
   - Click "Apply"

4. **Wait for Deployment**:
   - Web service will deploy (takes 5-10 minutes)
   - Cron job will be created (runs weekly)

### Option B: Manual Setup

#### Create Web Service:

1. **New Web Service**:
   - Click "New +" → "Web Service"
   - Connect GitHub repo
   - **Name**: `hockey-stats-dashboard`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python web_server.py`
   - **Plan**: Free

2. **Add Disk**:
   - In service settings → "Disks"
   - Click "Add Disk"
   - **Name**: `hockey-data`
   - **Mount Path**: `/data`
   - **Size**: 1 GB
   - Click "Save"

3. **Environment Variables**:
   - Add `DATA_DIR` = `/data`
   - Add `PORT` = `10000`

#### Create Cron Job:

1. **New Cron Job**:
   - Click "New +" → "Cron Job"
   - Connect same GitHub repo
   - **Name**: `hockey-stats-scraper-job`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Command**: `python scheduled_scraper.py`
   - **Schedule**: `0 2 * * 0` (Every Sunday 2 AM UTC)
   - **Plan**: Free

2. **Add Disk** (same as web service):
   - **Name**: `hockey-data`
   - **Mount Path**: `/data`
   - **Size**: 1 GB

3. **Environment Variables**:
   - Add `DATA_DIR` = `/data`

---

## Step 4: Configure Scraper Settings

Edit `scheduled_scraper.py` to customize:

```python
# Which leagues to scrape
LEAGUES_TO_SCRAPE = [
    {'name': 'NA3HL', 'url': '...', 'max_teams': None},  # None = all teams
    {'name': 'USPHL Premier', 'url': '...', 'max_teams': 10},  # 10 teams only
    # Add/remove leagues as needed
]

# Scraping settings
SEASON = '2025-2026'
DELAY = 3  # Seconds between requests (increase if getting rate limited)
```

---

## Step 5: Test Deployment

### Test Web Service:

1. Visit your Render dashboard
2. Click on `hockey-stats-dashboard`
3. Copy the URL (e.g., `https://hockey-stats-dashboard.onrender.com`)
4. Visit the URL - you should see the dashboard

### Test Cron Job Manually:

1. Go to `hockey-stats-scraper-job` in Render
2. Click "Trigger Run" (top right)
3. Watch logs to see scraping progress
4. First run will take 30-60 minutes depending on leagues

---

## Step 6: Access Your Data

### Dashboard URLs:

```
Main Dashboard:
https://hockey-stats-dashboard.onrender.com/

API Endpoints:
https://hockey-stats-dashboard.onrender.com/api/latest-data
https://hockey-stats-dashboard.onrender.com/api/data-info
https://hockey-stats-dashboard.onrender.com/api/latest-excel
https://hockey-stats-dashboard.onrender.com/health
```

### Download Latest Data:

```bash
# Get latest Excel file
curl https://hockey-stats-dashboard.onrender.com/api/latest-excel -o stats.xlsx

# Get latest JSON data
curl https://hockey-stats-dashboard.onrender.com/api/latest-data > stats.json

# Get info about available files
curl https://hockey-stats-dashboard.onrender.com/api/data-info
```

---

## Scheduling Options

Edit the `schedule` in `render.yaml`:

```yaml
# Every Sunday at 2 AM UTC
schedule: "0 2 * * 0"

# Every day at 3 AM UTC
schedule: "0 3 * * *"

# Every Monday and Friday at 1 AM UTC
schedule: "0 1 * * 1,5"

# Twice a week: Sunday and Wednesday at 2 AM UTC
schedule: "0 2 * * 0,3"
```

**Cron Format**: `minute hour day month weekday`
- `0 2 * * 0` = minute 0, hour 2, any day, any month, Sunday (0=Sunday, 6=Saturday)

---

## Cost Estimates

### Free Tier (Recommended for Start):
- **Web Service**: Free (750 hours/month, sleeps after 15 min inactivity)
- **Cron Job**: Free (up to 400 build hours/month)
- **Disk**: Free (1 GB)
- **Total**: $0/month

### Limitations:
- Web service sleeps after 15 min (wakes up when accessed)
- Cron jobs limited to 400 hours/month
- 1 GB storage (stores ~50 scrape runs)

### Paid Options:
If you need 24/7 uptime or more storage:
- **Starter Plan**: $7/month (no sleep, faster)
- **Additional Disk**: $0.25/GB/month

---

## Monitoring & Logs

### View Logs:

1. **Web Service Logs**:
   - Render Dashboard → `hockey-stats-dashboard` → "Logs"
   - See real-time access logs

2. **Cron Job Logs**:
   - Render Dashboard → `hockey-stats-scraper-job` → "Logs"
   - See scraping progress, errors
   - Click on specific run to see full output

### Set Up Alerts:

1. Go to service settings
2. "Notifications" tab
3. Add email or Slack webhook
4. Get notified on:
   - Deploy failures
   - Cron job failures
   - Service downtime

---

## Troubleshooting

### Issue: "Chrome not found" error

**Fix**: Render uses a Dockerfile for Chrome. Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install Chrome dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "web_server.py"]
```

Then update `render.yaml`:
```yaml
services:
  - type: web
    name: hockey-stats-dashboard
    env: docker  # Changed from python
```

### Issue: Cron job times out

**Fix**: Reduce leagues or set `max_teams`:
```python
LEAGUES_TO_SCRAPE = [
    {'name': 'NA3HL', 'url': '...', 'max_teams': 10},  # Only 10 teams
]
```

### Issue: Disk full

**Fix**: Delete old files in `scheduled_scraper.py`:
```python
# Add to main() function:
def cleanup_old_files():
    """Keep only last 10 data files"""
    files = sorted(glob.glob(os.path.join(DATA_DIR, 'scraped_data_*.json')))
    if len(files) > 10:
        for old_file in files[:-10]:
            os.remove(old_file)
            print(f"🗑️ Deleted old file: {old_file}")
```

---

## Alternative: AWS S3 Storage

If you want unlimited storage:

### Setup:

1. Create AWS S3 bucket
2. Get AWS credentials (Access Key, Secret Key)
3. Add to Render environment variables:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `S3_BUCKET_NAME`

4. Update `scheduled_scraper.py`:
```python
import boto3

def save_to_s3(data, timestamp):
    s3 = boto3.client('s3')
    bucket = os.environ['S3_BUCKET_NAME']
    
    # Save JSON
    s3.put_object(
        Bucket=bucket,
        Key=f'scraped_data_{timestamp}.json',
        Body=json.dumps(data)
    )
```

---

## Next Steps

1. ✅ Deploy to Render
2. ✅ Test cron job manually
3. ✅ Verify data is saved to `/data`
4. ✅ Access dashboard at your Render URL
5. ✅ Schedule weekly runs
6. 📊 Download Excel files weekly
7. 📈 Analyze trends over time

---

## Support

**Render Docs**: https://render.com/docs
**Cron Help**: https://crontab.guru (schedule tester)
**This Scraper**: Check GitHub repo issues

---

**Good luck with your deployment! 🏒**

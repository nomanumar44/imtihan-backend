# Deployment Notes

## AI Assistant (Gemini) API Key Setup

### Local Development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Get a free Gemini API key:
   - Go to [Google AI Studio](https://aistudio.google.com/)
   - Click **"Get API Key"**
   - Create a new key (no credit card needed)
   - Copy the key

3. Paste the key into `.env`:
   ```
   GEMINI_API_KEY=AIzaSy...your_key_here
   ```

4. Restart Django dev server:
   ```bash
   python manage.py runserver
   ```

### AWS EC2 (Production)

**Option A: /etc/environment (system-wide)**

```bash
sudo nano /etc/environment
```

Add this line:
```
GEMINI_API_KEY=AIzaSy...your_key_here
```

Save, then reload and restart:
```bash
source /etc/environment
sudo systemctl restart gunicorn
```

**Option B: systemd service file**

Edit your gunicorn service:
```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Add under `[Service]`:
```ini
[Service]
Environment="GEMINI_API_KEY=AIzaSy...your_key_here"
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

**Option C: .env file on the server**

If your deployment copies `.env` to the server, ensure it contains:
```
GEMINI_API_KEY=AIzaSy...your_key_here
```

Then restart gunicorn:
```bash
sudo systemctl restart gunicorn
```

### Free Tier Limits

`gemini-1.5-flash` free tier:
- **15 requests per minute**
- **1 million tokens per day**
- **No credit card required**

This is more than enough for your 5 questions per user per day limit.

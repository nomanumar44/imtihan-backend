# Deployment Notes

## Environment Variables

Set these in `.env` (local) or the server environment. Only `SECRET_KEY` is
required in production; the rest have defaults suitable for local development.

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Django secret. **Required when `DEBUG=False`** (startup fails without it). | insecure dev key |
| `DEBUG` | `True` / `False` | `True` |
| `ALLOWED_HOSTS` | Comma-separated hostnames, e.g. `api.imtihanhub.com.pk` | `*` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated frontend origins, e.g. `https://imtihanhub.com.pk,https://www.imtihanhub.com.pk`. Unset allows all origins. | allow all |
| `CSRF_TRUSTED_ORIGINS` | HTTPS origins that submit dashboard/admin forms, e.g. `https://api.imtihanhub.com.pk` | none |
| `FRONTEND_URL` | Public site URL used in email links | `http://localhost:3000` |
| `BACKEND_URL` | Public API URL used in email links (unsubscribe) | `http://127.0.0.1:8000` |
| `NUM_PROXIES` | Number of reverse proxies in front of Django (e.g. `1` behind nginx); makes rate limiting use the real client IP | unset |
| `QUICK_POST_SECRET` | Shared secret for `/quick-post/`. **Quick post is disabled until this is set.** | unset |
| `GROQ_API_KEY`, `KIMI_API_KEY`, `GEMINI_API_KEY` | AI tutor providers (comma-separated keys allowed) | unset |
| `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | SMTP settings | console backend |
| `ADMIN_EMAILS` | Comma-separated recipients for new service-request alerts | none |
| `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | `postgresql` / `mssql`; SQLite when unset | SQLite |

## Scheduled Commands

Nothing in the project schedules these; add them to cron on the server:

```cron
0 9,18 * * *  cd /path/to/imtihan-backend && python manage.py send_deadline_reminders
0 8 * * *     cd /path/to/imtihan-backend && python manage.py send_news_digest
```

## Tests

```bash
python manage.py test core
```

## AI Assistant (Gemini) API Key Setup

### Local Development

1. Create `.env` in the project root (it is git-ignored).

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

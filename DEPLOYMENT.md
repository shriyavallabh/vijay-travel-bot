# Deployment Guide: Shri Travels Admin Panel

This guide explains how to deploy the FastAPI backend and React Admin frontend to Railway.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Railway                               │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   Backend Service   │    │   Frontend Service          │ │
│  │   (FastAPI + Bot)   │◄───│   (React Admin Panel)       │ │
│  │   Port: 8000        │    │   Port: 80 (nginx)          │ │
│  │                     │    │                             │ │
│  │   Endpoints:        │    │   Features:                 │ │
│  │   - /webhook        │    │   - Dashboard               │ │
│  │   - /api/*          │    │   - Customer List           │ │
│  │   - /stats          │    │   - Chat Interface          │ │
│  └─────────────────────┘    └─────────────────────────────┘ │
│            │                             │                   │
│            ▼                             │                   │
│  ┌─────────────────────┐                 │                   │
│  │   PostgreSQL        │                 │                   │
│  │   (Railway Plugin)  │◄────────────────┘                   │
│  └─────────────────────┘                                     │
└─────────────────────────────────────────────────────────────┘
```

## Option 1: Monorepo Deployment (Recommended)

### Step 1: Add PostgreSQL Database

1. Go to your Railway project dashboard
2. Click "New" → "Database" → "PostgreSQL"
3. Railway will automatically set `DATABASE_URL` environment variable

### Step 2: Deploy Backend (Already Done)

Your FastAPI backend should already be deployed. Just add these new environment variables:

```
DATABASE_URL=<auto-set by Railway PostgreSQL>
ADMIN_ORIGINS=https://your-admin-panel.up.railway.app,http://localhost:3000
```

### Step 3: Deploy Frontend

1. In Railway dashboard, click "New" → "GitHub Repo"
2. Select the same repo, but set:
   - **Root Directory**: `admin_panel`
   - **Build Command**: `npm ci && npm run build`
   - **Start Command**: (leave empty for static hosting)

3. Add environment variables:
   ```
   VITE_API_URL=https://your-backend.up.railway.app/api
   ```

4. Generate a domain for the frontend service

### Step 4: Update Backend CORS

Add the frontend domain to `ADMIN_ORIGINS` in the backend service:
```
ADMIN_ORIGINS=https://your-frontend.up.railway.app
```

## Option 2: Separate Repositories

If you prefer separate repos:

### Backend Repo
Keep the current structure, deploy as-is.

### Frontend Repo
1. Copy `admin_panel/` to a new repo
2. Deploy to Railway as a static site
3. Set `VITE_API_URL` to your backend URL

## Environment Variables Reference

### Backend Service
| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key | sk-... |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp Business phone ID | 123456789 |
| `WHATSAPP_ACCESS_TOKEN` | Meta access token | EAAx... |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification token | my_token |
| `FB_APP_SECRET` | Facebook app secret | abc123 |
| `FB_APP_ID` | Facebook app ID | 123456 |
| `SERPER_API_KEY` | Serper search API key | xxx |
| `DATABASE_URL` | PostgreSQL connection URL | postgresql://... |
| `ADMIN_ORIGINS` | Allowed CORS origins | https://admin.example.com |

### Frontend Service
| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | https://api.example.com/api |

## Local Development

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd admin_panel

# Install dependencies
npm install

# Run dev server
npm run dev
```

The frontend dev server runs on http://localhost:3000 and proxies /api requests to the backend.

## Database Migrations

The database tables are created automatically on startup via `init_db()`.

To sync existing customers from the Knowledge Graph to the database:
```bash
curl -X POST https://your-backend.up.railway.app/api/sync/customers
```

Or use the "Sync Customers" button in the Admin Panel dashboard.

## Troubleshooting

### CORS Errors
- Ensure `ADMIN_ORIGINS` includes your frontend URL
- Check that the URL doesn't have a trailing slash

### Database Connection Issues
- Verify `DATABASE_URL` is correctly set
- For local dev, SQLite is used automatically if `DATABASE_URL` is not set

### Chat Messages Not Appearing
- Check that the WhatsApp webhook is correctly configured
- Verify the bot is processing messages (check Railway logs)

### Frontend Build Fails
- Ensure all TypeScript errors are resolved
- Check that `VITE_API_URL` is set during build

## API Endpoints Reference

### Admin API (`/api/*`)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/stats` | GET | Dashboard KPIs |
| `/api/users` | GET | List users (paginated) |
| `/api/users/{id}` | GET | Get user details |
| `/api/users/{id}` | PATCH | Update user |
| `/api/users/{id}/toggle-bot` | POST | Toggle bot pause |
| `/api/users/{id}/messages` | GET | Get chat history |
| `/api/messages/send` | POST | Admin sends message |
| `/api/conversations` | GET | List conversations |
| `/api/sync/customers` | POST | Sync from KG |

### Existing Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/webhook` | GET/POST | WhatsApp webhook |
| `/stats` | GET | System statistics |
| `/query` | POST | Query the RAG agent |

# Deployment Guide - Render

This guide will help you deploy AlgoClash Live to Render.

## Prerequisites

1. **Render Account**: Sign up at https://render.com
2. **GitHub Repository**: Push your code to GitHub
3. **API Keys**: Obtain the following keys:
   - OpenRouter API Key (required): https://openrouter.ai
   - E2B API Key (required): https://e2b.dev
   - FinancialDatasets.ai API Key (optional): https://financialdatasets.ai
   - GitHub Token (optional): https://github.com/settings/tokens
4. **MongoDB Atlas** (optional but recommended): https://www.mongodb.com/cloud/atlas

## Step 1: Prepare Your Repository

1. Ensure all files are committed and pushed to GitHub:
```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

2. Verify these files exist in your repository:
   - `render.yaml` (in root directory)
   - `runtime.txt` (in root directory)
   - `backend/requirements.txt`
   - `backend/app.py`

## Step 2: Create MongoDB Atlas Database (Optional)

1. Go to https://www.mongodb.com/cloud/atlas
2. Create a free cluster
3. Create a database user
4. Whitelist all IP addresses (0.0.0.0/0) for Render
5. Get your connection string:
   ```
   mongodb+srv://username:password@cluster.mongodb.net/algoclash?retryWrites=true&w=majority
   ```

## Step 3: Deploy to Render

### Option A: Using Blueprint (Recommended)

1. Go to https://dashboard.render.com
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml`
5. Configure environment variables (see below)
6. Click "Apply"

### Option B: Manual Web Service

1. Go to https://dashboard.render.com
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: algoclash-backend
   - **Runtime**: Python 3
   - **Build Command**: 
     ```
     pip install --upgrade pip && pip install -r backend/requirements.txt
     ```
   - **Start Command**: 
     ```
     cd backend && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
     ```
   - **Instance Type**: Free (or Starter for better performance)

## Step 4: Configure Environment Variables

In Render dashboard, go to your service → Environment → Add Environment Variables:

### Required Variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | Your OpenRouter API key |
| `E2B_API_KEY` | `e2b_...` | Your E2B API key for sandbox |

### Optional Variables:

| Variable | Value | Description |
|----------|-------|-------------|
| `GITHUB_TOKEN` | `github_pat_...` | For GitHub AI models |
| `FINANCIAL_DATASETS_API_KEY` | `your-key` | For stock fundamental data |
| `MONGO_URI` | `mongodb+srv://...` | MongoDB connection string |
| `ASSET_CLASS` | `CRYPTO` or `STOCK` | Trading mode (default: CRYPTO) |
| `ENABLE_SEMANTIC_ALPHA` | `true` | Enable sentiment analysis |
| `RENDER_EXTERNAL_URL` | Auto-set by Render | For keep-alive pings |

## Step 5: Deploy and Verify

1. Render will automatically build and deploy your service
2. Monitor the build logs for any errors
3. Once deployed, click the service URL (e.g., `https://algoclash-backend.onrender.com`)
4. You should see:
   ```json
   {
     "message": "AlgoClash Live - AI Trading Arena",
     "status": "running",
     "endpoints": {...}
   }
   ```

5. Test the health endpoint:
   ```
   https://your-service.onrender.com/health
   ```

## Step 6: Test Core Features

### Test 1: Check Status
```bash
curl https://your-service.onrender.com/status
```

Expected response:
```json
{
  "status": "online",
  "arena_running": false,
  "agent_count": 0,
  "active_agents": []
}
```

### Test 2: List Available Models
```bash
curl https://your-service.onrender.com/available_models
```

### Test 3: Create Sandbox Session
```bash
curl -X POST https://your-service.onrender.com/sandbox/create \
  -H "Content-Type: application/json" \
  -d '{"model": "openai/gpt-4o-mini"}'
```

Expected response:
```json
{
  "session_id": "uuid-here",
  "status": "created",
  "model": "openai/gpt-4o-mini"
}
```

## Build and Start Commands Summary

For quick reference:

**Build Command:**
```bash
pip install --upgrade pip && pip install -r backend/requirements.txt
```

**Start Command:**
```bash
cd backend && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
```

**Alternative Start Command (if socketio issues):**
```bash
cd backend && python app.py
```

## Troubleshooting

### Issue: Build Fails with "ModuleNotFoundError"

**Solution**: Check that `backend/requirements.txt` includes all dependencies:
```bash
# In your local environment
cd backend
pip freeze > requirements.txt
git add requirements.txt
git commit -m "Update requirements"
git push
```

### Issue: Service Crashes on Startup

**Solution**: Check logs in Render dashboard. Common issues:
- Missing required environment variables (OPENROUTER_API_KEY, E2B_API_KEY)
- MongoDB connection timeout (remove MONGO_URI if not using MongoDB)
- Port binding issues (ensure using $PORT in start command)

### Issue: WebSocket Connection Fails

**Solution**: 
- Ensure using `eventlet` worker class in gunicorn
- Check that frontend is connecting to correct backend URL
- Verify CORS is enabled in `backend/app.py`

### Issue: "Worker timeout" errors

**Solution**: Increase timeout in start command:
```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 300 app:app
```

### Issue: Memory Limit Exceeded (Free Tier)

**Solution**: 
- Remove unused dependencies from requirements.txt
- Consider upgrading to Starter tier ($7/month)
- Optimize agent loading (lazy load instead of preload)

### Issue: Service Sleeps After Inactivity (Free Tier)

**Solution**: The app includes automatic keep-alive pinging. Set `RENDER_EXTERNAL_URL`:
```
RENDER_EXTERNAL_URL=https://your-service.onrender.com
```

The backend will ping itself every 10 minutes to stay awake.

## Frontend Deployment (Optional)

To deploy the frontend separately:

1. Go to Render Dashboard → New Static Site
2. Connect your GitHub repository
3. Configure:
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Publish Directory**: `frontend/dist`
4. Add environment variable:
   - `VITE_API_URL`: Your backend URL (e.g., `https://algoclash-backend.onrender.com`)

5. Update `frontend/src/api.js` to use the environment variable:
```javascript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';
```

## Production Considerations

### 1. Database
- Use MongoDB Atlas (not in-memory mode)
- Enable authentication
- Whitelist Render IP ranges

### 2. API Keys
- Keep API keys secure (never commit to git)
- Use Render's environment variable encryption
- Rotate keys periodically

### 3. Monitoring
- Enable Render's health checks
- Monitor logs regularly
- Set up alerts for downtime

### 4. Scaling
- Start with Free tier for testing
- Upgrade to Starter ($7/month) for production
- Consider multiple workers if needed:
  ```bash
  gunicorn --worker-class eventlet -w 2 ...
  ```

### 5. Performance
- Enable MongoDB connection pooling
- Cache frequently accessed data
- Optimize agent execution frequency

## Cost Estimate

**Free Tier:**
- Render Web Service: $0 (sleeps after inactivity)
- MongoDB Atlas: $0 (512MB storage)
- Total: $0/month

**Production Setup:**
- Render Web Service (Starter): $7/month
- MongoDB Atlas (M10): $10/month
- Total: $17/month

## Support

If you encounter issues:
1. Check Render logs: Dashboard → Your Service → Logs
2. Review environment variables: Dashboard → Your Service → Environment
3. Test API endpoints with curl or Postman
4. Check GitHub Issues: https://github.com/yourusername/algoclash-live/issues

## Next Steps

After successful deployment:
1. Test the sandbox terminal at `/sandbox`
2. Generate your first agent
3. Deploy agents to the arena
4. Monitor performance on the dashboard
5. Share your deployment URL with users

---

Deployment URL format:
- Backend: `https://algoclash-backend.onrender.com`
- Frontend: `https://algoclash-frontend.onrender.com` (if deployed separately)

Remember to update your frontend API configuration to point to your Render backend URL.

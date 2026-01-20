# Render Deployment - Quick Reference

## Build Command
```bash
pip install --upgrade pip && pip install -r backend/requirements.txt
```

## Start Command
```bash
cd backend && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
```

## Environment Variables (Required)

### Must Have:
- `OPENROUTER_API_KEY` - Get from https://openrouter.ai
- `E2B_API_KEY` - Get from https://e2b.dev

### Recommended:
- `MONGO_URI` - MongoDB connection string (or leave empty for in-memory mode)
- `FINANCIAL_DATASETS_API_KEY` - For stock fundamental data
- `GITHUB_TOKEN` - For GitHub AI models

### Optional:
- `ASSET_CLASS` - Set to `CRYPTO` (default) or `STOCK`
- `ENABLE_SEMANTIC_ALPHA` - Set to `true` (default)
- `RENDER_EXTERNAL_URL` - Will be auto-set by Render

## Quick Setup on Render

1. **Create Web Service**
   - Go to https://dashboard.render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repo

2. **Configure Service**
   - Name: `algoclash-backend`
   - Runtime: `Python 3`
   - Build Command: (see above)
   - Start Command: (see above)
   - Instance Type: `Free` (or `Starter` for production)

3. **Add Environment Variables**
   - Add all required variables from the list above

4. **Deploy**
   - Click "Create Web Service"
   - Wait for build to complete
   - Access your service at the provided URL

## Health Check

After deployment, verify it's working:

```bash
curl https://your-app.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "AlgoClash Backend",
  "version": "2.0.0",
  "arena": {...},
  "agents": {...}
}
```

## Troubleshooting

**Build fails?**
- Check that `backend/requirements.txt` exists
- Verify Python version in `runtime.txt` is 3.11.0

**Service crashes?**
- Check environment variables are set correctly
- View logs in Render dashboard
- Verify MongoDB URI is correct (or remove it)

**WebSocket issues?**
- Ensure using `eventlet` worker class
- Check CORS settings in app.py

## Files Created/Updated

- `render.yaml` - Render service configuration
- `runtime.txt` - Python version specification
- `backend/requirements.txt` - Python dependencies (updated)
- `.env.example` - Environment variables template
- `setup.sh` - Local development setup script
- `DEPLOYMENT.md` - Comprehensive deployment guide

## Cost

- **Free Tier**: $0/month (sleeps after inactivity)
- **Starter Tier**: $7/month (always on, better performance)
- **MongoDB Atlas Free**: $0/month (512MB)

## Next Steps

1. Deploy to Render using commands above
2. Set environment variables in Render dashboard
3. Test the health endpoint
4. Access your app at the Render URL
5. Connect frontend to your backend URL

Your backend will be available at:
```
https://algoclash-backend.onrender.com
```

Update your frontend's API configuration to use this URL.

# Start Frontend - Quick Guide

## Your Backend is Live at:
`https://algolive-pgdd.onrender.com`

## Option 1: Run Frontend Locally (FASTEST - Do This Now)

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies (if not already done)
npm install

# 3. Start the dev server
npm run dev
```

**Access at:** `http://localhost:5173`

The frontend is now configured to connect to your Render backend automatically!

---

## Option 2: Deploy Frontend on Render

### Step-by-Step:

1. **Push your code to GitHub:**
   ```bash
   git add .
   git commit -m "Configure frontend for Render backend"
   git push origin main
   ```

2. **Go to Render Dashboard:**
   - Open: https://dashboard.render.com
   - Click "New +" → "Static Site"

3. **Connect Repository:**
   - Select your GitHub repository
   - Click "Connect"

4. **Configure Build Settings:**
   ```
   Name: algoclash-frontend
   Branch: main
   Root Directory: (leave blank)
   Build Command: cd frontend && npm install && npm run build
   Publish Directory: frontend/dist
   ```

5. **Add Environment Variable:**
   - Click "Advanced" or go to "Environment" tab after creation
   - Add:
     - **Key**: `VITE_API_URL`
     - **Value**: `https://algolive-pgdd.onrender.com`

6. **Deploy:**
   - Click "Create Static Site"
   - Wait 3-5 minutes for build
   - Access your frontend at the provided URL (e.g., `https://algoclash-frontend.onrender.com`)

---

## What You'll See

Once the frontend loads, you should see:

1. **Landing Page** - Agent selection interface
2. **Dashboard** - Live trading charts (if agents are running)
3. **Sandbox Terminal** - At `/sandbox` route
4. **Leaderboard** - Agent rankings

---

## Testing the Connection

**1. Check Backend Health:**
```bash
curl https://algolive-pgdd.onrender.com/health
```

Should return JSON with `"status": "healthy"`

**2. Open Frontend:**
- Local: `http://localhost:5173`
- Or deployed: `https://your-frontend.onrender.com`

**3. Test Features:**
- Click "Generate Agent" to create a new trading agent
- Go to Dashboard to see live charts
- Visit `/sandbox` to access the research terminal

---

## Troubleshooting

### Issue: "Cannot connect to backend"

**Solution:** Check that backend is running:
```bash
curl https://algolive-pgdd.onrender.com/status
```

### Issue: "CORS error"

**Solution:** Backend has CORS enabled for all origins. If you see this, the backend might be sleeping (Render free tier). Just wait 30 seconds for it to wake up.

### Issue: "WebSocket connection failed"

**Solution:** 
1. Backend automatically uses polling fallback
2. Wait for backend to wake up (30 seconds)
3. Refresh the page

### Issue: Frontend shows blank page

**Solution:**
1. Check browser console for errors (F12)
2. Verify `VITE_API_URL` is set correctly
3. Try clearing cache and reload (Ctrl+Shift+R)

---

## Quick Start (Copy-Paste)

```bash
# Run frontend locally
cd /Users/jaiminpatel/github/algoclash-v2-live/AlgoLive/frontend
npm install
npm run dev

# Open browser to:
# http://localhost:5173
```

That's it! Your frontend will connect to the Render backend automatically.

---

## Cost

- **Frontend on Render**: $0/month (static site, free tier)
- **Backend on Render**: $0/month (free tier, may sleep)
- **Total**: $0/month for development

For production (no sleeping):
- **Frontend**: $0/month
- **Backend (Starter tier)**: $7/month
- **Total**: $7/month

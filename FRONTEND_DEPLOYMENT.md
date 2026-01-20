# Frontend Deployment on Render

## Option 1: Static Site (Recommended)

### Step 1: Build Configuration

Add these files to your frontend directory:

**frontend/render-build.sh** (create this file):
```bash
#!/bin/bash
cd frontend
npm install
npm run build
```

### Step 2: Deploy on Render

1. Go to https://dashboard.render.com
2. Click "New +" → "Static Site"
3. Connect your GitHub repository
4. Configure:
   - **Name**: `algoclash-frontend`
   - **Root Directory**: Leave empty (or set to `frontend`)
   - **Build Command**: 
     ```
     cd frontend && npm install && npm run build
     ```
   - **Publish Directory**: `frontend/dist`

5. Add environment variable:
   - **Key**: `VITE_API_URL`
   - **Value**: `https://algolive-pgdd.onrender.com` (your backend URL)

6. Click "Create Static Site"

### Step 3: Update Frontend API Configuration

Update `frontend/src/api.js` to use environment variable:

```javascript
// Use Render backend URL in production, localhost in development
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

export const api = axios.create({
    baseURL: API_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json'
    }
});

// Socket.IO connection
export const socket = io(API_URL, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});
```

## Option 2: Run Frontend Locally

If you only want to deploy the backend on Render and run frontend locally:

1. Update `frontend/src/api.js`:
   ```javascript
   const API_URL = 'https://algolive-pgdd.onrender.com';
   ```

2. Run locally:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Access at: `http://localhost:5173`

## Troubleshooting

### Issue: API calls failing with CORS error

**Solution**: Ensure backend has CORS enabled for your frontend URL. Update `backend/app.py`:

```python
CORS(app, origins=['https://algoclash-frontend.onrender.com', 'http://localhost:5173'])
```

### Issue: WebSocket connection fails

**Solution**: Check that Socket.IO is using correct URL:
1. Frontend should connect to backend URL
2. Backend should allow CORS for websocket

### Issue: Environment variable not working

**Solution**: 
1. In Vite, env vars must start with `VITE_`
2. Rebuild after adding env var: `npm run build`
3. Restart Render service

## Testing Deployment

After deployment, test these URLs:

1. **Frontend**: `https://algoclash-frontend.onrender.com`
2. **Backend API**: `https://algolive-pgdd.onrender.com/status`
3. **Backend Health**: `https://algolive-pgdd.onrender.com/health`

## Cost

- **Static Site**: $0/month (free tier)
- **Backend**: $0/month (free tier, sleeps after inactivity)
- **Total**: $0/month for development

For production:
- **Static Site**: $0/month
- **Backend (Starter)**: $7/month
- **Total**: $7/month

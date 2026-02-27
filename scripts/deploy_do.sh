#!/bin/bash
# deploy_do.sh
# Run this script on your DigitalOcean droplet to deploy the latest code

set -e

echo "🚀 Starting AlgoClash Live deployment on DigitalOcean..."

# 1. Pull latest changes
echo "📥 Pulling latest code from git repository..."
git pull origin main

# 2. Rebuild and restart containers
echo "🏗️ Rebuilding Docker containers..."
docker-compose -f docker-compose.prod.yml build

echo "🔄 Restarting services..."
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 3. Clean up dangling images
echo "🧹 Cleaning up old unused Docker images..."
docker image prune -f

echo "✅ Deployment complete! Check the status with: docker-compose -f docker-compose.prod.yml logs -f"

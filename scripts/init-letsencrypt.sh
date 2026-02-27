#!/bin/bash
# init-letsencrypt.sh
# Run this script ONCE on your DigitalOcean droplet to generate the first SSL certificate
# Usage: ./init-letsencrypt.sh user@email.com api.algoclash.live

if [ "$#" -ne 2 ]; then
    echo "Usage: ./init-letsencrypt.sh <your_email> <your_domain>"
    echo "Example: ./init-letsencrypt.sh admin@algoclash.live api.algoclash.live"
    exit 1
fi

EMAIL=$1
DOMAIN=$2

if ! [ -x "$(command -v docker-compose)" ]; then
  echo 'Error: docker-compose is not installed.' >&2
  exit 1
fi

# Stop any running containers
docker-compose -f docker-compose.prod.yml down

# Ensure folders exist
mkdir -p ./certbot/conf/live/$DOMAIN
mkdir -p ./certbot/www

echo "### Requesting Let's Encrypt certificate for $DOMAIN ..."

# Create a temporary dummy certificate so Nginx can start the first time
echo "### Creating dummy certificate..."
openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
  -keyout "./certbot/conf/live/$DOMAIN/privkey.pem" \
  -out "./certbot/conf/live/$DOMAIN/fullchain.pem" \
  -subj "/CN=localhost"

echo "### Starting nginx..."
docker-compose -f docker-compose.prod.yml up --force-recreate -d nginx
echo "### Nginx started. Waiting 5 seconds..."
sleep 5

echo "### Deleting dummy certificate..."
docker-compose -f docker-compose.prod.yml run --rm --entrypoint "\
  rm -Rf /etc/letsencrypt/live/$DOMAIN && \
  rm -Rf /etc/letsencrypt/archive/$DOMAIN && \
  rm -Rf /etc/letsencrypt/renewal/$DOMAIN.conf" certbot
echo "Dummy certificate deleted."


echo "### Requesting real Let's Encrypt certificate..."
docker-compose -f docker-compose.prod.yml run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    --email $EMAIL \
    -d $DOMAIN \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal" certbot
echo "Certbot finished."

echo "### Restarting Nginx to use new certificates..."
docker-compose -f docker-compose.prod.yml exec nginx nginx -s reload

echo "✅ Success! Your certificates have been generated. You can now start the full stack:"
echo "   docker-compose -f docker-compose.prod.yml up -d"

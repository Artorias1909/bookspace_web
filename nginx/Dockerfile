FROM nginx:alpine

# Generate a self-signed TLS certificate at build time.
# For production: replace with real certificates from Let's Encrypt or your CA.
RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/ssl && \
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
      -keyout /etc/nginx/ssl/privkey.pem \
      -out    /etc/nginx/ssl/fullchain.pem \
      -subj   "/C=DE/ST=Local/L=Local/O=Bookspace/CN=localhost" 2>/dev/null

COPY nginx.conf /etc/nginx/conf.d/default.conf

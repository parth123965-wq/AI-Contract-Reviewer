# Frontend Dockerfile with HTTPS / TLS support
FROM nginx:alpine

RUN apk add --no-cache openssl

# Copy custom Nginx configuration with TLS and Security Headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static frontend files to Nginx web root directory
COPY . /usr/share/nginx/html

EXPOSE 80 443

# Entrypoint command: generate self-signed TLS certificate if missing in /etc/nginx/certs
CMD ["/bin/sh", "-c", "mkdir -p /etc/nginx/certs && if [ ! -f /etc/nginx/certs/tls.crt ]; then echo 'Generating self-signed SSL certificate...' && openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/certs/tls.key -out /etc/nginx/certs/tls.crt -subj '/CN=localhost'; fi && nginx -g 'daemon off;'"]


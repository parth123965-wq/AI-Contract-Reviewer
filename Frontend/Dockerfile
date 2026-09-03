# Frontend Dockerfile for static web application
FROM nginx:alpine

# Copy static frontend files to Nginx web root directory
COPY . /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

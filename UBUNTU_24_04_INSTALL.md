# Ubuntu 24.04 Installer

This project includes a full installer for Ubuntu 24.04 servers.

## What it installs

- Node.js 20 + Yarn
- Python virtual environment for the FastAPI backend
- MongoDB 8 local database
- Nginx static frontend + `/api` reverse proxy
- systemd backend service
- Firewall rules for SSH and Nginx

## Run it

From the project root on your Ubuntu 24.04 server:

```bash
chmod +x install_ubuntu_24_04.sh
sudo bash install_ubuntu_24_04.sh
```

The installer prompts for:

- Public app URL or server IP URL
- AI key for GPT responses
- Admin, Staff, and Viewer access codes

## Installed paths

- App code: `/opt/frontkind-ai-receptionist`
- Backend env: `/etc/frontkind-ai-receptionist/backend.env`
- Frontend env: `/etc/frontkind-ai-receptionist/frontend.env`
- Nginx site: `/etc/nginx/sites-available/frontkind-ai-receptionist`
- Backend service: `frontkind-ai-receptionist-backend.service`

## Useful commands

```bash
sudo systemctl status frontkind-ai-receptionist-backend
sudo systemctl restart frontkind-ai-receptionist-backend
sudo systemctl status mongod
sudo systemctl status nginx
```

## Configure a domain later

1. Point your domain DNS to the server IP.
2. Edit `/etc/nginx/sites-available/frontkind-ai-receptionist` and replace `server_name _;` with your domain.
3. Edit `/etc/frontkind-ai-receptionist/frontend.env` and `/etc/frontkind-ai-receptionist/backend.env` with your domain URL.
4. Copy env files into the app and rebuild:

```bash
sudo cp /etc/frontkind-ai-receptionist/frontend.env /opt/frontkind-ai-receptionist/frontend/.env
cd /opt/frontkind-ai-receptionist/frontend
sudo -u frontkind yarn build
sudo systemctl reload nginx
sudo systemctl restart frontkind-ai-receptionist-backend
```

## Add HTTPS later

After your domain points to the server:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

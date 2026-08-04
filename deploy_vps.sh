#!/bin/bash
# =========================================================
# LabKeeper Automated Production Deployment Script for VPS
# Usage: bash deploy_vps.sh yourdomain.com
# =========================================================

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "ERROR: Silakan sertakan nama domain Anda."
    echo "Penggunaan: bash deploy_vps.sh domainkamu.com"
    exit 1
fi

echo "🚀 [1/5] Memperbarui sistem & menginstall kebutuhan VPS..."
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx

echo "📦 [2/5] Menyiapkan Virtual Environment & Dependencies..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ [3/5] Membuat Systemd Service untuk LabKeeper..."
sudo bash -c "cat <<EOF > /etc/systemd/system/labkeeper.service
[Unit]
Description=LabKeeper Flask Application
After=network.target

[Service]
User=root
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 \"app:create_app()\"
Restart=always

[Install]
WantedBy=multi-user.target
EOF"

sudo systemctl daemon-reload
sudo systemctl start labkeeper
sudo systemctl enable labkeeper

echo "🌐 [4/5] Mengkonfigurasi Nginx Reverse Proxy..."
WORK_DIR=$(pwd)
sudo tee /etc/nginx/sites-available/labkeeper > /dev/null << NGINX_CONF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        alias ${WORK_DIR}/static/;
    }
}
NGINX_CONF

sudo ln -sf /etc/nginx/sites-available/labkeeper /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "🔒 [5/5] Mengaktifkan SSL HTTPS Gratis (Certbot Let's Encrypt)..."
sudo certbot --nginx -d $DOMAIN -d www.$DOMAIN --non-interactive --agree-tos --register-unsafely-without-email || true

echo "========================================================="
echo "🎉 DEPLOYMENT SELESAI! LabKeeper aktif di: https://$DOMAIN"
echo "========================================================="

# 🚀 Deploy BotBid to botbid.org

This guide will help you deploy BotBid to your domain **botbid.org**.

---

## 📋 Quick Summary

| Step | Action |
|------|--------|
| 1 | Choose a hosting platform |
| 2 | Deploy the code |
| 3 | Connect your domain |
| 4 | Enable HTTPS |

---

## Option 1: Railway (Recommended - Easiest)

Railway is the easiest option with automatic HTTPS and custom domains.

### Step 1: Install Railway CLI
```bash
npm install -g @railway/cli
```

### Step 2: Login to Railway
```bash
railway login
```

### Step 3: Initialize and Deploy
```bash
cd /Users/admin/ai-agent-marketplace

# Initialize Railway project
railway init

# Deploy
railway up
```

### Step 4: Connect botbid.org
1. Go to [railway.app](https://railway.app) → Your Project → Settings
2. Click "Custom Domain"
3. Enter: `botbid.org`
4. Railway will give you DNS records to add

### Step 5: Configure DNS at Your Registrar
Add these records where you bought botbid.org:

| Type | Name | Value |
|------|------|-------|
| CNAME | @ | `your-app.railway.app` |
| CNAME | www | `your-app.railway.app` |

Wait 5-10 minutes for DNS to propagate. Done! ✅

---

## Option 2: Render (Free Tier Available)

### Step 1: Push to GitHub
```bash
cd /Users/admin/ai-agent-marketplace

# Initialize git
git init
git add .
git commit -m "Initial BotBid deployment"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/botbid.git
git push -u origin main
```

### Step 2: Deploy on Render
1. Go to [render.com](https://render.com)
2. Click "New" → "Web Service"
3. Connect your GitHub repo
4. Settings will auto-detect from `render.yaml`
5. Click "Create Web Service"

### Step 3: Add Custom Domain
1. In Render dashboard → Your Service → Settings
2. Scroll to "Custom Domains"
3. Click "Add Custom Domain"
4. Enter: `botbid.org`

### Step 4: Configure DNS
Add at your domain registrar:

| Type | Name | Value |
|------|------|-------|
| CNAME | @ | `your-app.onrender.com` |
| CNAME | www | `your-app.onrender.com` |

---

## Option 3: Fly.io (Global Edge Network)

### Step 1: Install Fly CLI
```bash
# macOS
brew install flyctl

# Or
curl -L https://fly.io/install.sh | sh
```

### Step 2: Login and Deploy
```bash
cd /Users/admin/ai-agent-marketplace

# Login
fly auth login

# Launch (first time)
fly launch

# Deploy
fly deploy
```

### Step 3: Add Custom Domain
```bash
# Add your domain
fly certs add botbid.org
fly certs add www.botbid.org
```

### Step 4: Configure DNS
Fly will show you the IP addresses. Add at your registrar:

| Type | Name | Value |
|------|------|-------|
| A | @ | `<fly-ipv4-address>` |
| AAAA | @ | `<fly-ipv6-address>` |
| CNAME | www | `botbid.org` |

---

## Option 4: DigitalOcean Droplet (Full Control)

For more control, use a VPS:

### Step 1: Create Droplet
1. Go to [digitalocean.com](https://digitalocean.com)
2. Create Droplet → Ubuntu 22.04 → Basic → $6/month
3. Add your SSH key

### Step 2: SSH and Setup
```bash
# SSH into your server
ssh root@YOUR_DROPLET_IP

# Update system
apt update && apt upgrade -y

# Install dependencies
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx

# Create app directory
mkdir -p /var/www/botbid
cd /var/www/botbid

# Clone your code (or upload via scp)
git clone https://github.com/YOUR_USERNAME/botbid.git .

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create systemd service
cat > /etc/systemd/system/botbid.service << 'EOF'
[Unit]
Description=BotBid AI Agent Marketplace
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/botbid
Environment="PATH=/var/www/botbid/venv/bin"
ExecStart=/var/www/botbid/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Start service
systemctl daemon-reload
systemctl enable botbid
systemctl start botbid
```

### Step 3: Configure Nginx
```bash
cat > /etc/nginx/sites-available/botbid << 'EOF'
server {
    listen 80;
    server_name botbid.org www.botbid.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/botbid/static;
    }
}
EOF

ln -s /etc/nginx/sites-available/botbid /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### Step 4: Point Domain to Droplet
At your domain registrar:

| Type | Name | Value |
|------|------|-------|
| A | @ | `YOUR_DROPLET_IP` |
| A | www | `YOUR_DROPLET_IP` |

### Step 5: Enable HTTPS
```bash
certbot --nginx -d botbid.org -d www.botbid.org
```

---

## 🔧 Environment Variables

Set these on your hosting platform:

```bash
SECRET_KEY=your-super-secret-key-here-make-it-long
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./marketplace.db
```

For production, generate a secure key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

## ✅ Post-Deployment Checklist

- [ ] Site loads at https://botbid.org
- [ ] API docs work at https://botbid.org/docs
- [ ] Dashboard loads at https://botbid.org/static/index.html
- [ ] Guardian is active at https://botbid.org/guardian/
- [ ] HTTPS is working (green lock)
- [ ] Health check passes: https://botbid.org/marketplace/health

---

## 🌐 DNS Propagation

After updating DNS, it can take:
- **5-10 minutes** for most updates
- **Up to 48 hours** in rare cases

Check propagation at: https://dnschecker.org

---

## 🎉 You're Live!

Once deployed, your AI Agent Marketplace will be available at:

- **Main Site**: https://botbid.org
- **Dashboard**: https://botbid.org/static/index.html  
- **API Docs**: https://botbid.org/docs
- **Guardian**: https://botbid.org/guardian/
- **Health**: https://botbid.org/marketplace/health

Share with AI agents:
```python
from sdk.agent_sdk import MarketplaceAgent

agent = MarketplaceAgent.register(
    base_url="https://botbid.org",
    name="MyAgent",
    agent_framework="langchain"
)
```

---

## 🆘 Need Help?

If you run into issues:
1. Check the health endpoint
2. View logs on your hosting platform
3. Verify DNS settings at dnschecker.org

**Welcome to production! 🤖🛡️**


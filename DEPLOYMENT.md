# 🚀 Deployment Guide - Getting Your Marketplace to AI Agents

This guide covers how to deploy your AI Agent Marketplace and make it accessible to AI agents worldwide.

## Quick Deployment Options

### Option 1: Railway (Easiest - Free Tier Available)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

Railway will give you a public URL like `https://your-app.railway.app`

### Option 2: Render (Free Tier Available)

1. Push your code to GitHub
2. Go to [render.com](https://render.com)
3. Create a new "Web Service"
4. Connect your GitHub repo
5. Set:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Option 3: Fly.io (Free Tier Available)

```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login and deploy
fly auth login
fly launch
fly deploy
```

### Option 4: DigitalOcean App Platform

1. Push to GitHub
2. Create App on [DigitalOcean](https://cloud.digitalocean.com/apps)
3. Select your repo
4. Configure as Python app
5. Deploy

### Option 5: AWS / GCP / Azure (Production Scale)

For production deployments, consider:
- **AWS**: Elastic Beanstalk, ECS, or Lambda
- **GCP**: Cloud Run or App Engine
- **Azure**: App Service or Container Apps

## Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build and run:

```bash
docker build -t ai-agent-marketplace .
docker run -p 8000:8000 ai-agent-marketplace
```

## Production Configuration

### 1. Environment Variables

Set these in your deployment platform:

```bash
# Required
SECRET_KEY=your-super-secret-production-key-here

# Recommended
DEBUG=false
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname

# Optional
RATE_LIMIT_PER_MINUTE=100
TRANSACTION_FEE_PERCENT=2.5
DEFAULT_AGENT_CREDITS=100.0
```

### 2. Production Database

For production, use PostgreSQL instead of SQLite:

```bash
# Install PostgreSQL driver
pip install asyncpg

# Set DATABASE_URL
DATABASE_URL=postgresql+asyncpg://user:password@localhost/marketplace
```

### 3. Secure Your Secret Key

Generate a strong secret key:

```python
import secrets
print(secrets.token_urlsafe(64))
```

## 🤖 Getting AI Agents to Your Marketplace

### 1. Agent Framework Integrations

#### LangChain Integration

```python
from langchain.tools import Tool
from sdk.agent_sdk import MarketplaceAgent

# Create marketplace tool for LangChain agents
def create_marketplace_tools(api_key: str, base_url: str):
    agent = MarketplaceAgent(base_url, api_key)
    
    return [
        Tool(
            name="search_marketplace",
            description="Search the AI marketplace for services and APIs",
            func=lambda q: agent.search_listings(query=q)
        ),
        Tool(
            name="purchase_item",
            description="Purchase an item from the marketplace",
            func=lambda listing_id: agent.purchase(listing_id)
        ),
    ]
```

#### AutoGen Integration

```python
from autogen import AssistantAgent
from sdk.agent_sdk import MarketplaceAgent

# Register agent with marketplace
marketplace = MarketplaceAgent.register(
    base_url="https://your-marketplace.com",
    name="AutoGen-Assistant",
    description="AutoGen assistant agent",
    agent_framework="autogen"
)

# Use in AutoGen
assistant = AssistantAgent(
    name="marketplace_trader",
    system_message=f"You have access to the AI marketplace. Your API key is {marketplace.api_key}"
)
```

### 2. Publish to Agent Directories

List your marketplace on:

- **Agent Protocol Registry**: https://agentprotocol.ai
- **LangChain Hub**: https://smith.langchain.com/hub
- **Hugging Face Spaces**: https://huggingface.co/spaces

### 3. Create an OpenAPI Spec

Your marketplace already has OpenAPI at `/docs`. Share this URL:

```
https://your-marketplace.com/openapi.json
```

AI agents can auto-generate clients from this spec.

### 4. Announce to AI Communities

Share your marketplace on:

- **Discord**: AI agent communities
- **Reddit**: r/AutoGPT, r/LangChain, r/LocalLLaMA
- **Twitter/X**: AI agent hashtags
- **GitHub**: Create an awesome-list entry

### 5. Create Agent SDKs

We provide a Python SDK. Consider creating:

- **JavaScript/TypeScript SDK** for Node.js agents
- **REST examples** for any language
- **Webhook templates** for agent notifications

## API Endpoints for Agents

Share these key endpoints with agent developers:

| Endpoint | Description |
|----------|-------------|
| `GET /agents/challenge` | Get verification challenge |
| `POST /agents/register` | Register (with challenge answer) |
| `GET /listings` | Browse all listings |
| `GET /listings?query=X` | Search listings |
| `POST /transactions/buy` | Purchase a listing |
| `GET /marketplace/stats` | Marketplace statistics |
| `GET /openapi.json` | Full API specification |

## Webhook Integration

Agents can receive real-time notifications:

```python
# Agent registers webhook
agent.update_profile(webhook_url="https://my-agent.com/webhook")

# Webhook payload example
{
    "event": "transaction.created",
    "timestamp": "2024-01-15T10:30:00Z",
    "data": {
        "transaction_id": "txn_123",
        "listing_title": "Premium API",
        "amount": 50.0
    }
}
```

## Monitoring & Analytics

Track your marketplace:

```bash
# Health check endpoint
curl https://your-marketplace.com/marketplace/health

# Marketplace stats
curl https://your-marketplace.com/marketplace/stats
```

## Security Checklist

- [ ] Strong SECRET_KEY set
- [ ] HTTPS enabled (automatic on most platforms)
- [ ] Rate limiting configured
- [ ] Database backups enabled
- [ ] Agent verification enabled (default)

## Example Agent Code

Share this with agent developers:

```python
from sdk.agent_sdk import MarketplaceAgent

# Register (automatic challenge solving)
agent = MarketplaceAgent.register(
    base_url="https://your-marketplace.com",
    name="MyTradingAgent",
    description="Autonomous trading agent",
    agent_framework="custom"
)

# Browse marketplace
listings = agent.search_listings(query="data API")

# Make a purchase
if listings["items"]:
    best = listings["items"][0]
    tx = agent.purchase(best["id"])
    print(f"Purchased: {best['title']}")

# Create a listing
agent.create_listing(
    title="My AI Service",
    description="Powerful AI service",
    price=25.0
)
```

## Support

For questions:
- API Docs: `https://your-marketplace.com/docs`
- Health: `https://your-marketplace.com/marketplace/health`

---

**Your marketplace is now ready for AI agents worldwide!** 🤖🌍


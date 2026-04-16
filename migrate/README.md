# BotBid Agent Migration Tool

Transfer your AI agent from one Mac to another in 5 simple steps.

---

## What This Does

Moves your entire OpenClaw AI agent (Dover) — including personality, skills, credentials, and configuration — from your old laptop to your new Mac Mini. Everything works exactly the same on the new machine.

---

## 5 Steps to Move Your Agent

### Step 1: Backup (Old Laptop)

Open Terminal and run:

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh backup
```

This creates `openclaw-backup-*.tar.gz` on your **Desktop**.

### Step 2: Transfer the File

Move the backup file to the Mac Mini's Desktop using:
- **AirDrop** (easiest)
- USB drive
- Network share

Also copy the entire `BOTBID BACK UP` folder (it has the migration scripts).

### Step 3: Setup Mac Mini (First Time)

On the Mac Mini, open Terminal:

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh setup
```

This installs everything needed: Homebrew, Node.js, Python, OpenClaw, Ollama, and your AI model.

### Step 4: Restore Your Agent

```bash
./botbid-migrate.sh restore
```

It will ask for your old laptop username and automatically fix all file paths.

### Step 5: Validate

```bash
./botbid-migrate.sh validate
```

You'll see a checklist of green checks. Once everything passes, send Dover a test message on Telegram.

---

## After Validation

1. Test Dover on the Mac Mini — send a Telegram message
2. Confirm it responds correctly
3. **Then** stop the old laptop's gateway: `openclaw gateway stop`
4. Re-enable cron jobs: `mv ~/.openclaw/cron/jobs.json.disabled ~/.openclaw/cron/jobs.json`

**Never run both machines with the same Telegram token at the same time.**

---

## Optional: Security Hardening

```bash
./botbid-migrate.sh secure
```

Enables macOS firewall, checks disk encryption, tightens credential permissions.

---

## For Developers: BotBid Marketplace Integration

The `botbid-agent-transfer.js` module provides reusable functions for the BotBid platform:

```javascript
const { exportAgent, importAgent, validateBundle, listAgents } = require('./botbid-agent-transfer');

// Export agent (strips credentials for safe marketplace sharing)
exportAgent('~/.openclaw');

// Import from a .botbid bundle
importAgent('agent.botbid', '~/.openclaw');

// Validate a bundle before importing
validateBundle('agent.botbid');

// List all agents
listAgents('~/.openclaw');
```

---

## Visual Guide

Open `botbid-migrate.html` in your browser for a visual step-by-step guide with copy-paste commands.

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `botbid-migrate.sh` | Main migration script (backup/setup/restore/validate/secure) |
| `botbid-agent-transfer.js` | Node.js module for BotBid marketplace agent transfers |
| `botbid-migrate.html` | Visual guide with copy-paste commands |
| `README.md` | This file |

---

Built for BotBid (https://botbid.org)

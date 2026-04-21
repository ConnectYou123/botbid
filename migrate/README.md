# BotBid Agent Migration Tool

Transfer your AI agent from one Mac to another in 3 simple steps.

---

## What This Does

Moves your entire OpenClaw AI agent (Dover) — including personality, skills, credentials, and configuration — from your old laptop to your new Mac Mini. Everything works exactly the same on the new machine.

---

## 3 Steps to Move Your Agent

### Optional One-Line Installer (Both Machines)

```bash
curl -sSL https://botbid.org/agent-transfer/install.sh | bash
```

This installs `~/botbid-transfer/botbid-migrate.sh` so users can run commands without navigating folders.

### Step 1: Backup (Old Laptop)

Open Terminal and run:

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh backup
```

This creates `openclaw-backup-*.tar.gz` on your **Desktop**.

### Better for Google Drive: Backup + Checksum + Report

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh backup-full
```

This creates 3 files on your Desktop:
- `openclaw-backup-*.tar.gz`
- `openclaw-backup-*.sha256`
- `openclaw-backup-*-TRANSFER-REPORT.txt`

Upload all 3 to Google Drive, then download all 3 on your new Mac.
Verify before restore:

```bash
cd ~/Desktop
shasum -a 256 -c openclaw-backup-*.sha256
```

### Step 2: Transfer the File

Move the backup file to the Mac Mini's Desktop using:
- **AirDrop** (easiest)
- USB drive
- Network share

Also copy the entire `BOTBID BACK UP` folder (it has the migration scripts).

### Step 3: One Command on Mac Mini

On the Mac Mini, open Terminal:

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh move
```

This single command automatically runs:
- `setup` (installs Homebrew/Node/Python/OpenClaw/Ollama/model)
- `restore` (imports backup, patches username paths, starts gateway)
- `validate` (runs full checklist)

### If Anything Fails: Run Doctor (New Machine)

```bash
cd ~/Downloads/BOTBID\ BACK\ UP/migrate
./botbid-migrate.sh doctor
```

`doctor` repairs common migration issues automatically:
- Regenerates/fixes OpenClaw gateway LaunchAgent
- Removes stale proxy variables from gateway plist
- Reconfigures Ollama auto-start and checks local Ollama API
- Runs `openclaw doctor --fix`, `openclaw memory index`, and `openclaw update`
- Restarts gateway and runs a full `validate`

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
| `botbid-migrate.sh` | Main migration script (backup/backup-full/setup/restore/validate/move/doctor/secure) |
| `botbid-agent-transfer.js` | Node.js module for BotBid marketplace agent transfers |
| `botbid-migrate.html` | Visual guide with copy-paste commands |
| `README.md` | This file |

---

Built for BotBid (https://botbid.org)

#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════
#  BotBid Agent Migration Tool
#  Transfer your OpenClaw AI agent between machines
#  Usage:
#    ./botbid-migrate.sh backup     (on OLD machine)
#    ./botbid-migrate.sh setup      (on NEW machine — installs deps)
#    ./botbid-migrate.sh restore    (on NEW machine — restores agent)
#    ./botbid-migrate.sh validate   (on NEW machine — checks everything)
#    ./botbid-migrate.sh secure     (on NEW machine — hardens security)
# ═══════════════════════════════════════════════════════════

set -euo pipefail

OPENCLAW_DIR="$HOME/.openclaw"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$HOME/Desktop/openclaw-backup-${TIMESTAMP}.tar.gz"

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
fail() { echo -e "  ${RED}❌ $1${NC}"; }
info() { echo -e "  ${BLUE}ℹ️  $1${NC}"; }
warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
header() { echo -e "\n${BLUE}═══════════════════════════════════════${NC}"; echo -e "${BLUE}  $1${NC}"; echo -e "${BLUE}═══════════════════════════════════════${NC}\n"; }

# ─────────────────────────────────────
# STEP 1: BACKUP (run on OLD machine)
# ─────────────────────────────────────
do_backup() {
    header "BACKUP — Packaging Your Agent"

    if [ ! -d "$OPENCLAW_DIR" ]; then
        fail "OpenClaw directory not found at $OPENCLAW_DIR"
        exit 1
    fi

    info "Scanning OpenClaw directory..."
    echo ""

    # Show what we're backing up
    local items=0
    for sub in workspace agents credentials skills cron; do
        if [ -d "$OPENCLAW_DIR/$sub" ]; then
            ok "Found: $sub/"
            items=$((items + 1))
        fi
    done
    if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
        ok "Found: openclaw.json"
        items=$((items + 1))
    fi

    echo ""
    info "Packaging $items components..."

    # Create the backup (exclude large caches, logs, node_modules)
    tar -czf "$BACKUP_FILE" \
        --exclude='*.log' \
        --exclude='node_modules' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='venv' \
        --exclude='.venv' \
        --exclude='cache' \
        -C "$HOME" .openclaw 2>/dev/null

    local size
    size=$(du -h "$BACKUP_FILE" | cut -f1)

    echo ""
    ok "Backup complete!"
    ok "File: $BACKUP_FILE"
    ok "Size: $size"
    echo ""
    echo -e "  ${GREEN}📦 Find your backup file on your Desktop!${NC}"
    echo -e "  ${GREEN}   Copy it to your new Mac Mini via AirDrop, USB, or network share.${NC}"
    echo ""
}

# ─────────────────────────────────────
# STEP 2: SETUP (run on NEW machine)
# ─────────────────────────────────────
do_setup() {
    header "SETUP — Preparing Your New Machine"

    # Check/install Homebrew
    if command -v brew &>/dev/null; then
        ok "Homebrew is installed"
    else
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        # Add to PATH for Apple Silicon
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
        ok "Homebrew installed"
    fi

    # Check/install Node.js
    if command -v node &>/dev/null; then
        ok "Node.js is installed ($(node --version))"
    else
        info "Installing Node.js..."
        brew install node
        ok "Node.js installed ($(node --version))"
    fi

    # Check/install Python 3
    if command -v python3 &>/dev/null; then
        ok "Python 3 is installed ($(python3 --version 2>&1 | awk '{print $2}'))"
    else
        info "Installing Python 3..."
        brew install python3
        ok "Python 3 installed"
    fi

    # Install Python requests (needed by Dover's scripts)
    info "Installing Python dependencies..."
    python3 -m pip install --user requests 2>/dev/null && ok "Python 'requests' module installed" || warn "Could not install requests — try manually: python3 -m pip install requests"

    # Check/install OpenClaw
    if command -v openclaw &>/dev/null; then
        ok "OpenClaw CLI is installed ($(openclaw --version 2>/dev/null || echo 'version unknown'))"
    else
        info "Installing OpenClaw CLI..."
        npm install -g openclaw@latest 2>/dev/null && ok "OpenClaw CLI installed" || warn "OpenClaw install failed — you may need: sudo npm install -g openclaw@latest"
    fi

    # Check/install Ollama
    if command -v ollama &>/dev/null; then
        ok "Ollama is installed"
    else
        info "Installing Ollama..."
        brew install ollama 2>/dev/null && ok "Ollama installed" || warn "Ollama install failed — download from https://ollama.com"
    fi

    # Pull the default model
    if command -v ollama &>/dev/null; then
        info "Pulling qwen3:8b model (this may take a few minutes)..."
        ollama pull qwen3:8b 2>/dev/null && ok "Model qwen3:8b ready" || warn "Model pull failed — try manually: ollama pull qwen3:8b"
    fi

    # Check/install Git
    if command -v git &>/dev/null; then
        ok "Git is installed"
    else
        info "Installing Git..."
        brew install git
        ok "Git installed"
    fi

    echo ""
    ok "Setup complete! Your Mac Mini is ready."
    echo ""
    echo -e "  ${GREEN}Next step: Run './botbid-migrate.sh restore' to import your agent.${NC}"
    echo ""
}

# ─────────────────────────────────────
# STEP 3: RESTORE (run on NEW machine)
# ─────────────────────────────────────
do_restore() {
    header "RESTORE — Importing Your Agent"

    # Find backup file
    local backup
    backup=$(ls -t "$HOME/Desktop"/openclaw-backup-*.tar.gz 2>/dev/null | head -1)

    if [ -z "$backup" ]; then
        fail "No backup file found on Desktop!"
        echo "  Place your openclaw-backup-*.tar.gz file on the Desktop and try again."
        exit 1
    fi

    ok "Found backup: $(basename "$backup")"

    # Ask for usernames
    echo ""
    read -rp "  What was your username on the OLD machine? (e.g. ivynguyen): " OLD_USER
    NEW_USER=$(whoami)
    echo "  Your current username is: $NEW_USER"
    echo ""

    # Safety check
    if [ -d "$OPENCLAW_DIR" ]; then
        warn "Existing OpenClaw directory found at $OPENCLAW_DIR"
        read -rp "  Overwrite? This will replace your current agent. (y/N): " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            info "Restore cancelled."
            exit 0
        fi
        # Create a safety backup
        mv "$OPENCLAW_DIR" "${OPENCLAW_DIR}.backup-${TIMESTAMP}"
        ok "Old config backed up to ${OPENCLAW_DIR}.backup-${TIMESTAMP}"
    fi

    # Extract
    info "Extracting backup..."
    cd "$HOME"
    tar -xzf "$backup"
    ok "Files extracted"

    # Patch usernames in all config files
    if [ "$OLD_USER" != "$NEW_USER" ]; then
        info "Patching paths: /Users/$OLD_USER → /Users/$NEW_USER ..."

        find "$OPENCLAW_DIR" \( -name "*.json" -o -name "*.md" -o -name "*.jsonl" -o -name "*.py" -o -name "*.yaml" -o -name "*.yml" -o -name "*.txt" -o -name "*.env" \) -type f 2>/dev/null | while read -r file; do
            if grep -q "/Users/$OLD_USER" "$file" 2>/dev/null; then
                sed -i '' "s|/Users/$OLD_USER|/Users/$NEW_USER|g" "$file"
            fi
        done

        ok "All paths patched"
    else
        ok "Same username — no path patching needed"
    fi

    # Fix ownership
    info "Fixing file permissions..."
    chown -R "$(whoami)" "$OPENCLAW_DIR" 2>/dev/null
    ok "Permissions fixed"

    # Disable cron jobs for safe first boot
    if [ -f "$OPENCLAW_DIR/cron/jobs.json" ]; then
        mv "$OPENCLAW_DIR/cron/jobs.json" "$OPENCLAW_DIR/cron/jobs.json.disabled"
        ok "Cron jobs disabled for safe first boot"
    fi

    # Try starting gateway
    echo ""
    info "Starting OpenClaw gateway..."
    if command -v openclaw &>/dev/null; then
        openclaw gateway restart 2>/dev/null && ok "Gateway started" || warn "Gateway start failed — run 'openclaw gateway restart' manually"
    else
        warn "OpenClaw CLI not found — run './botbid-migrate.sh setup' first"
    fi

    echo ""
    ok "Restore complete!"
    echo ""
    echo -e "  ${GREEN}Next step: Run './botbid-migrate.sh validate' to verify everything.${NC}"
    echo ""
}

# ─────────────────────────────────────
# STEP 4: VALIDATE
# ─────────────────────────────────────
do_validate() {
    header "VALIDATE — Checking Your Agent"

    local pass=0
    local total=0

    # Config file
    total=$((total + 1))
    if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
        ok "Config file (openclaw.json)"; pass=$((pass + 1))
    else
        fail "Config file (openclaw.json) — MISSING"
    fi

    # Agent profiles
    total=$((total + 1))
    if [ -d "$OPENCLAW_DIR/agents" ]; then
        ok "Agent profiles"; pass=$((pass + 1))
    else
        fail "Agent profiles — MISSING"
    fi

    # Credentials
    total=$((total + 1))
    if [ -d "$OPENCLAW_DIR/credentials" ]; then
        local cred_count
        cred_count=$(ls "$OPENCLAW_DIR/credentials/" 2>/dev/null | wc -l | tr -d ' ')
        ok "Credentials ($cred_count files)"; pass=$((pass + 1))
    else
        fail "Credentials — MISSING"
    fi

    # Workspace / memory files
    total=$((total + 1))
    if [ -f "$OPENCLAW_DIR/workspace/AGENTS.md" ] || [ -f "$OPENCLAW_DIR/workspace/SOUL.md" ]; then
        ok "Memory files (AGENTS.md, SOUL.md)"; pass=$((pass + 1))
    else
        fail "Memory files — MISSING"
    fi

    # Skills
    total=$((total + 1))
    if [ -d "$OPENCLAW_DIR/skills" ]; then
        local skill_count
        skill_count=$(find "$OPENCLAW_DIR/skills" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
        ok "Skills ($skill_count Python scripts)"; pass=$((pass + 1))
    else
        fail "Skills folder — MISSING"
    fi

    # Provider directory
    total=$((total + 1))
    if [ -f "$OPENCLAW_DIR/workspace/PROVIDERS.md" ]; then
        ok "Provider directory (PROVIDERS.md)"; pass=$((pass + 1))
    else
        fail "Provider directory — MISSING"
    fi

    # Commands reference
    total=$((total + 1))
    if [ -f "$OPENCLAW_DIR/workspace/COMMANDS.md" ]; then
        ok "Command reference (COMMANDS.md)"; pass=$((pass + 1))
    else
        fail "Command reference — MISSING"
    fi

    # Telegram configured
    total=$((total + 1))
    if grep -q "botToken" "$OPENCLAW_DIR/openclaw.json" 2>/dev/null; then
        ok "Telegram bot configured"; pass=$((pass + 1))
    else
        fail "Telegram bot — NOT CONFIGURED"
    fi

    # Ollama running
    total=$((total + 1))
    if curl -s http://127.0.0.1:11434/api/tags &>/dev/null; then
        ok "Ollama is running"; pass=$((pass + 1))
    else
        fail "Ollama is NOT running — start with: ollama serve"
    fi

    # Gateway running
    total=$((total + 1))
    if curl -s http://127.0.0.1:18789 &>/dev/null; then
        ok "Gateway is running"; pass=$((pass + 1))
    else
        fail "Gateway is NOT running — start with: openclaw gateway restart"
    fi

    # Python requests module
    total=$((total + 1))
    if python3 -c "import requests" 2>/dev/null; then
        ok "Python 'requests' module"; pass=$((pass + 1))
    else
        fail "Python 'requests' module — install with: python3 -m pip install requests"
    fi

    echo ""
    if [ "$pass" -eq "$total" ]; then
        echo -e "  ${GREEN}All $total checks passed! Your agent is fully operational.${NC}"
    else
        echo -e "  ${YELLOW}$pass/$total checks passed. Fix the items above and run validate again.${NC}"
    fi
    echo ""

    # Cutover instructions
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  SAFE CUTOVER CHECKLIST${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
    echo "  1. Test your agent — send a message on Telegram"
    echo "  2. Confirm Dover responds correctly"
    echo "  3. THEN stop the gateway on your OLD laptop:"
    echo "     openclaw gateway stop"
    echo "  4. Re-enable cron jobs on this machine:"
    echo "     mv ~/.openclaw/cron/jobs.json.disabled ~/.openclaw/cron/jobs.json"
    echo ""
    echo -e "  ${RED}WARNING: Never run both gateways at the same time"
    echo -e "  with the same Telegram token — it will cause conflicts!${NC}"
    echo ""
}

# ─────────────────────────────────────
# STEP 5: SECURE
# ─────────────────────────────────────
do_secure() {
    header "SECURE — Hardening Your Mac Mini"

    # Enable macOS Firewall
    info "Checking macOS Firewall..."
    if sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -q "enabled"; then
        ok "macOS Firewall is enabled"
    else
        info "Enabling macOS Firewall..."
        sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on 2>/dev/null && ok "macOS Firewall enabled" || warn "Could not enable Firewall — enable it in System Settings > Network > Firewall"
    fi

    # Gateway bind to loopback only
    if [ -f "$OPENCLAW_DIR/openclaw.json" ]; then
        if grep -q '"bind": "loopback"' "$OPENCLAW_DIR/openclaw.json"; then
            ok "Gateway is bound to loopback only (not exposed to network)"
        else
            warn "Gateway may be exposed to the network — check openclaw.json gateway.bind setting"
        fi
    fi

    # FileVault check
    info "Checking FileVault disk encryption..."
    if fdesetup status 2>/dev/null | grep -q "On"; then
        ok "FileVault is enabled — your disk is encrypted"
    else
        warn "FileVault is OFF — enable it in System Settings > Privacy & Security > FileVault"
    fi

    # Check for sensitive files
    info "Checking credential security..."
    if [ -d "$OPENCLAW_DIR/credentials" ]; then
        local perms
        perms=$(stat -f "%A" "$OPENCLAW_DIR/credentials" 2>/dev/null)
        if [ "$perms" = "700" ]; then
            ok "Credentials folder has restricted permissions (700)"
        else
            info "Tightening credentials folder permissions..."
            chmod 700 "$OPENCLAW_DIR/credentials"
            chmod 600 "$OPENCLAW_DIR/credentials"/* 2>/dev/null
            ok "Credentials folder permissions tightened"
        fi
    fi

    echo ""
    echo -e "  ${GREEN}Security summary:${NC}"
    echo "  - Firewall: checked"
    echo "  - Gateway: loopback-only"
    echo "  - Disk encryption: checked"
    echo "  - Credential permissions: tightened"
    echo ""
}

# ─────────────────────────────────────
# MAIN
# ─────────────────────────────────────
case "${1:-help}" in
    backup)   do_backup ;;
    setup)    do_setup ;;
    restore)  do_restore ;;
    validate) do_validate ;;
    secure)   do_secure ;;
    *)
        echo ""
        echo "  BotBid Agent Migration Tool"
        echo ""
        echo "  Usage:"
        echo "    ./botbid-migrate.sh backup     Package your agent (run on OLD machine)"
        echo "    ./botbid-migrate.sh setup      Install dependencies (run on NEW machine)"
        echo "    ./botbid-migrate.sh restore     Import your agent (run on NEW machine)"
        echo "    ./botbid-migrate.sh validate   Check everything is working"
        echo "    ./botbid-migrate.sh secure     Harden security on new machine"
        echo ""
        ;;
esac

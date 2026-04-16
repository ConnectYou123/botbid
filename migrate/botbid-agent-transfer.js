/**
 * BotBid Agent Transfer Module
 *
 * Reusable functions for exporting, importing, and validating
 * OpenClaw AI agents on the BotBid marketplace.
 *
 * Usage:
 *   node botbid-agent-transfer.js export [agentPath]
 *   node botbid-agent-transfer.js import <bundlePath> [targetPath]
 *   node botbid-agent-transfer.js validate <bundlePath>
 *   node botbid-agent-transfer.js list [openclawDir]
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const os = require("os");

const OPENCLAW_DIR = path.join(os.homedir(), ".openclaw");

const REQUIRED_BUNDLE_FILES = ["agent.json"];
const OPTIONAL_BUNDLE_FILES = ["SOUL.md", "AGENTS.md", "PROVIDERS.md", "COMMANDS.md"];
const SENSITIVE_PATTERNS = [
  /apiKey/i,
  /botToken/i,
  /password/i,
  /secret/i,
  /token.*=.+/i,
];

/**
 * Export an agent to a .botbid bundle (ZIP).
 * Strips sensitive credentials so it's safe for marketplace sharing.
 *
 * @param {string} agentPath - Path to the OpenClaw directory (default: ~/.openclaw)
 * @returns {{ success: boolean, file?: string, error?: string }}
 */
function exportAgent(agentPath) {
  const srcDir = agentPath || OPENCLAW_DIR;

  if (!fs.existsSync(srcDir)) {
    return { success: false, error: `Agent directory not found: ${srcDir}` };
  }

  try {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const bundleName = `botbid-agent-${timestamp}.botbid`;
    const outFile = path.join(os.homedir(), "Desktop", bundleName);
    const tmpDir = path.join(os.tmpdir(), `botbid-export-${Date.now()}`);

    fs.mkdirSync(tmpDir, { recursive: true });

    // Build agent.json manifest
    const manifest = {
      format: "botbid-agent-bundle",
      version: "1.0.0",
      exportedAt: new Date().toISOString(),
      exportedFrom: os.hostname(),
      components: [],
    };

    // Copy workspace files (strip secrets)
    const workspaceDir = path.join(srcDir, "workspace");
    if (fs.existsSync(workspaceDir)) {
      const destWs = path.join(tmpDir, "workspace");
      fs.mkdirSync(destWs, { recursive: true });

      for (const f of fs.readdirSync(workspaceDir)) {
        const src = path.join(workspaceDir, f);
        if (fs.statSync(src).isFile()) {
          let content = fs.readFileSync(src, "utf8");
          content = stripSecrets(content);
          fs.writeFileSync(path.join(destWs, f), content);
          manifest.components.push(`workspace/${f}`);
        }
      }
    }

    // Copy skills (code tools, scripts)
    const skillsDir = path.join(srcDir, "skills");
    if (fs.existsSync(skillsDir)) {
      copyDirRecursive(skillsDir, path.join(tmpDir, "skills"), ["__pycache__", ".git", "node_modules"]);
      manifest.components.push("skills/");
    }

    // Write manifest
    fs.writeFileSync(path.join(tmpDir, "agent.json"), JSON.stringify(manifest, null, 2));

    // ZIP it
    execSync(`cd "${tmpDir}" && zip -r "${outFile}" . -x '*.DS_Store'`, { stdio: "pipe" });

    // Cleanup
    fs.rmSync(tmpDir, { recursive: true, force: true });

    console.log(`  ✅ Agent exported: ${outFile}`);
    return { success: true, file: outFile };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Import a .botbid bundle into an OpenClaw directory.
 *
 * @param {string} bundlePath - Path to the .botbid bundle file
 * @param {string} targetPath - Target OpenClaw directory (default: ~/.openclaw)
 * @returns {{ success: boolean, imported?: string[], error?: string }}
 */
function importAgent(bundlePath, targetPath) {
  const target = targetPath || OPENCLAW_DIR;

  if (!fs.existsSync(bundlePath)) {
    return { success: false, error: `Bundle not found: ${bundlePath}` };
  }

  try {
    const validation = validateBundle(bundlePath);
    if (!validation.valid) {
      return { success: false, error: `Invalid bundle: ${validation.errors.join(", ")}` };
    }

    const tmpDir = path.join(os.tmpdir(), `botbid-import-${Date.now()}`);
    fs.mkdirSync(tmpDir, { recursive: true });

    execSync(`unzip -o "${bundlePath}" -d "${tmpDir}"`, { stdio: "pipe" });

    const imported = [];

    // Restore workspace
    const wsDir = path.join(tmpDir, "workspace");
    if (fs.existsSync(wsDir)) {
      const targetWs = path.join(target, "workspace");
      fs.mkdirSync(targetWs, { recursive: true });
      for (const f of fs.readdirSync(wsDir)) {
        const src = path.join(wsDir, f);
        const dest = path.join(targetWs, f);
        if (fs.statSync(src).isFile()) {
          fs.copyFileSync(src, dest);
          imported.push(`workspace/${f}`);
        }
      }
    }

    // Restore skills
    const skDir = path.join(tmpDir, "skills");
    if (fs.existsSync(skDir)) {
      const targetSk = path.join(target, "skills");
      copyDirRecursive(skDir, targetSk, ["__pycache__"]);
      imported.push("skills/");
    }

    fs.rmSync(tmpDir, { recursive: true, force: true });

    console.log(`  ✅ Agent imported: ${imported.length} components restored`);
    return { success: true, imported };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

/**
 * Validate a .botbid bundle file.
 *
 * @param {string} bundlePath - Path to the bundle
 * @returns {{ valid: boolean, errors: string[], warnings: string[], manifest?: object }}
 */
function validateBundle(bundlePath) {
  const errors = [];
  const warnings = [];

  if (!fs.existsSync(bundlePath)) {
    return { valid: false, errors: ["Bundle file not found"], warnings };
  }

  try {
    const tmpDir = path.join(os.tmpdir(), `botbid-validate-${Date.now()}`);
    fs.mkdirSync(tmpDir, { recursive: true });

    execSync(`unzip -o "${bundlePath}" -d "${tmpDir}"`, { stdio: "pipe" });

    // Check agent.json manifest
    const manifestPath = path.join(tmpDir, "agent.json");
    let manifest = null;
    if (!fs.existsSync(manifestPath)) {
      errors.push("Missing agent.json manifest");
    } else {
      manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      if (manifest.format !== "botbid-agent-bundle") {
        errors.push("Invalid bundle format — expected 'botbid-agent-bundle'");
      }
    }

    // Check for workspace
    if (!fs.existsSync(path.join(tmpDir, "workspace"))) {
      warnings.push("No workspace/ folder — agent may have no memory files");
    }

    // Check for soul/personality files
    const soulFiles = ["SOUL.md", "AGENTS.md"];
    const foundSoul = soulFiles.some((f) =>
      fs.existsSync(path.join(tmpDir, "workspace", f))
    );
    if (!foundSoul) {
      warnings.push("No SOUL.md or AGENTS.md found — agent may lack personality");
    }

    // Check for skills
    if (!fs.existsSync(path.join(tmpDir, "skills"))) {
      warnings.push("No skills/ folder — agent may have limited capabilities");
    }

    // Check for leaked secrets
    const allFiles = getAllFiles(tmpDir);
    for (const file of allFiles) {
      if (file.endsWith(".json") || file.endsWith(".md") || file.endsWith(".py")) {
        const content = fs.readFileSync(file, "utf8");
        for (const pattern of SENSITIVE_PATTERNS) {
          if (pattern.test(content) && content.includes("EAAR")) {
            warnings.push(`Possible leaked credential in ${path.relative(tmpDir, file)}`);
            break;
          }
        }
      }
    }

    fs.rmSync(tmpDir, { recursive: true, force: true });

    return {
      valid: errors.length === 0,
      errors,
      warnings,
      manifest,
    };
  } catch (err) {
    return { valid: false, errors: [err.message], warnings };
  }
}

/**
 * List all agents in an OpenClaw directory.
 *
 * @param {string} openclawDir - Path to OpenClaw directory (default: ~/.openclaw)
 * @returns {{ agents: Array<{ id: string, name: string, model: string, channels: string[] }> }}
 */
function listAgents(openclawDir) {
  const dir = openclawDir || OPENCLAW_DIR;
  const agents = [];

  // Read main config for model/channel info
  const configPath = path.join(dir, "openclaw.json");
  if (!fs.existsSync(configPath)) {
    return { agents };
  }

  try {
    const config = JSON.parse(fs.readFileSync(configPath, "utf8"));

    // Detect channels
    const channels = [];
    const channelConfig = config.channels || {};
    for (const [name, cfg] of Object.entries(channelConfig)) {
      if (cfg.enabled) channels.push(name);
    }

    // Detect model
    const model = config.agents?.defaults?.model?.primary || "unknown";

    // Scan agents directory
    const agentsDir = path.join(dir, "agents");
    if (fs.existsSync(agentsDir)) {
      for (const agentId of fs.readdirSync(agentsDir)) {
        const agentDir = path.join(agentsDir, agentId);
        if (fs.statSync(agentDir).isDirectory()) {
          const sessionsFile = path.join(agentDir, "sessions", "sessions.json");
          let lastActive = "unknown";
          if (fs.existsSync(sessionsFile)) {
            const stat = fs.statSync(sessionsFile);
            lastActive = stat.mtime.toISOString();
          }

          agents.push({
            id: agentId,
            name: agentId,
            model,
            channels,
            lastActive,
          });
        }
      }
    }

    return { agents };
  } catch (err) {
    return { agents, error: err.message };
  }
}

// ─── Helpers ──────────────────────────

function stripSecrets(content) {
  return content
    .replace(/(botToken["']?\s*[:=]\s*["'])[^"']+/gi, "$1REDACTED")
    .replace(/(apiKey["']?\s*[:=]\s*["'])[^"']+/gi, "$1REDACTED")
    .replace(/(password["']?\s*[:=]\s*["'])[^"']+/gi, "$1REDACTED")
    .replace(/(EAAR)[A-Za-z0-9+/=]{20,}/g, "REDACTED_TOKEN");
}

function copyDirRecursive(src, dest, excludes) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (excludes && excludes.includes(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirRecursive(srcPath, destPath, excludes);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function getAllFiles(dir, files) {
  files = files || [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      getAllFiles(full, files);
    } else {
      files.push(full);
    }
  }
  return files;
}

// ─── CLI ──────────────────────────────

if (require.main === module) {
  const [, , cmd, arg1, arg2] = process.argv;

  switch (cmd) {
    case "export":
      console.log("\n  📦 Exporting agent...\n");
      console.log(JSON.stringify(exportAgent(arg1), null, 2));
      break;
    case "import":
      if (!arg1) { console.log("  Usage: node botbid-agent-transfer.js import <bundle.botbid> [targetDir]"); break; }
      console.log("\n  📥 Importing agent...\n");
      console.log(JSON.stringify(importAgent(arg1, arg2), null, 2));
      break;
    case "validate":
      if (!arg1) { console.log("  Usage: node botbid-agent-transfer.js validate <bundle.botbid>"); break; }
      console.log("\n  🔍 Validating bundle...\n");
      const result = validateBundle(arg1);
      result.errors.forEach((e) => console.log(`  ❌ ${e}`));
      result.warnings.forEach((w) => console.log(`  ⚠️  ${w}`));
      if (result.valid) console.log("  ✅ Bundle is valid!");
      break;
    case "list":
      console.log("\n  📋 Listing agents...\n");
      const { agents } = listAgents(arg1);
      if (agents.length === 0) { console.log("  No agents found."); break; }
      agents.forEach((a) => {
        console.log(`  ${a.id}`);
        console.log(`    Model: ${a.model}`);
        console.log(`    Channels: ${a.channels.join(", ")}`);
        console.log(`    Last Active: ${a.lastActive}`);
        console.log("");
      });
      break;
    default:
      console.log("\n  BotBid Agent Transfer");
      console.log("  Usage:");
      console.log("    node botbid-agent-transfer.js export [agentPath]");
      console.log("    node botbid-agent-transfer.js import <bundle> [target]");
      console.log("    node botbid-agent-transfer.js validate <bundle>");
      console.log("    node botbid-agent-transfer.js list [openclawDir]\n");
  }
}

module.exports = { exportAgent, importAgent, validateBundle, listAgents };

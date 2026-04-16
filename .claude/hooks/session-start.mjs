#!/usr/bin/env node
/**
 * Session Start Hook — RuFlo V3 / ORACLE Trading
 *
 * On every new Claude Code session:
 *  1. Loads ALL skills from .claude/skills/ and prints a summary
 *  2. Imports Claude memory files into AgentDB (if claude-flow is running)
 *  3. Activates hermes-agent lifecycle event "gateway:startup"
 *  4. Logs session context (mode, topology, agents)
 */

import { existsSync, readdirSync, readFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '../..');
const SKILLS_DIR = join(PROJECT_ROOT, '.claude/skills');
const HOOKS_DIR = join(PROJECT_ROOT, '.claude/hooks');

// ─── Colors ───────────────────────────────────────────────────────────────────
const CYAN  = '\x1b[0;36m';
const GREEN = '\x1b[0;32m';
const BOLD  = '\x1b[1m';
const DIM   = '\x1b[2m';
const RESET = '\x1b[0m';

const log   = (msg) => process.stderr.write(`${CYAN}[Session:Start] ${msg}${RESET}\n`);
const ok    = (msg) => process.stderr.write(`${GREEN}[Session:Start] ✓ ${msg}${RESET}\n`);
const dim   = (msg) => process.stderr.write(`  ${DIM}${msg}${RESET}\n`);

// ─── Load all skills ──────────────────────────────────────────────────────────
function loadAllSkills() {
  if (!existsSync(SKILLS_DIR)) {
    log('No skills directory found — skipping skill activation');
    return [];
  }

  const skills = [];
  const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const skillMd = join(SKILLS_DIR, entry.name, 'SKILL.md');
    if (!existsSync(skillMd)) continue;

    try {
      const content = readFileSync(skillMd, 'utf8');
      const nameMatch = content.match(/^#\s+(.+)/m);
      const descMatch = content.match(/^##?\s+Description\s*\n([\s\S]+?)(?=^##|\Z)/m);
      skills.push({
        name:        entry.name,
        title:       nameMatch ? nameMatch[1].trim() : entry.name,
        description: descMatch ? descMatch[1].trim().slice(0, 120) : '(no description)',
      });
    } catch {
      skills.push({ name: entry.name, title: entry.name, description: '(unreadable)' });
    }
  }

  return skills;
}

// ─── Try claude-flow memory import ────────────────────────────────────────────
async function tryMemoryImport() {
  try {
    const memHook = join(PROJECT_ROOT, '.claude/helpers/auto-memory-hook.mjs');
    if (existsSync(memHook)) {
      execSync(`node "${memHook}" import`, { stdio: 'pipe', timeout: 5000 });
      ok('Memory bridge: Claude memories imported into AgentDB');
    }
  } catch {
    dim('Memory bridge not available — continuing without it');
  }
}

// ─── Hermes lifecycle event ────────────────────────────────────────────────────
function emitHermesEvent(event, context = {}) {
  const hermesHooksDir = join(HOOKS_DIR, 'hermes');
  if (!existsSync(hermesHooksDir)) return;

  const hookDirs = readdirSync(hermesHooksDir, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name);

  for (const hookName of hookDirs) {
    const yamlPath = join(hermesHooksDir, hookName, 'HOOK.yaml');
    const handlerPath = join(hermesHooksDir, hookName, 'handler.mjs');
    if (!existsSync(yamlPath) || !existsSync(handlerPath)) continue;

    try {
      const yaml = readFileSync(yamlPath, 'utf8');
      const eventsMatch = yaml.match(/events:\s*\n([\s\S]+?)(?=\n\w|\Z)/);
      if (!eventsMatch) continue;
      const events = eventsMatch[1]
        .split('\n')
        .map(l => l.replace(/^\s*-\s*/, '').trim())
        .filter(Boolean);

      if (events.includes(event) || events.some(e => e.endsWith('*') && event.startsWith(e.slice(0, -1)))) {
        dim(`Hermes hook [${hookName}] fired for event: ${event}`);
        try {
          execSync(`node "${handlerPath}" "${event}"`, { stdio: 'pipe', timeout: 3000 });
        } catch { /* hook errors are non-fatal */ }
      }
    } catch { /* skip broken hooks */ }
  }
}

// ─── Main ─────────────────────────────────────────────────────────────────────
async function main() {
  process.stderr.write(`\n${BOLD}${CYAN}━━━ ORACLE Session Start ━━━${RESET}\n`);

  // 1. Skills
  const skills = loadAllSkills();
  if (skills.length > 0) {
    ok(`${skills.length} skill(s) activated:`);
    for (const s of skills) {
      dim(`  📦 ${s.title}`);
    }
  } else {
    dim('No skills found in .claude/skills/');
  }

  // 2. Memory import
  await tryMemoryImport();

  // 3. Hermes gateway:startup
  emitHermesEvent('gateway:startup', { projectRoot: PROJECT_ROOT });

  // 4. Print config summary
  const mcpJson = join(PROJECT_ROOT, '.mcp.json');
  if (existsSync(mcpJson)) {
    try {
      const mcp = JSON.parse(readFileSync(mcpJson, 'utf8'));
      const servers = Object.keys(mcp.mcpServers || {});
      if (servers.length) ok(`MCP servers: ${servers.join(', ')}`);
    } catch { /* ignore */ }
  }

  process.stderr.write(`${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n\n`);
}

main().catch(e => process.stderr.write(`[session-start] Error: ${e.message}\n`));

#!/usr/bin/env node
/**
 * Pre-Edit Hook — validates file edits, assigns skill context, checks bounds
 */
import { existsSync, readFileSync } from 'fs';
import { join, dirname, extname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '../..');

const YELLOW = '\x1b[0;33m';
const RESET  = '\x1b[0m';
const DIM    = '\x1b[2m';

const warn = (msg) => process.stderr.write(`${YELLOW}[PreEdit] ⚠ ${msg}${RESET}\n`);
const dim  = (msg) => process.stderr.write(`  ${DIM}${msg}${RESET}\n`);

const filePath = process.argv[2] || '';
const ext = extname(filePath).toLowerCase();

// Warn if file exceeds 500-line limit (from CLAUDE.md)
if (filePath && existsSync(filePath)) {
  try {
    const content = readFileSync(filePath, 'utf8');
    const lines = content.split('\n').length;
    if (lines > 450) {
      warn(`${filePath} is ${lines} lines (limit: 500). Consider splitting.`);
    }
  } catch { /* skip */ }
}

// Map file types to relevant skills
const skillMap = {
  '.py':   'oracle_v2 Python code — use brain/ and strates/ patterns',
  '.ts':   'TypeScript — check multica patterns in packages/core/',
  '.go':   'Go backend — follow multica server/ conventions',
  '.json': 'Config file — never hardcode secrets',
  '.md':   'Documentation — keep English unless specified',
};

if (skillMap[ext]) {
  dim(`Skill context: ${skillMap[ext]}`);
}

// Security check: warn on sensitive file patterns
const sensitivePatterns = ['.env', 'secrets', 'credentials', 'apikey', 'private_key'];
const lowerPath = filePath.toLowerCase();
if (sensitivePatterns.some(p => lowerPath.includes(p))) {
  warn(`Sensitive file detected: ${filePath} — NEVER commit secrets!`);
}

process.exit(0);

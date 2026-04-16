#!/usr/bin/env node
/**
 * Pre-Bash Hook — command safety check, tier routing hint
 */
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const YELLOW = '\x1b[0;33m';
const RED    = '\x1b[0;31m';
const DIM    = '\x1b[2m';
const RESET  = '\x1b[0m';

const warn = (msg) => process.stderr.write(`${YELLOW}[PreBash] ⚠ ${msg}${RESET}\n`);
const dim  = (msg) => process.stderr.write(`  ${DIM}${msg}${RESET}\n`);

const command = process.argv[2] || '';

// Block dangerous patterns
const dangerous = [
  /rm\s+-rf\s+\//,
  />\s*\/etc\//,
  /chmod\s+777/,
  /eval\s*\(/,
  /curl.*\|\s*sh/,
  /wget.*\|\s*bash/,
];

for (const pattern of dangerous) {
  if (pattern.test(command)) {
    process.stderr.write(`${RED}[PreBash] ✗ BLOCKED: Dangerous command pattern detected\n  Command: ${command.slice(0, 100)}\x1b[0m\n`);
    process.exit(2);  // Non-zero exit blocks the command
  }
}

// Tier routing hint (from CLAUDE.md ADR-026)
if (command.length < 50 && !command.includes('&&')) {
  dim(`Tier 1/2 candidate: ${command.slice(0, 60)}`);
} else {
  dim(`Tier 3 candidate (complex command)`);
}

process.exit(0);

#!/usr/bin/env node
/**
 * Oracle Lifecycle Hook Handler
 * Fires alongside hermes-agent events to keep ORACLE v2 in sync with
 * the Claude Code session lifecycle.
 */
import { existsSync, appendFileSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '../../../../..');

const event = process.argv[2] || 'unknown';

const CYAN  = '\x1b[0;36m';
const DIM   = '\x1b[2m';
const RESET = '\x1b[0m';

// Log event
try {
  const logsDir = join(PROJECT_ROOT, '.claude-flow/logs');
  mkdirSync(logsDir, { recursive: true });
  appendFileSync(
    join(logsDir, 'hermes-events.log'),
    `[${new Date().toISOString()}] event=${event}\n`
  );
} catch { /* non-fatal */ }

// Only print for startup
if (event === 'gateway:startup') {
  process.stderr.write(`${CYAN}[Hermes:oracle-lifecycle] ORACLE gateway ready${RESET}\n`);
}

process.exit(0);

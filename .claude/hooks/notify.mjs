#!/usr/bin/env node
/**
 * Notification Hook — logs Claude notifications, optionally forwards to Telegram
 */
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import { existsSync, appendFileSync, mkdirSync } from 'fs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '../..');

const CYAN  = '\x1b[0;36m';
const RESET = '\x1b[0m';

const message = process.argv[2] || '';

// Log to file
try {
  const logsDir = join(PROJECT_ROOT, '.claude-flow/logs');
  mkdirSync(logsDir, { recursive: true });
  const logEntry = `[${new Date().toISOString()}] ${message}\n`;
  appendFileSync(join(logsDir, 'notifications.log'), logEntry);
} catch { /* non-fatal */ }

// Echo to stderr (visible in Claude session)
if (message) {
  process.stderr.write(`${CYAN}[Notify] 🔔 ${message}${RESET}\n`);
}

process.exit(0);

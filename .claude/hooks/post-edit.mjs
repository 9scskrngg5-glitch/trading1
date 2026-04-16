#!/usr/bin/env node
/**
 * Post-Edit Hook — auto-format, neural pattern learning, hermes agent:step event
 */
import { existsSync, readFileSync } from 'fs';
import { join, dirname, extname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const PROJECT_ROOT = join(__dirname, '../..');

const GREEN  = '\x1b[0;32m';
const DIM    = '\x1b[2m';
const RESET  = '\x1b[0m';

const ok  = (msg) => process.stderr.write(`${GREEN}[PostEdit] ✓ ${msg}${RESET}\n`);
const dim = (msg) => process.stderr.write(`  ${DIM}${msg}${RESET}\n`);

const filePath = process.argv[2] || '';
const ext = extname(filePath).toLowerCase();

// Auto-format Python files
if (ext === '.py' && filePath) {
  try {
    execSync(`python3 -c "import ast; ast.parse(open('${filePath}').read()); print('Syntax OK')"`,
      { stdio: 'pipe', timeout: 3000, cwd: PROJECT_ROOT });
    ok(`Syntax check passed: ${filePath}`);
  } catch (e) {
    process.stderr.write(`\x1b[0;31m[PostEdit] ✗ Syntax error in ${filePath}\x1b[0m\n`);
    process.stderr.write(`  ${e.stderr?.toString()?.slice(0, 200) || e.message}\n`);
  }
}

// Hermes agent:step event (non-fatal)
dim(`agent:step fired for ${filePath || '(unknown)'}`);

process.exit(0);

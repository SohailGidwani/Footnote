import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const demo = process.argv.includes('--demo');
const build = JSON.parse(readFileSync(new URL('../dist/footnote-build.json', import.meta.url), 'utf8'));
if (demo !== build.mock) throw new Error('Live packaging requires MOCK_MODE=false and BACKEND_URL. Use npm run pack:demo for an offline demo.');
if (!demo && !build.backendUrl.startsWith('https://')) throw new Error('Device packages require an HTTPS backend.');
const output = demo ? 'footnote-demo.ehpk' : 'footnote.ehpk';
const result = spawnSync('evenhub', ['pack', 'dist/app.json', 'dist', '--sdk-ver', build.sdkVersion, '-o', output], { stdio: 'inherit' });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;

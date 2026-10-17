import { loadEnv } from 'vite';
import { readFileSync } from 'node:fs';

export function publicConfig(mode, root) {
  const env = loadEnv(mode, root, '');
  const mock = mode === 'demo' || (env.MOCK_MODE ?? 'true') === 'true';
  if (env.MOCK_MODE && !['true', 'false'].includes(env.MOCK_MODE)) throw new Error('MOCK_MODE must be true or false.');
  let backendUrl = '';
  if (!mock) {
    const url = new URL(env.BACKEND_URL || 'missing');
    const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if ((url.protocol !== 'https:' && !(local && url.protocol === 'http:')) || url.username || url.password || url.pathname !== '/' || url.search || url.hash) {
      throw new Error('BACKEND_URL must be the HTTPS origin only, without credentials or paths.');
    }
    backendUrl = url.origin;
  }
  return { mock, backendUrl };
}

export function clientDefines(config) {
  return { __MOCK_MODE__: JSON.stringify(config.mock), __BACKEND_URL__: JSON.stringify(config.backendUrl) };
}

export function manifestPlugin(config, root) {
  return {
    name: 'footnote-manifest',
    generateBundle() {
      const manifest = JSON.parse(readFileSync(new URL('./app.json', root), 'utf8'));
      const sdk = JSON.parse(readFileSync(new URL('../node_modules/@evenrealities/even_hub_sdk/package.json', root), 'utf8'));
      manifest.min_sdk_version = sdk.version;
      manifest.min_app_version = sdk.minAppVersion;
      if (!config.mock) manifest.permissions.push({ name: 'network', desc: 'Send meeting audio and approved follow-up actions to the Footnote backend.', whitelist: [config.backendUrl] });
      this.emitFile({ type: 'asset', fileName: 'app.json', source: JSON.stringify(manifest, null, 2) });
      this.emitFile({ type: 'asset', fileName: 'footnote-build.json', source: JSON.stringify({ ...config, sdkVersion: sdk.version }) });
    },
  };
}

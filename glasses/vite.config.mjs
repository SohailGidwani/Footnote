import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { publicConfig, clientDefines, manifestPlugin } from './config.mjs';

export default defineConfig(({ mode }) => {
  const root = new URL('./', import.meta.url);
  const config = publicConfig(mode, fileURLToPath(root));
  return { base: './', define: clientDefines(config), plugins: [manifestPlugin(config, root)] };
});

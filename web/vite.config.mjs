import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { publicConfig, clientDefines } from '../glasses/config.mjs';

export default defineConfig(({ mode }) => ({
  base: './',
  define: clientDefines(publicConfig(mode, fileURLToPath(new URL('./', import.meta.url)))),
  esbuild: { jsx: 'automatic' },
}));

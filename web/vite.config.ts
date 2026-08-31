import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', sourcemap: true },
  // `css: true` lets a test read a stylesheet's text, which is how the layout
  // guards in tests/demo-page.test.tsx hold decisions that only exist in CSS.
  test: { include: ['tests/**/*.test.{ts,tsx}'], environment: 'node', css: true },
});

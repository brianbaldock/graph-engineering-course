// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://brianbaldock.github.io/graph-engineering-course',
  base: '/graph-engineering-course',
  integrations: [mdx(), sitemap()],
  vite: { plugins: [tailwindcss()] },
});

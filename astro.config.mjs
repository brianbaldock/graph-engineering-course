// @ts-check
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  site: 'https://brianbaldock.github.io/graph-engineering-course',
  base: '/graph-engineering-course',
  integrations: [mdx(), sitemap()],
  markdown: {
    // github-dark's comment colour (#6A737D) fails WCAG AA against our code
    // background. github-dark-dimmed lightens comments enough to pass.
    shikiConfig: { theme: 'github-dark-dimmed' },
  },
  vite: { plugins: [tailwindcss()] },
});

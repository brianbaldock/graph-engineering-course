import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';

const lessons = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/lessons' }),
  schema: z.object({
    title: z.string(),
    order: z.number(),
    part: z.string(),
    summary: z.string(),
    minutes: z.number().default(20),
    hands_on: z.boolean().default(false),
  }),
});

export const collections = { lessons };

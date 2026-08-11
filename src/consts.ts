export const SITE_TITLE = 'Graph Engineering';
export const SITE_TAGLINE = 'Stop prompting. Start building agentic graphs.';
export const SITE_DESCRIPTION =
  'A hands-on course in agentic graph engineering: knowledge-graph memory, cheap extraction, selective retrieval, and routing policy. Driven with Hermes Agent and GitHub Copilot CLI.';
export const REPO_URL = 'https://github.com/brianbaldock/graph-engineering-course';

/**
 * GoatCounter analytics endpoint.
 *
 * Cookieless, no consent banner needed, ~3.5KB beacon. Same choice as the
 * blog. Set to '' to disable analytics entirely (the script is then not
 * emitted at all, rather than firing at a dead endpoint).
 *
 * Honest caveat carried over from the blog: this is a client-side beacon, so
 * ad blockers suppress it. This audience runs blockers heavily, so treat the
 * numbers as directional (which lessons land) rather than a true visitor count.
 */
export const GOATCOUNTER_URL = 'https://agenticgraphs.goatcounter.com/count';

/**
 * giscus comments, stored as GitHub Discussions on this repo.
 *
 * These are public identifiers, not secrets, and are safe to commit.
 * Verified live from the GitHub API on 2026-08-11:
 *   repo id     -> R_kgDOT1iL_A
 *   category    -> Q&A (answerable, unlike the blog's Announcements)
 *   category id -> DIC_kwDOT1iL_M4DDLTX
 *
 * Q&A rather than Announcements is deliberate: a course generates questions,
 * and an answerable category lets a reply be marked as the accepted answer.
 */
export const GISCUS = {
  repo: 'brianbaldock/graph-engineering-course',
  repoId: 'R_kgDOT1iL_A',
  category: 'Q&A',
  categoryId: 'DIC_kwDOT1iL_M4DDLTX',
} as const;

# CLAUDE.md

Project-specific guidance for AI coding agents.

## How Van learns

Prefer **ASCII diagrams + plain language** for architecture and concepts (RAG flow, agent loop, chunk overlap, memory vs DB, LangGraph vs LlamaIndex). Lead with the picture, then a short caption. Full standing preference: `AGENTS.md`.

Hard concepts: life analogy first, then diagram, then jargon; Vietnamese OK when asked. Locked models in `docs/learning/` (e.g. **07-chunking.md** Ch. 20–21, **08-agent-evals.md** Ch. 22–23: six eval categories + philosophy intention→trust/reliability).

Learning hub: `docs/learning/README.md` — add new ahas to the matching topic file + hub index.

<!-- ASTRYX:START -->
Astryx v0.1.4 · 149 components
CLI: run every command as `npx astryx <cmd>` (shown below as `astryx ...`).

SETUP (once, in your app entry e.g. main.tsx) — without these, components render unstyled:
  import "@astryxdesign/core/reset.css";
  import "@astryxdesign/core/astryx.css";

WORKFLOW — discover, don't guess. Before writing UI:
1. `astryx build "<idea>"` — START HERE: returns a kit (closest [page] + [block]s + [component]s). No args = full playbook.
2. `astryx template <name> [--skeleton]` — scaffold the [page]/[block]s it named, or study their layout. Templates are reference code.
3. `astryx component <Name>` — props + examples for every component you use.

RULES:
- No <div> — components do all layout/spacing. Full page → AppShell; sidebar nav → SideNav.
- Frame first: pick the shell (AppShell / Layout+LayoutPanel) and budget regions in px BEFORE writing content (`astryx docs layout`).
- Dense data = rows (Table, List/Item) edge-to-edge — never Card-wrapped list items. Card = dashboard widgets, galleries, settings groups only.
- Status → StatusDot/Token; Badge only for counts and enumerated states, never decoration.
- Custom styling: component props first; else style/className with tokens — var(--color-*|--spacing-*|--radius-*). No raw hex/px. (No StyleX/Tailwind compiler here — don't use xstyle/utility classes.)
- Tokens for every value (`astryx docs tokens`). Brand/accent via `astryx theme` — never override --color-* in :root.

MORE CLI:
  search "<query>"   find any component / hook / doc / template / block
  component --list   149 components by category
  template --list    page + block recipes
  docs <topic>       color, elevation, icons, illustrations, layout, migration, motion, principles, shape, spacing, styling, theme, tokens, typography
  swizzle <Name>     eject component source for deep customization
  upgrade --apply    run after any @astryxdesign/core bump
<!-- ASTRYX:END -->

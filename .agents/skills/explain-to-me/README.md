# Explain to Me

Single skill package for adaptive explanations. ASD-STE100 controlled clarity and ASCII mental models are **methodology references**, not separate skills.

## Layout

```text
explain-to-me/
├── SKILL.md
├── README.md
└── references/
    ├── asd-ste100/                 # full STE guide + rules + examples (MIT)
    │   ├── guide.md
    │   ├── writing-rules.md
    │   ├── before-after.md
    │   ├── README.md
    │   └── LICENSE
    └── explaining-with-ascii/
        └── guide.md                # full ASCII explaining methodology
```

| Path | Role |
|------|------|
| `SKILL.md` | Always-on entry: depth, language, clarity defaults, when to load refs |
| `references/asd-ste100/` | Full STE rewrite guide, writing-rule summary, before/after examples |
| `references/explaining-with-ascii/guide.md` | Full ASCII diagram shapes, teaching order, quality rules |

Agents load reference trees only when needed (progressive disclosure).

## Installation

Copy this folder into the agent skills directory:

```bash
# Claude Code / common layout
cp -r explain-to-me ~/.claude/skills/

# Grok (user-level)
cp -r explain-to-me ~/.grok/skills/

# Project-local agents
mkdir -p <project>/.agents/skills
cp -r explain-to-me <project>/.agents/skills/
```

Install **this one folder only**. Do not install nested `asd-ste100` or `explaining-with-ascii` as standalone skills.

## Usage

- `/explain-to-me` or natural phrases: “explain to me”, “how does this work”, “help me understand”
- STE rewrite: “simplify for STE100”, “reduce ambiguity for agents”
- Visual: “ASCII diagram”, “mental model”, “like I’m new”

## Sources

- Controlled clarity methodology: ASD-STE100 Issue 9 categories (see `references/asd-ste100/`)
- ASCII mental models: vendored guide under `references/explaining-with-ascii/`
- ADHD-friendly structure ideas: [i-have-adhd](https://github.com/ayghri/i-have-adhd)

ASD-STE100 reference materials retain their original MIT license (`references/asd-ste100/LICENSE`).

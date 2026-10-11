# Cloudflare demo

Live app: https://agentic-rag-demo.kv090695.workers.dev

This is a public demo: there is no Cloudflare Access login. Anyone with the URL
can upload, ask questions, or clear the shared corpus, and chat uses the owner's
OpenAI account. Do not upload sensitive documents. Add authentication and usage
limits before using this beyond a short demo.

The Worker routes every request to one fixed Cloudflare Container.
That container runs the existing Next.js UI and a single FastAPI worker. The
Next.js same-origin `/api/*` proxy reaches FastAPI inside the container. No
browser-local API URL or separate public API service is needed.

## Demo limits

- Maximum one `standard-1` instance (4 GiB RAM, 0.5 vCPU), with CPU-only PyTorch.
- Sleeps after 15 idle minutes. Cold starts can take time.
- Uploaded files and the vector index are temporary: sleep, restart, or redeploy
  clears them. Upload again after the container wakes.
- One shared corpus, not multi-tenant use.
- Duplicate filenames return 409. Clear documents before replacing a file.
- Containers and OpenAI calls incur usage charges; one instance is not a dollar
  spending cap.
- Jev routing is not implemented in this deployment.

## Build and deploy

Prerequisites: Node.js 22.18+, Docker, and the Cloudflare CLI login for the target
account. Run commands from the repository root unless noted.

```bash
npm ci --prefix deploy/cloudflare
deploy/cloudflare/node_modules/.bin/cf auth login --no-browser
docker build --network=host -t agentic-rag-demo:demo-20261011-public .
deploy/cloudflare/node_modules/.bin/cf containers push --tag agentic-rag-demo:demo-20261011-public
npm run deploy --prefix deploy/cloudflare
```

Use a new image tag for a release and update the image reference in
`deploy/cloudflare/cloudflare.config.ts` before deploying. `--network=host` is for
Linux/orb builds; omit it when the local Docker builder has normal networking.
The Cloudflare project uses its own lockfile so deployment tooling does not enter
the frontend bundle. `.agents/setup` installs both lockfiles for fresh orbs.

`OPENAI_API_KEY` is a Cloudflare Worker secret and is passed to the container only
at runtime. It must never be put in the image, frontend, or committed files. For
the initial deployment, `cf deploy --secrets-file <private-file>` can upload it
alongside the Worker version; delete the private file afterward. Subsequent
deployments preserve the existing Worker secret.

The registry image reference is account-specific. Update it before deploying to
a different account. Supervisor writes bounded child logs under `/tmp` because
Cloudflare's stdout/stderr sockets cannot be reopened as `/dev/stdout` log files.

## Checks

```bash
node --experimental-strip-types --test src/lib/api.test.mjs
.venv/bin/python -m unittest discover -s backend -p 'test_*.py'
npm run build --prefix deploy/cloudflare
```

For a live check, verify UI and API requests work without signing in;
upload a small non-sensitive PDF or Markdown file, and ask both
a supported question and one whose answer is absent. Verify Direct and
Orchestrator responses, source citations, and duplicate-upload rejection.

## Live audit (2026-10-11)

Public UI and health checks passed. Markdown and PDF uploads returned 200;
duplicate filenames returned 409. Direct answers correctly cited 19 requests per
minute from Markdown and 7 support seats from PDF page 1. Orchestrator correctly
returned a 12-minute timeout through `ask_docs`. The missing-price question
produced a refusal rather than inventing a price. Cross-encoder reranking appeared
in the retrieved evidence. Warm streamed answers took approximately 3–6 seconds.

Known limitations, not production guarantees:

- The first document question timed out at 240 seconds; subsequent questions
  succeeded. The cold retrieval delay still needs profiling.
- Orchestrator's final rewrite can omit the specialist's citations.
- The source list can show retrieved passages beyond those actually cited.
- This was a small synthetic-document smoke test, not the full golden eval set.

The proposed Jev router is documented in
[`docs/learning/09-jev-routing.md`](../docs/learning/09-jev-routing.md). It is not
running in the live demo.

import { bindings, defineConfig, defineContainer, exports } from "cf/config";

const demo = defineContainer({
  name: "agentic-rag-demo",
  image: {
    reference:
      "registry.cloudflare.com/777f57b3d77ecb4759a0002ea904518e/agentic-rag-demo:demo-20261011-public",
  },
  instanceType: "standard-1",
  maxInstances: 1,
});

export default defineConfig({
  worker: {
    name: "agentic-rag-demo",
    entrypoint: "./worker.js",
    compatibilityDate: "2026-10-11",
    compatibilityFlags: ["nodejs_compat"],
    workersDev: true,
    previewUrls: false,
    exports: {
      RagDemo: exports.durableObject({ storage: "sqlite", container: demo }),
    },
    env: {
      RAG_DEMO: bindings.durableObject({
        worker: "agentic-rag-demo",
        exportName: "RagDemo",
      }),
      OPENAI_API_KEY: bindings.secret(),
    },
  },
  containers: [demo],
});

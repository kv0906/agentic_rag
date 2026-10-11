import { Container } from "@cloudflare/containers";

export class RagDemo extends Container {
  defaultPort = 3000;
  requiredPorts = [3000, 8000];
  sleepAfter = "15m";
  envVars = { OPENAI_API_KEY: this.env.OPENAI_API_KEY };
}

export default {
  async fetch(request, env) {
    if (!env.OPENAI_API_KEY)
      return new Response("Demo is not configured yet.", { status: 503 });
    // One fixed ID keeps the demo's in-memory corpus on one container.
    const container = env.RAG_DEMO.getByName("public");
    // Next.js starts before Python; wait for both before exposing the UI/API.
    await container.startAndWaitForPorts({
      cancellationOptions: {
        instanceGetTimeoutMS: 120_000,
        portReadyTimeoutMS: 120_000,
      },
    });
    return container.fetch(request);
  },
};

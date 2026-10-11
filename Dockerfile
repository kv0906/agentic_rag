FROM node:22-bookworm-slim AS frontend
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY next.config.ts tsconfig.json next-env.d.ts ./
COPY src ./src
RUN npm run build

FROM node:22-bookworm-slim
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000
EXPOSE 3000
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/demo.conf"]
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv supervisor ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app
COPY --from=frontend /app/.next/standalone ./
COPY --from=frontend /app/.next/static ./.next/static
COPY backend/requirements.txt ./backend/requirements.txt
RUN uv venv --python python3 .venv \
    && uv pip install --python .venv/bin/python --link-mode copy --torch-backend cpu -r backend/requirements.txt \
    && uv cache clean
COPY backend ./backend
COPY deploy/supervisord.conf /etc/supervisor/conf.d/demo.conf

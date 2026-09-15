FROM node:26-alpine AS assetsbuild

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN npm install -g pnpm && \
    pnpm install --frozen-lockfile

COPY ludia ./ludia
RUN pnpm run build
CMD ["pnpm", "run", "watch"]

FROM ghcr.io/trojsten/django-docker:v8

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

COPY --chown=appuser:appuser . /app/
COPY --chown=appuser:appuser --from=assetsbuild /app/ludia/styles/static/app.js /app/ludia/styles/static/
RUN SECRET_KEY=none python manage.py collectstatic --no-input

ENV BASE_START=/app/start.sh

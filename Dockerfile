# syntax=docker/dockerfile:1

# Build stage: resolve and install the locked dependency set with uv. Kept
# separate from the runtime stage so the final image doesn't carry uv, the
# build cache, or any dev-only tooling.
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Install dependencies first (cached layer) before copying application code,
# so source-only changes don't invalidate the dependency install.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Runtime stage: slim image with only the built virtualenv and application
# code. Host-neutral — no PaaS-specific configuration here (see
# .docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §4/§8).
FROM python:3.13-slim AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system appuser \
    && useradd --system --create-home --gid appuser appuser

COPY --from=builder --chown=appuser:appuser /app /app

# STATIC_ROOT/MEDIA_ROOT (staticfiles/, media/) aren't part of the build
# context (see .dockerignore) so they don't exist yet — collectstatic and
# local-disk media storage need to create them at runtime as appuser.
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media \
    && chown appuser:appuser /app/staticfiles /app/media

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]

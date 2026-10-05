FROM node:22-alpine AS client-build

WORKDIR /app/client

COPY client/package.json client/package-lock.json ./
RUN npm ci

COPY client/ ./
COPY docs/manuel-utilisateur/ /app/docs/manuel-utilisateur/
RUN npm run build


FROM python:3.12-slim AS runtime

ARG APP_VERSION=1.5.0
ARG RELEASE_GIT_SHA=unknown

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_VERSION=${APP_VERSION}
ENV RELEASE_GIT_SHA=${RELEASE_GIT_SHA}

LABEL org.opencontainers.image.title="marketteo-crm" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${RELEASE_GIT_SHA}"

WORKDIR /app

RUN addgroup --system prospect \
    && adduser --system --ingroup prospect prospect \
    && mkdir -p /app/.runtime/imports \
    && chown -R prospect:prospect /app/.runtime

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=client-build /app/client/dist /app/client/dist

USER prospect

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

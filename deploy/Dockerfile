# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Stage 1: Build stage — resolve and install deps for Python 3.12
FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS builder
WORKDIR /build
RUN tdnf update -y && tdnf install -y \
    gcc \
    libffi-devel \
    && tdnf clean all
COPY requirements.in .
RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --no-cache-dir pip-tools \
    && pip-compile --strip-extras --no-header \
        -o requirements.lock requirements.in \
    && pip install --no-cache-dir -r requirements.lock

# Stage 2: Startup stage
FROM mcr.microsoft.com/azurelinux/base/python:3.12

ARG APP_UID=1000
ARG APP_GID=1000

RUN tdnf update -y && tdnf install -y \
    openssh-clients \
    git \
    curl \
    util-linux \
    shadow-utils \
    && tdnf clean all \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && groupadd -g "${APP_GID}" appuser \
    && useradd -u "${APP_UID}" -g appuser -m -s /bin/bash appuser \
    && mkdir -p /app/data/logs/service /app/data/logs/jobs \
    && mkdir -p /app/data/jobs/history /home/appuser/.ssh \
    && chmod 700 /home/appuser/.ssh \
    && chown -R appuser:appuser /app /home/appuser/.ssh

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=appuser:appuser src/ ./src/

ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV=/opt/venv
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1
EXPOSE 8000
CMD ["sh", "-c", "mkdir -p /app/data/logs/service /app/data/logs/jobs /app/data/jobs/history && exec uvicorn src.api.app:app --host 0.0.0.0 --port 8000"]
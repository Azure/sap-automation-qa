# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Stage 1: Build stage
FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS builder
WORKDIR /build
RUN tdnf update -y && tdnf install -y \
    gcc \
    libffi-devel \
    && tdnf clean all
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/build/deps -r requirements.txt

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
    && mkdir -p /app/data /app/logs /home/appuser/.ssh \
    && chmod 700 /home/appuser/.ssh \
    && chown -R appuser:appuser /app /home/appuser/.ssh

WORKDIR /app

COPY --from=builder /build/deps /usr/local
COPY --chown=appuser:appuser src/ ./src/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1
EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
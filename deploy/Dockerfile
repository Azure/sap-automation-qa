# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Stage 1: Build stage — resolve and install deps for Python 3.12
FROM mcr.microsoft.com/azurelinux/base/python:3.12@sha256:8300706a0e644a7e260b6a464a1ae3967181ee9057a4accceaaf0ecdedb1d4a2 AS builder
WORKDIR /build
RUN tdnf update -y && tdnf install -y \
    gcc \
    libffi-devel \
    ca-certificates \
    && update-ca-trust extract \
    && tdnf clean all
COPY requirements.in .
COPY collections/requirements.yml collections/requirements.yml
RUN python3 -m venv /opt/venv \
    && . /opt/venv/bin/activate \
    && pip install --no-cache-dir pip-tools \
    && pip-compile --strip-extras --no-header \
        -o requirements.lock requirements.in \
    && pip install --no-cache-dir -r requirements.lock \
    && ansible-galaxy collection install \
        -r collections/requirements.yml \
        -p /opt/ansible/collections

# Stage 2: Startup stage
FROM mcr.microsoft.com/azurelinux/base/python:3.12@sha256:8300706a0e644a7e260b6a464a1ae3967181ee9057a4accceaaf0ecdedb1d4a2

RUN tdnf update -y && tdnf install -y \
    openssh-clients \
    git \
    curl \
    util-linux \
    gawk \
    shadow-utils \
    && tdnf clean all \
    && ln -sf /usr/bin/python3 /usr/bin/python \
    && pip install --no-cache-dir azure-cli \
    && groupadd --gid 1000 appgroup \
    && useradd --uid 1000 --gid appgroup --shell /bin/bash \
        --create-home --home-dir /app appuser \
    && mkdir -p /app/.ssh \
    && chmod 700 /app/.ssh \
    && chown -R appuser:appgroup /app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/ansible /opt/ansible
COPY src/ ./src/
COPY VERSION ./VERSION

ENV PATH="/opt/venv/bin:$PATH"
ENV VIRTUAL_ENV=/opt/venv
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV HOME=/app
ENV ANSIBLE_COLLECTIONS_PATH=/opt/ansible/collections

RUN chown -R appuser:appgroup /opt/venv /app

RUN mkdir -p /app/data/logs/service && chown -R appuser:appgroup /app/data

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1
EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
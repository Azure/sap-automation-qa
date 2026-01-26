# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Stage 1: Build stage
FROM mcr.microsoft.com/azurelinux/base/python:3.12 as builder
WORKDIR /app
RUN tdnf update -y && tdnf install -y \
    gcc \
    libffi-devel \
    && tdnf clean all
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Startup stage
FROM mcr.microsoft.com/azurelinux/base/python:3.12
WORKDIR /app
RUN tdnf update -y && tdnf install -y \
    openssh-clients \
    git \
    curl \
    util-linux \
    && tdnf clean all \
    && mkdir -p /app/data /app/logs /root/.ssh \
    && chmod 700 /root/.ssh
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY src/ ./src/
COPY docs/ ./docs/
COPY WORKSPACES/ ./WORKSPACES/
RUN mkdir -p /app/data
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1
EXPOSE 8000
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
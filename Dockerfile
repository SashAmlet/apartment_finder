################################################################
# Multi-target Dockerfile (CPU and GPU)
################################################################

# Base stage: small Python image for installing runtime dependencies.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system packages required by some Python packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       ca-certificates \
       git \
       libglib2.0-0 \
       libsm6 \
       libxrender1 \
       ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the production requirements (without torch). Torch will be installed
# explicitly per-target so we can choose CPU vs CUDA wheels.
COPY requirements-prod.txt /app/requirements-prod.txt

# Install pip + CPU torch wheel, then install remaining production deps.
# Use the official PyTorch CPU wheel index; note that some torch releases
# are published without the '+cpu' suffix, so pin to the normal release
# (e.g. '2.10.0') while pointing pip at the CPU wheel index.
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir torch==2.10.0 -f https://download.pytorch.org/whl/cpu/torch_stable.html \
    && pip install --no-cache-dir -r /app/requirements-prod.txt

# Copy source and set permissions
COPY . /app
RUN groupadd -r app && useradd -m -r -g app app \
    && chown -R app:app /app

ENV PATH=/home/app/.local/bin:$PATH

### CPU target (default)
FROM base AS cpu
USER app
WORKDIR /app
CMD ["python", "main.py"]

### GPU target: use NVIDIA CUDA runtime as base and install CUDA torch
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS gpu

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install small set of system deps used by the app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       curl \
       ca-certificates \
       git \
       libglib2.0-0 \
       libsm6 \
       libxrender1 \
       ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy application files from base stage (already has deps installed)
COPY --from=base /app /app

# Install CUDA-enabled torch matching CUDA 12.4 (adjust version if needed)
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir torch==2.10.0+cu124 -f https://download.pytorch.org/whl/cu124.html

RUN groupadd -r app && useradd -m -r -g app app \
    && chown -R app:app /app

ENV PATH=/home/app/.local/bin:$PATH
USER app
WORKDIR /app
CMD ["python", "main.py"]
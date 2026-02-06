# apartment_finder — Docker build & run

This repository contains a Python project that can run both locally (CPU) and in production with a GPU-enabled image. The repository includes a multi-target `Dockerfile` which produces two targets and a `docker-compose.yml` to run the images easily.

- `cpu` — a CPU-only image based on `python:3.11-slim` (default runtime target)
- `gpu` — a GPU image built on an NVIDIA CUDA runtime and installing a CUDA-enabled PyTorch wheel

This README explains how to build and run both variants, how to use `docker-compose`, and other tips for a smooth developer experience.

## Files added for Docker

- `Dockerfile` — multi-target (base / cpu / gpu)
- `requirements-prod.txt` — runtime dependencies (torch is installed explicitly per-target)
- `.dockerignore` — excludes large files and sensitive folders from the build context
- `docker-compose.yml` — compose file with two services (`app` for CPU and `app-gpu` for GPU)

## Build & run (PowerShell)

### 1) Build CPU image (default)

This builds the `cpu` target from the multi-stage Dockerfile and installs a CPU PyTorch wheel plus `requirements-prod.txt`.

```powershell
docker build -t apartment_finder:cpu --target cpu .
```

Run the CPU image:

```powershell
docker run --rm -it apartment_finder:cpu
# or with local data mounted and an env-file:
docker run --rm -it -v ${PWD}\data:/app/data --env-file .env apartment_finder:cpu
```

### 2) Build GPU image (production)

This builds the `gpu` target. It uses an NVIDIA CUDA runtime base image and installs a matching CUDA PyTorch wheel.

Requirements:
- Docker with NVIDIA Container Toolkit installed on the host (so containers can access GPUs).

Build:

```powershell
docker build -t apartment_finder:gpu --target gpu .
```

Run (with NVIDIA GPUs available):

```powershell
docker run --gpus all --rm -it apartment_finder:gpu
```

If you need to map files or pass secrets:

```powershell
docker run --gpus all --rm -it -v ${PWD}\models:/app/models --env-file .env apartment_finder:gpu
```

### 3) Docker Compose (recommended for local integration)

A `docker-compose.yml` is included and defines two services:

- `app` — builds the `cpu` target and is suitable for local testing
- `app-gpu` — builds the `gpu` target and requests GPUs (requires NVIDIA Container Toolkit)

Build & start with docker-compose:

```powershell
docker compose up --build
```

Start only the CPU service:

```powershell
docker compose up --build app
```

Start only the GPU service:

```powershell
docker compose up --build app-gpu
```

Notes:
- Use `--env-file .env` or `env_file: .env` in compose to pass secrets like API keys.
- The compose file mounts `./data` and `./models` into the container; adjust paths as needed.
- `gpus: all` requires Docker Engine with NVIDIA Container Toolkit installed and a compatible `docker compose` implementation.

#### Redis service

The `docker-compose.yml` now also contains a `redis` service (image `redis:7-alpine`) with a persistent volume. By default the service exposes port `6379` and is reachable from the `app` container by the hostname `redis`.

- To enable Redis AUTH, set `REDIS_PASSWORD` in your `.env` file (example below). The compose service will start Redis with `--requirepass` when this variable is set.
- Connection string from the app: `redis://[:<password>@]redis:6379/0` (use the `REDIS_PASSWORD` value if set).

Example `.env` addition for Redis (do NOT commit):

```text
REDIS_PASSWORD=your_redis_password_here
```

## Environment variables

Secrets and API keys (for example `GEMINI_API_KEY`) should be provided at runtime either via `--env`/`--env-file` or an orchestration system. Example:

```powershell
docker run --rm -it --env GEMINI_API_KEY=xxxx apartment_finder:cpu
```

Or use a file named `.env` and pass `--env-file .env`.

Example `.env` (do NOT commit this file):

```text
GEMINI_API_KEY=your_key_here
OTHER_SECRET=...
```

## Notes & troubleshooting

- The `requirements-prod.txt` intentionally excludes `torch` so the Dockerfile installs the correct wheel per-target (CPU vs CUDA). If you change torch versions, update the `Dockerfile` to match the wheel you want.
- If a pip install of torch fails in the GPU build, check the CUDA base image version and choose a matching `torch` wheel (see https://download.pytorch.org/whl/cu124.html for cu124 wheels).
- Use `.dockerignore` to keep the build context small. Do not copy data, models or virtual environments into the image.
- If the build is too large or slow, consider trimming `requirements-prod.txt` to the minimal runtime dependencies.
- A `.dockerignore` is included to exclude `data/`, `models/`, `.venv/` and other unnecessary paths from the build context. Review it and add any local folders you don't want copied into the image.
- The Dockerfile creates a non-root `app` user and sets proper ownership of `/app` for better security.
- `requirements-prod.txt` intentionally excludes `torch`. The Dockerfile installs the appropriate `torch` wheel explicitly per target (CPU vs CUDA). This avoids attempts to install CUDA wheels on CPU-only images.

## Development (optional)

For iterative development on your machine, consider running the code in a local virtualenv (faster feedback loop) and use the Docker image only for integration or production tests. Example:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-prod.txt
python main.py
```

### Fast local development with docker-compose.override

For iterative development you can create `docker-compose.override.yml` in your project root to mount the source directory into the container and run with live code changes. Example override content:

```yaml
version: '3.8'
services:
	app:
		volumes:
			- ./:/app:rw
		command: ["python", "main.py"]
```

Run the override (docker-compose automatically picks up `docker-compose.override.yml`):

```powershell
docker compose up --build
```

This lets you edit code locally and have the container run the latest files. Keep in mind that installing new Python packages will still require rebuilding the image.

## CI / automation

If you want CI to build both images, invoke both targets during your pipeline:

```yaml
# example steps
- docker build --target cpu -t apartment_finder:cpu .
- docker build --target gpu -t apartment_finder:gpu .
```

---

If you'd like, I can also:
- Add `Dockerfile.cpu` and `Dockerfile.gpu` explicit files (some CI systems prefer separate files),
- Further prune `requirements-prod.txt` to remove packages you don't need at runtime, or
- Add a brief `docker-compose.yml` for local testing wiring env files and volumes.

If you want one of those, tell me which and I'll add it.

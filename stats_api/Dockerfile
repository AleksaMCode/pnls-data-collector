FROM python:3.13-slim

# Installs the Debian security updates released after the base image was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /stats_api_service

COPY stats_api/requirements.txt /stats_api_service/requirements.txt

# pip is only needed at build time, and the libraries bundled inside it are flagged by the image scan, so it is removed from the final filesystem.
RUN pip install -r requirements.txt \
    && pip uninstall -y pip

# Keep stats_api as a standalone app root so imports like
# "from core...", "from routers...", "from middleware..." work.
# Local .env files are left out by Dockerfile.dockerignore.
COPY stats_api /stats_api_service/stats_api

WORKDIR /stats_api_service/stats_api

EXPOSE 9098

CMD ["python", "-m", "main"]

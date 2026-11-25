FROM python:3.13-slim

# Installs the Debian security updates released after the base image was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /stats_api_service

COPY stats_api/requirements.txt /stats_api_service/requirements.txt
RUN pip install -r requirements.txt

# pip is only needed at build time. The libraries bundled inside it are flagged by the image scan.
RUN pip uninstall -y pip

# Keep stats_api as a standalone app root so imports like
# "from core...", "from routers...", "from middleware..." work.
COPY stats_api /stats_api_service/stats_api

WORKDIR /stats_api_service/stats_api

EXPOSE 9098

CMD ["python", "-m", "main"]

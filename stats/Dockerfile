FROM python:3.13-slim

# Installs the Debian security updates released after the base image was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /stats_service

COPY stats/requirements.txt /stats_service/requirements.txt
COPY util/requirements.txt /stats_service/requirements_util.txt

# Installed in one command so that conflicting pins between the two files fail the build.
# pip is only needed at build time, and the libraries bundled inside it are flagged by the image scan, so it is removed from the final filesystem.
RUN pip install -r requirements.txt -r requirements_util.txt \
    && pip uninstall -y pip

COPY stats /stats_service/stats
COPY util /stats_service/util

EXPOSE 9097

CMD ["python", "-m", "stats.main"]

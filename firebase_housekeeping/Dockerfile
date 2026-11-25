FROM python:3.13-slim

# Installs the Debian security updates released after the base image was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /firebase_housekeeping_service

COPY firebase_housekeeping/requirements.txt /firebase_housekeeping_service/requirements.txt
RUN pip install -r requirements.txt

COPY util/requirements.txt /firebase_housekeeping_service/requirements_util.txt
RUN pip install -r requirements_util.txt

# pip is only needed at build time. The libraries bundled inside it are flagged by the image scan.
RUN pip uninstall -y pip

COPY firebase_housekeeping /firebase_housekeeping_service/firebase_housekeeping
COPY util /firebase_housekeeping_service/util

EXPOSE 9090

CMD ["python", "-m", "firebase_housekeeping.main"]

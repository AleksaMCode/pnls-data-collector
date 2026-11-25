FROM python:3.13-slim

# Installs the Debian security updates released after the base image was built.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /ssid_geo_mapper_service

COPY ssid_geo_mapper/requirements.txt /ssid_geo_mapper_service/requirements.txt
COPY util/requirements.txt /ssid_geo_mapper_service/requirements_util.txt

# Installed in one command so that conflicting pins between the two files fail the build.
# pip is only needed at build time, and the libraries bundled inside it are flagged by the image scan, so it is removed in the same layer.
RUN pip install -r requirements.txt -r requirements_util.txt \
    && pip uninstall -y pip

COPY ssid_geo_mapper /ssid_geo_mapper_service/ssid_geo_mapper
COPY util /ssid_geo_mapper_service/util

EXPOSE 9089

CMD ["python", "-m", "ssid_geo_mapper.main"]

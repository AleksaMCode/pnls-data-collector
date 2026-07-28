FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /ssid_geo_mapper_service

COPY ssid_geo_mapper/requirements.txt /ssid_geo_mapper_service/requirements.txt
RUN pip install -r requirements.txt

COPY util/requirements.txt /ssid_geo_mapper_service/requirements_util.txt
RUN pip install -r requirements_util.txt

COPY ssid_geo_mapper /ssid_geo_mapper_service/ssid_geo_mapper
COPY util /ssid_geo_mapper_service/util

EXPOSE 9089

CMD ["python", "-m", "ssid_geo_mapper.main"]

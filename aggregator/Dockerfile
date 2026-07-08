FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /aggregator_service

COPY aggregator/requirements.txt /aggregator_service/requirements.txt
RUN pip install -r requirements.txt

COPY util/requirements.txt /aggregator_service/requirements_util.txt
RUN pip install -r requirements_util.txt

COPY aggregator /aggregator_service/aggregator
COPY util /aggregator_service/util

EXPOSE 9091

CMD ["python", "-m", "aggregator.main"]

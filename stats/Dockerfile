FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /stats_service

COPY stats/requirements.txt /stats_service/requirements.txt
RUN pip install -r requirements.txt

COPY util/requirements.txt /stats_service/requirements_util.txt
RUN pip install -r requirements_util.txt

COPY stats /stats_service/stats
COPY util /stats_service/util

EXPOSE 9097

CMD ["python", "-m", "stats.main"]

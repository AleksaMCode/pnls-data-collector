FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /firebase_housekeeping_service

COPY firebase_housekeeping/requirements.txt /firebase_housekeeping_service/requirements.txt
RUN pip install -r requirements.txt

COPY util/requirements.txt /firebase_housekeeping_service/requirements_util.txt
RUN pip install -r requirements_util.txt

COPY firebase_housekeeping /firebase_housekeeping_service/firebase_housekeeping
COPY util /firebase_housekeeping_service/util

EXPOSE 9090

CMD ["python", "-m", "firebase_housekeeping.main"]

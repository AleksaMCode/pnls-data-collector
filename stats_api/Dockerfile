FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /stats_api_service

COPY stats_api/requirements.txt /stats_api_service/requirements.txt
RUN pip install -r requirements.txt

# Keep stats_api as a standalone app root so imports like
# "from core...", "from routers...", "from middleware..." work.
COPY stats_api /stats_api_service/stats_api

WORKDIR /stats_api_service/stats_api

EXPOSE 9098

CMD ["python", "-m", "main"]

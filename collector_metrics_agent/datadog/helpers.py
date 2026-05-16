from datadog import api

from collector_metrics_agent.settings import DEVICE_NAME
from util.logger import get_logger

logger = get_logger(__name__)


def send_metrics(metrics):
    try:
        prepared_metrics = []
        for metric in metrics:
            current_metric = dict(metric)
            tags = list(current_metric.get("tags", []))
            normalized_host_tag = f"host:{DEVICE_NAME}"

            tags = [tag for tag in tags if not str(tag).startswith("host:")]
            tags.append(normalized_host_tag)

            current_metric["tags"] = tags
            current_metric["host"] = DEVICE_NAME
            current_metric.setdefault("type", "gauge")
            prepared_metrics.append(current_metric)

        api.Metric.send(prepared_metrics)
        return True
    except Exception as e:
        logger.error(f"Failed to send metrics to Datadog. Error: {str(e)}")
        return False

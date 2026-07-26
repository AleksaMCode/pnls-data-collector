import logging
from typing import List

from tenacity import after_log, before_log, retry, stop_after_attempt, wait_exponential

from ssid_geo_mapper.core.orm._init_runtime import _session
from ssid_geo_mapper.core.orm.models import SSID, Country, SSIDGeo, SSIDGeoReduced
from util.logger import get_logger

logger = get_logger(__name__)


def insert_ssid_geo_batch(
    ssid_id: int,
    locations: list[dict[str, str | float]],
    reduced_locations: list[dict[str, str | float]],
):
    with _session() as db:
        try:
            country_cache: dict[str, int | None] = {}

            def get_country_id(alpha2: str | None) -> int | None:
                if alpha2 is None:
                    return None

                alpha2 = alpha2.upper()
                if alpha2 not in country_cache:
                    country_cache[alpha2] = (
                        db.query(Country.id).filter(Country.alpha2 == alpha2).scalar()
                    )
                return country_cache[alpha2]

            full_rows = [
                SSIDGeo(
                    ssid=ssid_id,
                    latitude=location["lat"],
                    longitude=location["long"],
                    country=get_country_id(location["alpha2"]),
                )
                for location in locations
            ]
            logger.info("Insert of non-reduced locations completed.")

            reduced_rows = [
                SSIDGeoReduced(
                    ssid=ssid_id,
                    latitude=location["lat"],
                    longitude=location["long"],
                    country=get_country_id(location["alpha2"]),
                )
                for location in reduced_locations
            ]
            logger.info("Insert of reduced locations completed.")

            db.add_all(full_rows + reduced_rows)
            db.query(SSID).filter(SSID.id == ssid_id).update(
                {
                    SSID.mapped: True,
                    SSID.has_geo: bool(full_rows or reduced_rows),
                },
                synchronize_session=False,
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Error occurred during batch insert: {str(e)}")
            raise


@retry(
    stop=stop_after_attempt(10),
    wait=wait_exponential(multiplier=1, min=30, max=90),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.ERROR),
)
def get_unmapped_ssids(limit: int) -> List[SSID]:
    try:
        with _session() as db:
            return (
                db.query(SSID)
                .filter(SSID.mapped.is_(False), SSID.has_geo.is_(False))
                .order_by(SSID.id.asc())
                .limit(limit)
                .all()
            )
    except Exception as e:
        logger.error(f"Database query failed: {e}")
        raise


def update_ssid_mapped(ssid_id: int, has_geo: bool = False):
    with _session() as db:
        db.query(SSID).filter(SSID.id == ssid_id).update(
            {
                SSID.mapped: True,
                SSID.has_geo: has_geo,
            },
            synchronize_session=False,
        )
        db.commit()

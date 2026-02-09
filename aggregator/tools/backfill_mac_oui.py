from sqlalchemy import and_
from tqdm import tqdm

# This import is needed in order for listener to work!! - from aggregator.core.orm import event
from aggregator.core.orm import event
from aggregator.core.orm.helpers import _session, resolve_oui
from aggregator.core.orm.models import MAC
from aggregator.tools import logger


def backfill_mac_oui():
    """
    Adds missing mapping between MAC and OUI.
    """
    with _session() as db:
        try:
            macs = (
                db.query(MAC).filter(and_(MAC.uaa.is_(True), MAC.oui.is_(None))).all()
            )

            for mac in tqdm(macs, desc="Updating MAC data", unit="mac"):
                resolve_oui(db, mac)

            db.commit()
        except Exception as e:
            logger.warning(f"Failed to load csv - {e}")
            db.rollback()


if __name__ == "__main__":
    logger.info("Starting the backfill for MAC OUI.")
    backfill_mac_oui()
    logger.info("Finished.")

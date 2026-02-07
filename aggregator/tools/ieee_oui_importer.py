import csv
import os
import re

from aggregator.core.orm.helpers import _session, get_country_id_with_alpha2
from aggregator.core.orm.models import IEEEMacOui, IEEEMacOuiOrg

from . import logger

# Fix for pipeline.
if os.getenv("ENV") != "test":
    from tqdm import tqdm

# From https://regauth.standards.ieee.org/standards-ra-web/pub/view.html
CSV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ieee_oui.csv")
ALPHA2_REGEX = re.compile(r"\b([A-Z]{2})\b")


def extract_country_id(address, cache):
    """
    Extract alpha-2 country code from address.
    Returns uppercase alpha-2 or None if not found.
    """
    # Not the best solution using ALPHA2_REGEX as it will skip about 3.5k records.
    # This is why we check every find. We reverse it as the address is often like "*IL US*"
    tokens = ALPHA2_REGEX.findall(address.upper())
    if not tokens:
        return None

    for alpha2 in reversed(tokens):
        if alpha2 in cache:
            return cache[alpha2]

        country = get_country_id_with_alpha2(alpha2)

        if country:
            cache[alpha2] = country.id
            return country.id

    return None


def load_csv(path=CSV_FILE):
    # simple in-memory cache
    org_cache = {}  # org_name -> IEEEMacOuiOrg
    country_cache = {}  # alpha2 -> country_id

    with _session() as db:
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row in tqdm(reader, desc="Importing records", unit="record"):
                    registry = row["Registry"].strip()
                    assignment = row["Assignment"].strip()
                    org_name = row["Organization Name"].strip()
                    address = row["Organization Address"].strip()

                    # get or create org
                    org = org_cache.get(org_name)
                    if org is None:
                        country_id = None

                        if address and address != "":
                            country_id = extract_country_id(address, country_cache)

                        org = IEEEMacOuiOrg(
                            name=org_name, address=None if not address or address == "" else address, country=country_id
                        )
                        db.add(org)
                        db.flush()

                        org_cache[org_name] = org

                    oui = IEEEMacOui(
                        registry=registry,
                        assignment=assignment,
                        org=org.id,
                    )
                    db.add(oui)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to load csv - {e}")
            db.rollback()


if __name__ == "__main__":
    logger.info("Starting the importer.")
    load_csv()
    logger.info("Finished.")

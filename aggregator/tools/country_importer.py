import csv
import os

from aggregator.core.orm.helpers import _session
from aggregator.core.orm.models import Country

from . import logger

# From https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes/blob/master/all/all.csv
CSV_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "iso-3166-countries.csv"
)


def load_csv(path=CSV_FILE):
    with _session() as db:
        try:
            with open(path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                countries = []
                for row in reader:
                    country = Country(
                        name=row["name"],
                        alpha2=row["alpha-2"],
                        alpha3=row["alpha-3"],
                        country_code=row["country-code"],
                        region=row.get("region") or None,
                        sub_region=row.get("sub-region") or None,
                        intermediate_region=row.get("intermediate-region") or None,
                        region_code=(
                            int(row["region-code"]) if row.get("region-code") else None
                        ),
                        sub_region_code=(
                            int(row["sub-region-code"])
                            if row.get("sub-region-code")
                            else None
                        ),
                        intermediate_region_code=(
                            int(row["intermediate-region-code"])
                            if row.get("intermediate-region-code")
                            else None
                        ),
                    )
                    countries.append(country)

                db.bulk_save_objects(countries)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to load csv - {e}")
            db.rollback()


if __name__ == "__main__":
    logger.info("Starting the importer.")
    load_csv()
    logger.info("Finished.")

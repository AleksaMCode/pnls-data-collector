from datetime import datetime

from sqlalchemy import desc

from core.orm import _session
from core.orm.models import MAC, SSID, CapturedInfo, ImportsInfo, LocationMapping
from settings import MAC_FILTER, TIMESTAMP_FORMAT
from util import clean_string


def get_latest_import_date():
    with _session() as db:
        return (
            db.query(ImportsInfo)
            .order_by(desc(ImportsInfo.timestamp))
            .first()
            .timestamp
        )


def import_data(data):
    with _session() as db:
        # Cache existing SSIDs and MACs for fast lookup
        ssid_map = {s.ssid: s.id for s in db.query(SSID).all()}
        mac_map = {m.mac: m.id for m in db.query(MAC).all()}

        captured_records = []
        for record in data:
            device_name = record.get("device")
            ssid_str = clean_string(record.get("ssid"))
            # TODO Decrypt the MAC address here
            mac_str = record.get("mac")

            if mac_str in MAC_FILTER:
                continue

            timestamp_str = record.get("timestamp")

            if not ssid_str or not mac_str or not timestamp_str:
                continue

            ts = datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)

            ssid_id = ssid_map.get(ssid_str)
            if not ssid_id:
                ssid_obj = SSID(ssid=ssid_str)
                db.add(ssid_obj)
                db.flush()
                ssid_map[ssid_str] = ssid_obj.id
                ssid_id = ssid_obj.id

            mac_id = mac_map.get(mac_str)
            if not mac_id:
                mac_obj = MAC(mac=mac_str)
                db.add(mac_obj)
                db.flush()
                mac_map[mac_str] = mac_obj.id
                mac_id = mac_obj.id

            mapping = db.query(LocationMapping).filter_by(device=device_name).first()
            if not mapping:
                print(
                    f"No location mapping found for device {device_name}, skipping record."
                )
                continue

            location_id = mapping.location_id
            captured_records.append(
                CapturedInfo(
                    ssid=ssid_id, mac=mac_id, location=location_id, timestamp=ts
                )
            )

        if captured_records:
            db.add_all(captured_records)
            db.add(ImportsInfo(captured=len(captured_records)))
            try:
                db.commit()
                print(f"Imported {len(captured_records)} new captured records.")
            except Exception as e:
                db.rollback()
                print(f"Failed to add new captured records - {str(e)}")

from datetime import date

from aggregator.util.util import send_webhook_message


def publish_to_channel(data: dict, probe_req_count: int, import_date: date = None):
    # This is tightly coupled with stats data from firebase#publish_stats_data.
    first_line = (
        "**Today's data has been aggregated.**\n"
        if not import_date
        else f"**Data imported for date '{import_date}'.**\n"
    )

    mattermost_msg = (
        first_line
        + f"(Captured Probe Requests: **{probe_req_count}**)\n"
        + f"* Total captured probe requests: {data['total_count']}\n"
        + f"* Total captured unique MAC addresses: {data['mac_count']}\n"
        + f"* Total captured unique SSIDs: {data['ssid_count']}\n"
    )
    send_webhook_message(mattermost_msg)

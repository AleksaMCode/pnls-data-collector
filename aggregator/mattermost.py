from datetime import date

from aggregator.util.util import send_webhook_message


def publish_to_channel(data: dict, probe_req_count: int, import_date: date = None):
    # This is tightly coupled with stats data from firebase#publish_stats_data.
    mattermost_msg = (
        f"**Today's data has been aggregated.**\n"
        if import_date is None
        else f"**Data imported for date '{import_date}'.**\n"
        f"(Total captured Probe Requests today: **{probe_req_count}**)"
        f"* Total captured probe requests: {data['total_count']}\n"
        f"* Total captured unique MAC addresses: {data['mac_count']}\n"
        f"* Total captured unique SSIDs: {data['ssid_count']}\n"
    )
    send_webhook_message(mattermost_msg)

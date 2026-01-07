from datetime import date

from aggregator.util.util import send_webhook_message


def publish_to_channel(data: dict, probe_req_count: int, import_date: date = None):
    # This is tightly coupled with stats data from firebase#publish_stats_data.
    mattermost_msg = f"""{
        f"**Today's data has been aggregated.**" if not import_date
        else f"**Data imported for date '{import_date}'.**"
    }
    (Total captured Probe Requests: **{probe_req_count}**)
    * Total captured probe requests: {data['total_count']}
    * Total captured unique MAC addresses: {data['mac_count']}
    * Total captured unique SSIDs: {data['ssid_count']}
    """
    send_webhook_message(mattermost_msg)

from aggregator.core.firebase.helpers import publish_devices_data


def publish_all_data():
    publish_devices_data()


if __name__ == "__main__":
    publish_all_data()

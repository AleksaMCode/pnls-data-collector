from aggregator.core.firebase.helpers import publish_manufacturers_data


def publish_all_data():
    publish_manufacturers_data()


if __name__ == "__main__":
    # To be used for bulk import
    publish_all_data()

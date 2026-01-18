from aggregator.core.mongo.helpers import insert_from_firebase_to_mongo

from .firebase import delete_all_by_nodes, download_all

if __name__ == "__main__":
    data = download_all()
    insert_from_firebase_to_mongo(data)
    delete_all_by_nodes()

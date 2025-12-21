import os

# Pipeline fix. See #45
if os.getenv("ENV") != "test":
    import gridfs
    import pymongo
    from dotenv import load_dotenv
    load_dotenv()

connection_url = (
    f"mongodb://{os.getenv("MONGO_USERNAME")}"
    f":{os.getenv("MONGO_PASSWORD")}@{os.getenv("MONGO_URL")}:{os.getenv("MONGO_PORT")}"
    f"/{os.getenv("MONGO_DB")}?authSource={os.getenv("MONGO_AUTH_SOURCE")}"
)


client = pymongo.MongoClient(connection_url)

db = client[os.getenv("MONGO_DB")]


def get_collection(collection: str):
    return db[collection]


def get_bucket_for_write():
    return gridfs.GridFSBucket(db)


def get_bucket_for_read():
    return gridfs.GridFS(db)

import io
import json
from datetime import datetime

from yaspin import yaspin

from firebase_housekeeping.settings import TIMESTAMP_FORMAT
from util.core.orm.models import Device
from util.logger import get_logger

from . import get_bucket_for_read, get_bucket_for_write, get_collection

logger = get_logger(__name__)


def read_all_firebase_data_from_mongo():
    fs = get_bucket_for_read()
    for file in fs.list():
        read_firebase_data_from_mongo(file)


def read_firebase_data_from_mongo(file_name):
    fs = get_bucket_for_write()
    try:
        memory_file = fs.open_download_stream_by_name(filename=file_name)
        fs.find()
        if memory_file:
            downloaded_data = json.loads(memory_file.read().decode("utf-8"))
            # TODO Implement download of data to file system.
            logger.info(f"Successfully read file with filename {file_name}.")
        else:
            logger.warning(f"No file found for {file_name}.")
    except Exception as e:
        logger.error(f"Error reading data for {file_name}: {e}")


def insert_from_firebase_to_mongo(data: dict):
    """
    Insert data from Firebase into MongoDB.
    Data is downloaded using firebase.download_all.
    PNLS data is large and should be batched.
    """
    bucket = get_bucket_for_write()

    for key, value in data.items():
        device_data_bytes = json.dumps(value).encode("utf-8")
        memory_file = io.BytesIO(device_data_bytes)
        try:
            file_id = bucket.upload_from_stream(
                f"{Device(key).value}-{datetime.today().strftime(TIMESTAMP_FORMAT.split(' ')[0])}",
                memory_file,
            )
            logger.info(
                f"Uploaded data (id={file_id}) from Firebase to MongoDB for {key}."
            )
        except Exception as e:
            logger.error(
                f"There was an error while uploading data to MongoDB bucket: {e}"
            )


def insert_many(data, collection: str):
    collection = get_collection(collection)
    res = collection.insert_many(data)
    if not res.acknowledged:
        logger.error(f"Insert into MongoDB collection {collection} wasn't successful.")

    logger.info(f"Insert into MongoDB collection {collection} is completed.")


def insert_one(data, collection: str):
    collection = get_collection(collection)
    res = collection.insert_many(data)
    if not res.acknowledged:
        logger.error(f"Insert into MongoDB collection {collection} wasn't successful.")


@yaspin("Inserting device data into MongoDB")
def insert_data_into_collection(data, collection: str):
    logger.info(f"Starting inserting data into MongoDB collection {collection}.")
    try:
        insert_many(data, collection)
    except Exception as e:
        logger.error(f"Insert into MongoDB collection {collection} failed due to {e}.")

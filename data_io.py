import os
import json
import logging
import requests

import pandas as pd

from utils.utils import strcut
from google.cloud import storage
from google.oauth2 import service_account


LOGGER = logging.getLogger(__name__)


class GoogleObjectStore(object):

    def __init__(self, bucket_name, credentials):
        self.bucket_name = bucket_name
        self.credentials = credentials
        self.storage_client = storage.Client(
            credentials=service_account.Credentials.from_service_account_info(credentials)
        )
        self.bucket = self.storage_client.bucket(bucket_name)

    def __repr__(self):
        return f"GoogleObjectStore(bucket='{self.bucket_name}', credentials={strcut(str(self.credentials))})"

    def __getitem__(self, key):
        blob = self.bucket.blob(key)
        with blob.open("r") as f:
            LOGGER.debug(f"Reading from '{key}'")
            return f.read()

    def __setitem__(self, key, value):
        blob = self.bucket.blob(key)
        with blob.open("w") as f:
            LOGGER.debug(f"Writing to '{key}'")
            f.write(value)


def load_file(item, io_type="os", prefix="", **kwargs):
    # override file type or derive from item name
    file_type = kwargs.get("file_type", os.path.split(item)[-1].split(".")[-1])

    LOGGER.info(f"Loading [{prefix}]'{item}' of type '{file_type}' from '{io_type}'")
    if io_type == "os":
        if file_type == "json":
            return json.load(open(os.path.join(prefix, item), "r"))
    elif io_type == "url":
        if file_type == "json":
            return requests.get(prefix + item).json()
    elif io_type == "google_storage":
        object_store = GoogleObjectStore(bucket_name=kwargs["bucket_name"], credentials=kwargs["credentials"])
        if file_type == "json":
            return json.loads(object_store[prefix + item])

    LOGGER.error(f"Loading of type '{io_type}' for file type '{file_type}' not currently supported")


def save_file(item, data, io_type="os", prefix="", **kwargs):
    # override file type or derive from item name
    file_type, saved = kwargs.get("file_type", os.path.split(item)[-1].split(".")[-1]), True

    LOGGER.info(f"Saving [{prefix}]'{item}' of type '{file_type}' to '{io_type}'")
    if io_type == "os":
        if file_type == "*":
            open(os.path.join(prefix, item), "w").write(data)
        elif file_type == "json":
            json.dump(data, open(os.path.join(prefix, item), "w"))
        else:
            saved = False
    elif io_type == "google_storage":
        object_store = GoogleObjectStore(bucket_name=kwargs["bucket_name"], credentials=kwargs["credentials"])
        if file_type == "*":
            object_store[prefix + item] = data
        elif file_type == "json":
            object_store[prefix + item] = json.dumps(data)
        else:
            saved = False
    else:
        saved = False

    if not saved:
        LOGGER.error(f"Saving of type '{io_type}' for file type '{file_type}' not currently supported")


if __name__ == "__main__":
    df = pd.read_csv("/Users/andrewsanderson/Desktop/logs/pokemon_index_cache.csv")

    cred = load_file("google-cloud-credentials.json", io_type="os", prefix="/Users/andrewsanderson/Documents/dev/tennis-booking/.secrets")

    obj_store = GoogleObjectStore(bucket_name="tennis_booking", credentials=cred)
    obj_store["test_object.json"] = df.head().to_json()  # i.e. convert pokemon index cache inputs to a JSON for GCP storage

    assert obj_store["test_object.json"] == df.head().to_json()  # test the round-trip

    print(load_file(r"/Users/andrewsanderson/Desktop/logs/pokemon_index.json"))
    print(load_file(item="pokemon_index.json", io_type="os", prefix="/Users/andrewsanderson/Desktop/logs"))
    d = load_file(
        item="index_level.json", io_type="google_storage", bucket_name="tennis_booking", credentials=cred
    )
    print(d)
    assert isinstance(d, dict)

from cfg.cfg import GOOGLE_CLOUD_CREDENTIALS
from data_io import load_file, save_file  # , GoogleObjectStore


env = "DEV"  # PRD
deploy = False  # ONLY CHANGE TO TRUE IF OK TO OVERWRITE GOOGLE STORAGE DATA
# object_store = GoogleObjectStore(bucket_name="tennis_booking", credentials=GOOGLE_CLOUD_CREDENTIALS)
save_file_args = dict(io_type="google_storage", bucket_name="tennis_booking", credentials=GOOGLE_CLOUD_CREDENTIALS)


if deploy:
    # deploy application configuration (used across both back and front-end)
    cfg = load_file(f"/Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/cfg/{env}.cfg.json", io_type="os")
    # object_store[f"{env}.cfg.json"] = json.dumps(cfg)
    save_file(f"{env}.cfg.json", cfg, **save_file_args)  # dictionary -> JSON

    # deploy the cache data
    cache = load_file(f"/Users/andrewsanderson/Documents/dev/tower-hamlets-tennis-court-watcher/cfg/{env}.cache.json", io_type="os")
    # object_store[f"{env}.cache.json"] = json.dumps(cache)
    save_file(f"{env}.cache.json", cache, **save_file_args)  # dictionary -> JSON

    print(f"Deployed data to '{env}'")
else:
    print("Not deploying data")

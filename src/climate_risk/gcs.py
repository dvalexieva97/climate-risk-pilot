from __future__ import annotations

import logging
from pathlib import Path

from google.cloud import storage

from climate_risk.config import AppConfig

logger = logging.getLogger(__name__)


def upload_file(local_path: Path, config: AppConfig, object_name: str | None = None) -> str | None:
    if not config.gcs.upload or not config.gcs.bucket:
        logger.debug("GCS upload skipped (upload=%s, bucket=%s)", config.gcs.upload, config.gcs.bucket)
        return None

    client = storage.Client()
    bucket = client.bucket(config.gcs.bucket)
    blob_name = f"{config.gcs.prefix.rstrip('/')}/{object_name or local_path.name}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(local_path))
    uri = f"gs://{config.gcs.bucket}/{blob_name}"
    logger.info("Uploaded %s -> %s", local_path, uri)
    return uri


def upload_tree(local_dir: Path, config: AppConfig, suffixes: tuple[str, ...] = (".tif", ".parquet", ".json")) -> list[str]:
    uris: list[str] = []
    for path in local_dir.rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            rel = path.relative_to(local_dir)
            uri = upload_file(path, config, object_name=str(rel).replace("\\", "/"))
            if uri:
                uris.append(uri)
    return uris

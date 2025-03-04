"""
azure_blob.py
-----------------------------------------------------------------------------------
Minimal wrapper around Azure Blob Storage for managing FAISS index files.

Key ideas
---------
* Each environment (prod / staging / dev) stores its blobs under a prefix such
  as "prod/" so that indexes never clash.
* Every index comes in two names:
    1.  <prefix><kind>_<YYYYMMDDHHMMSS>.faiss    ← immutable, versioned snapshot
    2.  <prefix><kind>_latest.faiss              ← copy of the most recent snapshot
  The upload helper first writes the versioned file, then does a server-side
  copy to update the *latest* alias atomically.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from azure.storage.blob import BlobClient, ContainerClient
from django.conf import settings
import tempfile, shutil, os
from azure.storage.blob import generate_blob_sas, BlobSasPermissions


CONN  = settings.AZURE_STORAGE_CONNECTION_STRING
CONT  = settings.FAISS_CONTAINER
PREF  = settings.FAISS_PREFIX.rstrip("/") + "/"


# Internal helper: return a BlobClient for a given blob *name* (path inside container)
def _blob(name: str) -> BlobClient:
    return BlobClient.from_connection_string(CONN, container_name=CONT, blob_name=name)

# Public helper #1 : Download the "latest" version of an index to local disk
def download_latest(kind: str, dest: Path):
    latest_name = f"{PREF}{kind}_latest.faiss"
    blob = _blob(latest_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as fh:
        fh.write(blob.download_blob().readall())

# Public helper #2 : Upload a *new* index version and update the "latest" alias
def upload_version(kind: str, src_path: Path):
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    version_name = f"{PREF}{kind}_{ts}.faiss"
    latest_name  = f"{PREF}{kind}_latest.faiss"

    # 1. upload versioned blob
    _blob(version_name).upload_blob(src_path.read_bytes(), overwrite=True)

    # 2. build a read-only SAS for the new version
    sas = generate_blob_sas(
        account_name      = settings.AZURE_STORAGE_ACCOUNT_NAME,
        account_key       = settings.AZURE_STORAGE_ACCOUNT_KEY,
        container_name    = settings.FAISS_CONTAINER,
        blob_name         = version_name,
        permission        = BlobSasPermissions(read=True),
        expiry            = datetime.utcnow() + timedelta(minutes=20),
    )
    source_url = f"{_blob(version_name).url}?{sas}"

    # 3. server-side copy -> latest
    _blob(latest_name).start_copy_from_url(source_url, requires_sync=True)

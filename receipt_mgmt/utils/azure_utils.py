# utils/azure_utils.py
import uuid
from datetime import datetime, timedelta, timezone

from django.conf import settings
from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)

ALLOWED_IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}

CONTAINER = getattr(settings, "AZURE_BLOB_CONTAINER_NAME", "receipt-images")
ACCOUNT   = settings.AZURE_STORAGE_ACCOUNT_NAME
KEY       = settings.AZURE_STORAGE_ACCOUNT_KEY      # or use DefaultAzureCredential

# ---------- upload ---------- #
def upload_receipt_image(image_data: bytes, content_type: str, *, user_id: int) -> str:
    """
    Upload a single image to a **private** container.
    Returns only the blob NAME (e.g. 'user_42/abcd.jpg').
    """

    # 1) Ensure the caller provided an imae type we explicitly allow
    #    (e.g. 'image/png', 'image/jpeg').  The mapping
    #    ALLOWED_IMAGE_TYPES = {"image/png": "png", ...} is defined above.
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")

    # 2) Build a globally-unique blob name in the pattern
    #       user_<id>/<uuid4>.<ext>
    #    This keeps each user’s blobs in a pseudo-directory while avoiding
    #    name collisions.  Only the *name* is persisted to the DB; the
    #    container itself remains private.
    ext       = ALLOWED_IMAGE_TYPES[content_type]
    blob_name = f"user_{user_id}/{uuid.uuid4()}.{ext}"     # <── this is what we store

    # 3) Connect to Azure Blob Storage using the account-level connection
    #    string held in settings.  We then get a client scoped to our
    #    single private CONTAINER and the specific blob_name we just built.
    blob_service = BlobServiceClient.from_connection_string(
        settings.AZURE_STORAGE_CONNECTION_STRING
    )
    blob_client = blob_service.get_blob_client(CONTAINER, blob_name)

    # 4) Upload the raw bytes.  `overwrite=True` lets us retry safely if a
    #    transient error occurred and the same blob_name was already created.
    #    We also set the Content-Type so Azure serves the file correctly.
    blob_client.upload_blob(image_data, overwrite=True, content_type=content_type)

    # 5) Return only the blob_name so callers can store it on the Receipt
    #    and later generate a short-lived SAS URL for secure access.
    return blob_name


# ---------- download (SAS) ---------- #
def make_private_download_url(blob_name: str, *, minutes: int = 5) -> str:
    """
    Build a read-only SAS URL valid for `minutes` (default 5).
    """

    # 1) Determine when the URL should expire.
    #    Using UTC avoids any local-time ambiguity when Azure verifies the expiry.
    expiry = datetime.now(timezone.utc) + timedelta(minutes=minutes)

    # 2) Create a Shared-Access-Signature (SAS) token that grants **read-only**
    #    rights to this specific blob until the expiry time.  The token embeds:
    #      • storage account name
    #      • container name
    #      • blob name
    #      • account key (for signing)
    #      • permission flags (read=True)
    #      • expiry timestamp
    #      • https_only=True enforces TLS
    sas = generate_blob_sas(
        account_name   = ACCOUNT,
        container_name = CONTAINER,
        blob_name      = blob_name,
        account_key    = KEY,
        permission     = BlobSasPermissions(read=True),
        expiry         = expiry,
        https_only     = True,
    )
    # 3) Return the full URL that the client can use to download the file
    #    directly from Azure Blob Storage.  Once the SAS expires, the link
    #    will no longer work
    return f"https://{ACCOUNT}.blob.core.windows.net/{CONTAINER}/{blob_name}?{sas}"
 
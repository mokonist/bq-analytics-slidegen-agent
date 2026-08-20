import os
import uuid
import logging
import asyncio
from google.cloud.storage import Client

def get_storage_client() -> Client:
    """Gets the GCS client using Application Default Credentials / environment."""
    return Client()

async def upload_data_to_gcs(
    bucket_name: str,
    data: bytes,
    content_type: str = "image/png"
) -> str:
    """
    Uploads binary data to GCS and returns a URL.
    - If PUBLIC_BUCKET is true: returns https://storage.googleapis.com/[BUCKET]/[OBJECT] (public)
    - If PUBLIC_BUCKET is false: returns https://storage.cloud.google.com/[BUCKET]/[OBJECT] (authenticated)
    """
    try:
        client = get_storage_client()
        bucket = client.bucket(bucket_name)
        
        # Generate a unique filename
        filename = f"{uuid.uuid4()}.png"
        blob = bucket.blob(filename)
        
        # Upload the data using a thread to avoid blocking the event loop
        logging.info(f"Uploading image {filename} to bucket {bucket_name}")
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        
        # Determine URL format based on bucket visibility
        is_public = os.environ.get("PUBLIC_BUCKET", "false").lower() in ("true", "1", "yes")
        if is_public:
            # Public access URL: https://storage.googleapis.com/[BUCKET_NAME]/[OBJECT_NAME]
            url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
        else:
            # Authenticated URL: https://storage.cloud.google.com/[BUCKET_NAME]/[OBJECT_NAME]
            url = f"https://storage.cloud.google.com/{bucket_name}/{filename}"
            
        logging.info(f"Successfully uploaded to {url} (public={is_public})")
        return url
        
    except Exception as e:
        logging.error(f"Error uploading to GCS: {str(e)}")
        # Return empty string to signal failure upstream
        return ""


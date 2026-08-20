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
    Uploads binary data to GCS and returns a storage.cloud.google.com URL.
    This URL requires the user to be authenticated to Google Cloud to view.
    
    Args:
        bucket_name (str): The name of the GCS bucket.
        data (bytes): The binary data to upload.
        content_type (str): The MIME type of the data.
        
    Returns:
        str: The URL to the uploaded object.
    """
    try:
        client = get_storage_client()
        # Use factory pattern (bucket()) instead of get_bucket() which requires more IAM permissions
        bucket = client.bucket(bucket_name)
        
        # Generate a unique filename
        filename = f"{uuid.uuid4()}.png"
        blob = bucket.blob(filename)
        
        # Upload the data using a thread to avoid blocking the event loop
        logging.info(f"Uploading image {filename} to bucket {bucket_name}")
        await asyncio.to_thread(blob.upload_from_string, data, content_type=content_type)
        
        # Return the authenticated URL format as requested
        # Format: https://storage.cloud.google.com/[BUCKET_NAME]/[OBJECT_NAME]
        url = f"https://storage.cloud.google.com/{bucket_name}/{filename}"
        logging.info(f"Successfully uploaded to {url}")
        return url
        
    except Exception as e:
        logging.error(f"Error uploading to GCS: {str(e)}")
        # Return empty string to signal failure upstream
        return ""

import os
import logging
from google import genai
from google.genai import types

from ..media_models import MediaAsset
from ..storage_utils import upload_data_to_gcs

logger = logging.getLogger(__name__)

# GCS Bucket from environment variable (injected via deploy.sh / .env)
GCS_BUCKET = os.environ.get("GCS_BUCKET")
MAX_RETRIES = 5

# Initialize the GenAI client once
genai_client = genai.Client(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(
            attempts=MAX_RETRIES,
            initial_delay=2.0,
            max_delay=60.0,
            http_status_codes=[429]
        )
    )
)

async def generate_slide_image(
    prompt: str,
) -> str:
    """Generates a 1-Pager slide image based on the prompt using Gemini 3 Flash Image model.
    Use this tool ONLY when the user explicitly agrees to create a slide.
    
    Args:
        prompt (str): Detailed instruction to generate a slide image including textual content and visual style.
    
    Returns:
        str: A message containing the markdown image link `![Slide](url)` of the generated image, or an error text.
    """
    if not GCS_BUCKET:
        logger.error("GCS_BUCKET environment variable is not configured.")
        return "エラー: 画像の保存先 GCS バケット (GCS_BUCKET) が設定されていません。"

    logger.info(f"Generating image with prompt: {prompt}")
    
    content = types.Content(
        parts=[types.Part.from_text(text=prompt)],
        role="user"
    )

    asset = MediaAsset(uri="")
    
    for attempt in range(MAX_RETRIES):
        try:
            # Use the async client (.aio)
            response = await genai_client.aio.models.generate_content(
                model="gemini-3.1-flash-image",
                contents=[content],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                    )
                )
            )
            
            if response and response.parts:
                for part in response.parts:
                    # Some endpoints return file_uri
                    if part.file_data and part.file_data.file_uri:
                        asset = MediaAsset(uri=part.file_data.file_uri)
                        break
                    # The image generation usually returns inline_data (base64/bytes)
                    if part.inline_data and part.inline_data.data:
                        # Upload the raw bytes to GCS
                        url = await upload_data_to_gcs(
                            GCS_BUCKET,
                            part.inline_data.data,
                            part.inline_data.mime_type or "image/png"
                        )
                        asset = MediaAsset(uri=url)
                        break
            if asset.uri:
                break
                
        except Exception as e:
            logger.error(f"Error calling generate_content (attempt {attempt + 1}/{MAX_RETRIES}): {str(e)}")
            continue

    if not asset.uri:
        return "画像の生成に失敗しました。"
    
    logger.info(f"Image URL: {asset.uri}")
    return f"![Generated Slide]({asset.uri})"

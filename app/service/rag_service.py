import asyncio
import httpx
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from functools import partial
from typing import List
from app.core.logging import logger
from app.core.config import config

# Singleton HTTP client — reused across all requests (connection pool)
_http_client: httpx.AsyncClient = httpx.AsyncClient(timeout=10.0)

# Singleton boto3 S3 client — created once at module load
_s3_client = boto3.client(
    "s3",
    aws_access_key_id=config.ACCESS_KEY_ID,
    aws_secret_access_key=config.SECRET_ACCESS_KEY,
    region_name=config.REGION,
)


async def fetch_relevant_chunks(query: str, top_k: int = 5) -> List[dict]:
    """Fetches the most relevant chunks from the RAG service based on the provided query."""
    try:
        token = config.RAG_SERVICE_TOKEN
        headers = {"accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = await _http_client.get(
            config.RAG_SERVICE,
            params={"query": query, "top_k": top_k},
            headers=headers,
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting RAG service: {e}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"RAG service returned an error: {e.response.status_code} - {e.response.text}")
        return []


async def fetch_document_url_from_s3(document_ids: List[str], user_id: str) -> List[str]:
    """Fetches the document URLs from S3 based on the provided document IDs."""
    try:
        loop = asyncio.get_event_loop()
        urls = []
        for doc_id in document_ids:
            key = f"{config.S3_SOURCE_PATH.rstrip('/')}/{user_id}/{doc_id}"
            # Run blocking boto3 call in thread pool to avoid blocking the event loop
            generate = partial(
                _s3_client.generate_presigned_url,
                "get_object",
                Params={"Bucket": config.S3_BUCKET_NAME, "Key": key},
                ExpiresIn=300,
            )
            url = await loop.run_in_executor(None, generate)
            urls.append(url)
        return urls
    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to generate presigned URLs from S3: {e}")
        return []
       
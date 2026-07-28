import asyncio
from functools import partial
from typing import List

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import config
from app.core.logging import logger

# Singleton HTTP client — reused across all requests (connection pool)
_http_client: httpx.AsyncClient = httpx.AsyncClient(
    timeout=httpx.Timeout(config.RAG_SERVICE_TIMEOUT_SECONDS, connect=3.0)
)

# Singleton boto3 S3 client — created once at module load
_s3_client = boto3.client(
    "s3",
    region_name=config.REGION,
    endpoint_url=f"https://s3.{config.REGION}.amazonaws.com",
    config=boto3.session.Config(signature_version="s3v4"),
)


async def fetch_relevant_chunks(
    query: str,
    top_k: int = None,
    auth_header: str = None,
    source_document_ids: List[str] = None,
) -> List[dict]:
    """Fetches relevant chunks from the RAG service with optional document scoping."""
    try:
        headers = {"accept": "application/json"}
        if auth_header:
            headers["Authorization"] = auth_header

        params = {"query": query, "top_k": top_k or config.RAG_TOP_K}
        if source_document_ids:
            params["document_ids"] = ",".join(source_document_ids)

        response = await _http_client.get(config.RAG_SERVICE, params=params, headers=headers)
        response.raise_for_status()
        return response.json().get("results", [])
    except httpx.RequestError as e:
        logger.error(f"An error occurred while requesting RAG service: {e}")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"RAG service returned an error: {e.response.status_code} - {e.response.text}")
        return []


async def fetch_document_url_from_s3(document_ids: List[str], user_id: str) -> List[str]:
    """Fetch document URLs from S3 concurrently for lower latency."""
    if not document_ids or not user_id:
        return []

    loop = asyncio.get_running_loop()

    async def one_url(doc_id: str):
        try:
            key = f"{config.S3_SOURCE_PATH.rstrip('/')}/{user_id}/{doc_id}"
            generate = partial(
                _s3_client.generate_presigned_url,
                "get_object",
                Params={"Bucket": config.S3_BUCKET_NAME, "Key": key},
                ExpiresIn=300,
            )
            return await loop.run_in_executor(None, generate)
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to generate presigned URL for {doc_id}: {e}")
            return None

    urls = await asyncio.gather(*(one_url(doc_id) for doc_id in document_ids))
    return [url for url in urls if url]

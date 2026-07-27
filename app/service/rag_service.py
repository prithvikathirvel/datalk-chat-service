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
    region_name=config.REGION,
    endpoint_url=f"https://s3.{config.REGION}.amazonaws.com",
    config=boto3.session.Config(signature_version="s3v4"),
)


async def fetch_relevant_chunks(
    query: str,
    top_k: int = 5,
    auth_header: str = None,
    source_document_ids: List[str] = None,
) -> List[dict]:
    """Fetches the most relevant chunks from the RAG service based on the provided query.

    When `source_document_ids` is provided (non-empty), the RAG service is
    asked to restrict retrieval to those document IDs — used to scope an
    embed widget's chatbot to a specific set of documents (see
    `embed_config_sources`). Filtering is requested at the vector-search
    layer (pre-retrieval) for efficiency; `fetch_data` additionally
    re-filters the returned chunks as a safety net.
    """
    try:
        #token = config.RAG_SERVICE_TOKEN
        headers = {"accept": "application/json"}
        # if token:
        #     headers["Authorization"] = f"Bearer {token}"
        if auth_header:
            headers["Authorization"] = auth_header

        params = {"query": query, "top_k": top_k}
        if source_document_ids:
            # Sent as a comma-separated list; adjust to match the RAG
            # service's actual filter parameter contract once confirmed.
            params["document_ids"] = ",".join(source_document_ids)

        response = await _http_client.get(
            config.RAG_SERVICE,
            params=params,
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
       
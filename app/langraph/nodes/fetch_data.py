import time

from app.core.config import config as settings
from app.core.logging import logger
from app.langraph.schema import AgentState
from langchain_core.runnables import RunnableConfig
from app.service.rag_service import fetch_document_url_from_s3, fetch_relevant_chunks
from app.langraph.utils.helper import get_last_human_message


async def fetch_data(agent_state: AgentState, config: RunnableConfig):
    logger.info("[fetch_data] Node entered")
    try:
        messages = agent_state["messages"]
        configurable = config.get("configurable", {})
        user_id = configurable.get("user_id")
        auth_header = configurable.get("auth_header")
        source_document_ids = configurable.get("source_document_ids")
        standalone_query = agent_state.get("standalone_query") or get_last_human_message(messages)
        original_query = get_last_human_message(messages)
        multi_hop = any(
            marker in standalone_query.lower()
            for marker in (" compare ", " versus ", " vs ", " and ", " between ", "difference", "both", "each")
        ) or standalone_query.count("?") > 1
        top_k = settings.RAG_TOP_K_MULTI_HOP if multi_hop else settings.RAG_TOP_K

        logger.info(
            f"[fetch_data] query={standalone_query!r}, top_k={top_k}, user_id={user_id!r}, "
            f"source_document_ids={source_document_ids!r}"
        )
        started = time.perf_counter()
        results = await fetch_relevant_chunks(
            standalone_query,
            top_k=top_k,
            auth_header=auth_header,
            source_document_ids=source_document_ids,
        )
        logger.info(f"[fetch_data] Attempt 1 raw results: {len(results)}")

        if not results and original_query and original_query != standalone_query:
            logger.info(f"[fetch_data] Attempt 2 — original query={original_query!r}")
            results = await fetch_relevant_chunks(
                original_query,
                top_k=settings.RAG_FALLBACK_TOP_K,
                auth_header=auth_header,
                source_document_ids=source_document_ids,
            )
            logger.info(f"[fetch_data] Attempt 2 raw results: {len(results)}")
        retrieval_response_time_ms = round((time.perf_counter() - started) * 1000, 2)

        retrieved_texts = []
        seen_texts = set()
        seen_doc_ids = set()
        document_ids = []
        allowed_doc_ids = set(source_document_ids) if source_document_ids else None

        for res in results:
            meta = res.get("metadata") or {}
            text = (meta.get("text") or res.get("text") or res.get("content") or res.get("page_content") or "").strip()
            doc_id = meta.get("document_id") or res.get("document_id") or meta.get("doc_id") or res.get("doc_id") or ""

            if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                continue
            if text and text not in seen_texts:
                seen_texts.add(text)
                retrieved_texts.append(text)
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                document_ids.append(doc_id)

        if not retrieved_texts:
            logger.info("[fetch_data] No chunks retrieved")
            return {
                "retrieved_texts": [],
                "document_ids": [],
                "source_documents": [],
                "retrieval_response_time_ms": retrieval_response_time_ms,
            }

        logger.info(f"[fetch_data] Fetching S3 URLs for {len(document_ids)} unique document(s)")
        source_documents = await fetch_document_url_from_s3(document_ids, user_id=user_id)

        logger.info(
            f"[fetch_data] Done: {len(retrieved_texts)} chunks, {len(document_ids)} docs, "
            f"{len(source_documents)} source URLs, retrieval={retrieval_response_time_ms}ms"
        )
        return {
            "retrieved_texts": retrieved_texts,
            "document_ids": document_ids,
            "source_documents": source_documents,
            "retrieval_response_time_ms": retrieval_response_time_ms,
        }
    except Exception as e:
        logger.error(f"[fetch_data] Error: {e}")
        return {"retrieved_texts": [], "document_ids": [], "source_documents": [], "retrieval_response_time_ms": 0.0}

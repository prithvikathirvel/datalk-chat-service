import time

from app.langraph.schema import AgentState
from langchain_core.runnables import RunnableConfig
from app.service.rag_service import fetch_document_url_from_s3, fetch_relevant_chunks
from app.core.logging import logger
from app.langraph.utils.helper import get_last_human_message


async def fetch_data(agent_state: AgentState, config: RunnableConfig):
    logger.info("[fetch_data] Node entered")
    try:
        messages = agent_state["messages"]
        user_id = config["configurable"]["user_id"]
        auth_header = config["configurable"]["auth_header"]
        standalone_query = agent_state.get("standalone_query") or get_last_human_message(messages)

        logger.info(f"[fetch_data] Attempt 1 — query={standalone_query!r}, user_id={user_id!r}")
        _t0 = time.perf_counter()
        results = await fetch_relevant_chunks(standalone_query, top_k=5, auth_header=auth_header)
        logger.info(f"[fetch_data] Attempt 1 raw results: {len(results)}")

        # Retry with broader query (original user message) if first attempt yields nothing
        if not results:
            fallback_query = get_last_human_message(messages)
            logger.info(f"[fetch_data] Attempt 2 (retry) — broader query={fallback_query!r}, top_k=10")
            results = await fetch_relevant_chunks(fallback_query, top_k=10, auth_header=auth_header)
            logger.info(f"[fetch_data] Attempt 2 raw results: {len(results)}")
        retrieval_response_time_ms = round((time.perf_counter() - _t0) * 1000, 2)

        retrieved_texts = []
        seen_doc_ids: set = set()
        document_ids = []

        for res in results:
            meta = res.get("metadata", {})
            text = meta.get("text", "")
            doc_id = meta.get("document_id", "")
            if text:
                retrieved_texts.append(text)
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                document_ids.append(doc_id)

        if not retrieved_texts:
            logger.info("[fetch_data] No chunks retrieved after both attempts — will fallback to general_chat")
            return {"retrieved_texts": [], "document_ids": [], "source_documents": [], "retrieval_response_time_ms": retrieval_response_time_ms}

        logger.info(f"[fetch_data] Fetching S3 URLs for {len(document_ids)} unique document(s)")
        source_documents = await fetch_document_url_from_s3(document_ids, user_id=user_id)

        logger.info(f"[fetch_data] Done: {len(retrieved_texts)} chunks, {len(document_ids)} docs, {len(source_documents)} source URLs, retrieval={retrieval_response_time_ms}ms")
        return {
            "retrieved_texts": retrieved_texts,
            "document_ids": document_ids,
            "source_documents": source_documents,
            "retrieval_response_time_ms": retrieval_response_time_ms,
        }
    except Exception as e:
        logger.error(f"[fetch_data] Error: {e}")
        return {"retrieved_texts": [], "document_ids": [], "source_documents": [], "retrieval_response_time_ms": 0.0}
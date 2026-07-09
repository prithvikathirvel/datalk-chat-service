from app.langraph.schema import AgentState
from langchain_core.runnables import RunnableConfig
from app.service.rag_service import fetch_document_url_from_s3, fetch_relevant_chunks
from app.core.logging import logger
from app.langraph.utils.helper import get_last_human_message


async def fetch_data(agent_state: AgentState, config: RunnableConfig):
    logger.info("[fetch_data] Node entered")
    try:
        messages = agent_state["messages"]
        user_message = get_last_human_message(messages)
        user_id = config["configurable"]["user_id"]
        logger.info(f"[fetch_data] Fetching relevant chunks for user_id={user_id!r}, query={user_message!r}")

        results = await fetch_relevant_chunks(user_message)
        logger.info(f"[fetch_data] Raw results count: {len(results)}")

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

        logger.info(f"[fetch_data] Fetching S3 URLs for {len(document_ids)} unique document(s)")
        source_documents = await fetch_document_url_from_s3(document_ids, user_id=user_id)

        logger.info(f"[fetch_data] Done: {len(retrieved_texts)} chunks, {len(document_ids)} docs, {len(source_documents)} source URLs")
        return {
            "retrieved_texts": retrieved_texts,
            "document_ids": document_ids,
            "source_documents": source_documents,
        }
    except Exception as e:
        logger.error(f"[fetch_data] Error: {e}")
        return {"retrieved_texts": [], "document_ids": [], "source_documents": []}
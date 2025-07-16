import json
import os
import tempfile

from celery import Celery
from docling.models.base_model import DoclingDocument

from dify_kg_ext.docling import chunk_document, parse_document

# Get Redis connection details from environment
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", "0")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# Initialize Celery with Redis broker/backend
if REDIS_PASSWORD:
    broker_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    broker_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

app = Celery("worker", broker=broker_url, backend=broker_url)


@app.task
def parse_document_task(source, **kwargs):
    """
    Celery task for parsing documents

    Args:
        source: Document path/URL/binary stream
        **kwargs: Conversion options (max_num_pages, max_file_size, etc.)

    Returns:
        Parsed document object serialized as JSON
    """
    document = parse_document(source, **kwargs)
    # Convert document to JSON serializable format
    return json.dumps(document.export_to_dict())


@app.task
def chunk_document_task(document_json, **kwargs):
    """
    Celery task for chunking parsed documents

    Args:
        document_json: JSON serialized document object
        **kwargs: Chunking options (max_tokens, etc.)

    Returns:
        List of document chunks with metadata
    """

    # Create a temporary file to store the JSON document
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=True) as temp_file:
        temp_file.write(document_json)
        temp_file.flush()  # Ensure data is written to disk
        document = DoclingDocument.load_from_json(temp_file.name)

    chunks = chunk_document(document, **kwargs)
    return chunks


# Legacy task for backward compatibility
@app.task
def parse_document_task_legacy(source, **kwargs):
    """
    Legacy Celery task for parsing and chunking documents (deprecated)

    Args:
        source: Document path/URL/binary stream
        **kwargs: Conversion options (max_num_pages, tokenizer, etc.)

    Returns:
        List of document chunks with metadata
    """
    from dify_kg_ext.docling import parse_and_chunk

    return parse_and_chunk(source, **kwargs)

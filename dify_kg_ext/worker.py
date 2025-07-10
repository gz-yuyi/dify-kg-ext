import os
from celery import Celery
from dify_kg_ext.docling import parse_and_chunk

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
    Celery task for parsing and chunking documents

    Args:
        source: Document path/URL/binary stream
        **kwargs: Conversion options (max_num_pages, tokenizer, etc.)

    Returns:
        List of document chunks with metadata
    """
    return parse_and_chunk(source, **kwargs)

from celery import Celery
from dify_kg_ext.docling import parse_and_chunk

# Initialize Celery
app = Celery("worker", broker="pyamqp://guest@localhost//", backend="rpc://")


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
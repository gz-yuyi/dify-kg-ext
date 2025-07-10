import os
from celery import Celery
from dify_kg_ext.docling import parse_and_chunk

# Get RabbitMQ connection details from environment
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "")

# Initialize Celery with configurable broker
broker_url = f"pyamqp://{RABBITMQ_USER}:{RABBITMQ_PASS}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}"
app = Celery("worker", broker=broker_url, backend="rpc://")


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

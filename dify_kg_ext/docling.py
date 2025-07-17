# use docling to parse the document
import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer


def parse_document(source, **kwargs):
    """
    Parse a document from source without chunking.

    Args:
        source: Document path/URL/binary stream
        **kwargs: Additional conversion options (max_num_pages, max_file_size, etc.)

    Returns:
        Parsed document object with metadata
    """
    converter = DocumentConverter()
    result = converter.convert(source)
    return result.document


def chunk_document(document, **kwargs):
    """
    Chunk a parsed document into meaningful segments.

    Args:
        document: Parsed document object from parse_document
        **kwargs: Chunking options (max_tokens, etc.)

    Returns:
        List of document chunks with metadata
    """
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.encoding_for_model("gpt-4o"),
        max_tokens=kwargs.get(
            "max_tokens", 1024
        ),  # context window length required for OpenAI tokenizers
    )
    chunker = HybridChunker(tokenizer=tokenizer)
    chunks = [chunks.export_json_dict() for chunks in chunker.chunk(document)]
    return chunks


def parse_and_chunk(source, **kwargs):
    """
    Parse a document from source and chunk it into meaningful segments.
    (Legacy function for backward compatibility)

    Args:
        source: Document path/URL/binary stream
        **kwargs: Additional conversion options (max_num_pages, max_file_size, etc.)

    Returns:
        List of document chunks with metadata
    """
    document = parse_document(source, **kwargs)
    return chunk_document(document, **kwargs)

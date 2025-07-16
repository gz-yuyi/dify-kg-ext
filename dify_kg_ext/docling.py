# use docling to parse the document
import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

tokenizer = OpenAITokenizer(
    tokenizer=tiktoken.encoding_for_model("gpt-4o"),
    max_tokens=128 * 1024,  # context window length required for OpenAI tokenizers
)


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
    chunker = HybridChunker(
        tokenizer=tokenizer, max_tokens=kwargs.get("max_tokens", 1024)
    )
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
    # Convert document
    converter = DocumentConverter()
    result = converter.convert(source)
    document = result.document

    # Chunk document
    chunker = HybridChunker(tokenizer=tokenizer, max_tokens=1024)
    chunks = [chunks.export_json_dict() for chunks in chunker.chunk(document)]
    return chunks

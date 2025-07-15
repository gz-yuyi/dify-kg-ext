# use docling to parse the document
import tiktoken
from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer

tokenizer = OpenAITokenizer(
    tokenizer=tiktoken.encoding_for_model("gpt-4o"),
    max_tokens=128 * 1024,  # context window length required for OpenAI tokenizers
)


def parse_and_chunk(source, **kwargs):
    """
    Parse a document from source and chunk it into meaningful segments.

    Args:
        source: Document path/URL/binary stream
        tokenizer: Tokenizer model for chunking
        **kwargs: Additional conversion options (max_num_pages, max_file_size, etc.)

    Returns:
        List of document chunks with metadata
    """
    # Convert document
    converter = DocumentConverter()
    result = converter.convert(source)
    document = result.document

    # Chunk document
    chunker = HybridChunker(tokenizer=tokenizer)
    chunks = [chunks.export_json_dict() for chunks in chunker.chunk(document)]
    return chunks

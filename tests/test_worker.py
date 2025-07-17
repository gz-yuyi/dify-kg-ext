import pytest
import json
from unittest.mock import patch, MagicMock
from dify_kg_ext.worker import parse_document_task, chunk_document_task

@pytest.fixture
def mock_parse_document():
    with patch("dify_kg_ext.worker.parse_document") as mock_parse:
        yield mock_parse

@pytest.fixture  
def mock_chunk_document():
    with patch("dify_kg_ext.worker.chunk_document") as mock_chunk:
        yield mock_chunk

def test_parse_document_task_success(mock_parse_document):
    # Set up mock document object
    mock_doc = MagicMock()
    mock_doc.export_to_dict.return_value = {"title": "Test", "content": "Test content"}
    mock_parse_document.return_value = mock_doc
    
    # Call the task
    result = parse_document_task("test_source", max_num_pages=5)
    
    # Verify results - should be JSON string
    result_dict = json.loads(result)
    assert result_dict["title"] == "Test"
    assert result_dict["content"] == "Test content"
    mock_parse_document.assert_called_once_with("test_source", max_num_pages=5)

def test_parse_document_task_failure(mock_parse_document):
    # Set up exception
    mock_parse_document.side_effect = Exception("Test error")
    
    # Call the task and expect exception
    with pytest.raises(Exception) as excinfo:
        parse_document_task("test_source")
    
    # Verify error message
    assert "Test error" in str(excinfo.value)

def test_chunk_document_task_success(mock_chunk_document):
    # Set up mock chunks
    mock_chunks = [
        {"text": "First chunk", "metadata": {}},
        {"text": "Second chunk", "metadata": {}}
    ]
    mock_chunk_document.return_value = mock_chunks
    
    # Mock document JSON
    document_json = json.dumps({"title": "Test", "content": "Test content"})
    
    # Mock DoclingDocument.load_from_json to avoid validation issues
    with patch("dify_kg_ext.worker.DoclingDocument.load_from_json") as mock_load:
        mock_doc = MagicMock()
        mock_load.return_value = mock_doc
        
        # Call the task
        result = chunk_document_task(document_json, max_tokens=512)
        
        # Verify results
        assert result == mock_chunks
        mock_chunk_document.assert_called_once_with(mock_doc, max_tokens=512)
        mock_load.assert_called_once()

def test_chunk_document_task_failure(mock_chunk_document):
    # Set up exception
    mock_chunk_document.side_effect = Exception("Chunking failed")
    
    # Mock DoclingDocument.load_from_json to avoid validation issues
    with patch("dify_kg_ext.worker.DoclingDocument.load_from_json") as mock_load:
        mock_doc = MagicMock()
        mock_load.return_value = mock_doc
        
        # Call the task and expect exception
        with pytest.raises(Exception) as excinfo:
            chunk_document_task('{"title": "test"}')
        
        # Verify error message
        assert "Chunking failed" in str(excinfo.value)

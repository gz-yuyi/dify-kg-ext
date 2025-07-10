import pytest
from unittest.mock import patch, MagicMock
from dify_kg_ext.worker import parse_document_task

@pytest.fixture
def mock_parse_and_chunk():
    with patch("dify_kg_ext.worker.parse_and_chunk") as mock_parse:
        yield mock_parse

def test_parse_document_task_success(mock_parse_and_chunk):
    # Set up mock return value
    mock_parse_and_chunk.return_value = ["chunk1", "chunk2"]
    
    # Call the task
    result = parse_document_task("test_source", max_num_pages=5)
    
    # Verify results
    assert result == ["chunk1", "chunk2"]
    mock_parse_and_chunk.assert_called_once_with("test_source", max_num_pages=5)

def test_parse_document_task_failure(mock_parse_and_chunk):
    # Set up exception
    mock_parse_and_chunk.side_effect = Exception("Test error")
    
    # Call the task and expect exception
    with pytest.raises(Exception) as excinfo:
        parse_document_task("test_source")
    
    # Verify error message
    assert "Test error" in str(excinfo.value)

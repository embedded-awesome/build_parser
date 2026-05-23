"""Tests for file reader utilities."""

import pytest
import tempfile
from pathlib import Path
from build_converter.file_reader import FileReader


@pytest.fixture
def sample_file():
    """Create a sample file for testing."""
    content = "line 1\nline 2\nline 3"
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write(content)
        return f.name


def test_file_reader_read_file(sample_file):
    """Test reading entire file."""
    content = FileReader.read_file(sample_file)
    assert "line 1" in content
    assert "line 2" in content


def test_file_reader_read_lines(sample_file):
    """Test reading file as lines."""
    lines = FileReader.read_lines(sample_file)
    assert len(lines) >= 3


def test_file_reader_read_nonexistent():
    """Test reading nonexistent file raises error."""
    with pytest.raises(FileNotFoundError):
        FileReader.read_file("/nonexistent/path/file.txt")


def test_file_reader_find_files():
    """Test finding files by pattern."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        Path(tmpdir, "CMakeLists.txt").touch()
        Path(tmpdir, "test.txt").touch()
        Path(tmpdir, "other.py").touch()
        
        files = FileReader.find_files(tmpdir, "*.txt")
        names = [f.name for f in files]
        
        assert "CMakeLists.txt" in names
        assert "test.txt" in names
        assert "other.py" not in names

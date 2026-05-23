"""File reader utilities for reading CMake and KConfig files."""

from pathlib import Path
from typing import List


class FileReader:
    """Utility class for reading files with common operations."""

    @staticmethod
    def read_file(file_path: str) -> str:
        """Read entire file as string.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            File contents as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {file_path}") from e
        except IOError as e:
            raise IOError(f"Failed to read file: {file_path}") from e

    @staticmethod
    def read_lines(file_path: str) -> List[str]:
        """Read file as list of lines (with newlines preserved).
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            List of lines with newlines
        """
        content = FileReader.read_file(file_path)
        return content.splitlines(keepends=True)

    @staticmethod
    def find_files(directory: str, pattern: str = "*.txt") -> List[Path]:
        """Find files matching pattern in directory.
        
        Args:
            directory: Directory to search
            pattern: File pattern (e.g., "CMakeLists.txt", "Kconfig")
            
        Returns:
            List of matching file paths
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []
        return list(dir_path.rglob(pattern))

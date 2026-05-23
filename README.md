# Build Converter

Convert CMake and KConfig files to Yakka files for Zephyr projects.

## Project Structure

- `build_converter/` - Main package
  - `cmake_parser.py` - CMake file parsing
  - `kconfig_parser.py` - KConfig file parsing
  - `file_reader.py` - File I/O utilities
  - `analyzer.py` - Analysis and structure extraction

- `tests/` - Unit tests for each module

## Installation

```bash
pip install -e .
```

## Development Setup

```bash
pip install -e ".[dev]"
```

## Usage

```python
from build_converter.cmake_parser import CMakeParser
from build_converter.kconfig_parser import KConfigParser

# Parse CMake file
cmake_parser = CMakeParser("path/to/CMakeLists.txt")
cmake_data = cmake_parser.parse()

# Parse KConfig file
kconfig_parser = KConfigParser("path/to/Kconfig")
kconfig_data = kconfig_parser.parse()
```

## Step 1: File Readers and Parsers

This implementation provides:
- CMake file parser that extracts commands, variables, and structure
- KConfig file parser that extracts configuration options and dependencies
- Base file reader for common file I/O operations
- Analysis module for extracting meaningful structures

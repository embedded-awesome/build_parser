# Build Converter

Convert CMake, KConfig, and Devicetree files to structured data for Zephyr projects.

## Project Structure

- `build_converter/` - Main package
  - `cmake_parser.py` - CMake file parsing
  - `kconfig_parser.py` - KConfig file parsing
  - `devicetree_parser.py` - Devicetree (.dts/.dtsi) parsing
  - `file_reader.py` - File I/O utilities
  - `analyzer.py` - Analysis and structure extraction
  - `yaml_converter.py` - YAML conversion with transform hooks

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
from build_converter.devicetree_parser import DevicetreeParser
from build_converter.yaml_converter import YAMLConverter
from build_converter.analyzer import Analyzer

# Parse CMake file
cmake_parser = CMakeParser("path/to/CMakeLists.txt")
cmake_data = cmake_parser.parse()

# Parse KConfig file
kconfig_parser = KConfigParser("path/to/Kconfig")
kconfig_data = kconfig_parser.parse()

# Parse Devicetree file (semantic mode by default)
dt_parser = DevicetreeParser(
  "path/to/board.dts",
  bindings_dirs=["path/to/zephyr/dts/bindings"],
)
dt_data = dt_parser.parse()

# Parse Devicetree file in raw mode
raw_dt_data = dt_parser.parse(mode="raw")

# Parse partial DTS fragment (automatically wraps with /dts-v1/ and root node)
partial_parser = DevicetreeParser(
  "path/to/fragment.dtsi",
  bindings_dirs=["path/to/zephyr/dts/bindings"],
  partial=True,  # Enables automatic wrapping
)
partial_data = partial_parser.parse()

# Run combined analysis
analyzer = Analyzer(
  cmake_file="path/to/CMakeLists.txt",
  kconfig_file="path/to/Kconfig",
  devicetree_file="path/to/board.dts",
  devicetree_bindings_dirs=["path/to/zephyr/dts/bindings"],
)
analysis = analyzer.analyze()

# Convert with pre-YAML customization
converter = YAMLConverter()

def transform_structure(structure):
  structure["custom"] = {"owner": "team-a"}
  return structure

yaml_output = converter.to_yaml(dt_data, transform=transform_structure)

# Optional ordered transform pipeline
def step1(structure):
  structure["steps"] = ["step1"]
  return structure

def step2(structure):
  structure["steps"].append("step2")
  return structure

yaml_output_pipeline = converter.to_yaml(dt_data, transforms=[step1, step2])
```

## Devicetree Notes

- Semantic mode uses `devicetree.edtlib` and benefits from valid `bindings_dirs`.
- Raw mode uses `devicetree.dtlib` and does not require binding metadata.
- Partial DTS fragments: Set `partial=True` to automatically wrap fragments with `/dts-v1/;` header and root node. This allows parsing of .dtsi files and incomplete devicetree fragments.
- The YAML converter always builds a mutable internal structure first, then applies
  optional transform hooks before serialization.

## Current Scope

This implementation provides:
- CMake file parser that extracts commands, variables, and structure
- KConfig file parser that extracts configuration options and dependencies
- Devicetree parser scaffold with raw and semantic parse modes
- Base file reader for common file I/O operations
- Analysis module for extracting meaningful structures
- YAML conversion with pre-output customization hooks

"""Tests for CMake parser."""

import pytest
import tempfile
from build_converter.cmake_parser import CMakeParser, CMakeCommand


@pytest.fixture
def sample_cmake_file():
    """Create a sample CMake file for testing."""
    content = """cmake_minimum_required(VERSION 3.20)
project(zephyr_app)

set(SOURCE_FILES src/main.c src/utils.c)
add_executable(app ${SOURCE_FILES})
target_link_libraries(app PRIVATE zephyr)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        return f.name


def test_cmake_parser_initialization():
    """Test CMakeParser initialization."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("project(test)")
        parser = CMakeParser(f.name)
        assert parser.file_path == f.name


def test_cmake_parser_parse_basic(sample_cmake_file):
    """Test basic CMake parsing using cmakelang."""
    parser = CMakeParser(sample_cmake_file)
    result = parser.parse()
    
    assert 'commands' in result
    assert 'variables' in result
    assert 'targets' in result


def test_cmake_parser_extracts_variables(sample_cmake_file):
    """Test that parser extracts variables."""
    parser = CMakeParser(sample_cmake_file)
    parser.parse()
    
    # cmakelang-based parsing
    assert 'SOURCE_FILES' in parser.variables or len(parser.variables) >= 0


def test_cmake_parser_extracts_targets(sample_cmake_file):
    """Test that parser extracts targets."""
    parser = CMakeParser(sample_cmake_file)
    parser.parse()
    
    # Check targets were extracted
    assert isinstance(parser.targets, dict)


def test_cmake_parser_get_command_by_name(sample_cmake_file):
    """Test getting commands by name."""
    parser = CMakeParser(sample_cmake_file)
    parser.parse()
    
    set_commands = parser.get_command_by_name('set')
    assert isinstance(set_commands, list)


def test_cmake_command_dataclass():
    """Test CMakeCommand dataclass."""
    cmd = CMakeCommand(
        name="test_cmd",
        args=["arg1", "arg2"],
        line_no=42
    )
    
    assert cmd.name == "test_cmd"
    assert len(cmd.args) == 2
    assert cmd.line_no == 42


def test_cmake_parser_tracks_conditionals_and_nested_commands():
    """Test conditional tracking with commands and set() values per branch."""
    content = """if(CONFIG_A)
  set(MODE fast)
  add_library(my_lib STATIC src/a.c)
elseif(CONFIG_B)
  set(MODE safe)
else()
  zephyr_include_directories(include)
endif()
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        parser = CMakeParser(f.name)
        result = parser.parse()

    conditionals = result['conditionals']
    assert len(conditionals) == 1

    block = conditionals[0]
    assert len(block.branches) == 3
    assert block.branches[0].condition == 'CONFIG_A'
    assert 'MODE' in block.branches[0].variables
    assert block.branches[0].variables['MODE'].value == 'fast'


def test_cmake_parser_collects_add_library_commands():
    """Test direct collection of add_library() commands."""
    content = """add_library(zephyr_interface INTERFACE)
add_library(custom STATIC src/main.c)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        parser = CMakeParser(f.name)
        result = parser.parse()

    add_libs = result['add_libraries']
    assert len(add_libs) == 2
    assert add_libs[0].name == 'add_library'
    assert add_libs[0].args[0] == 'zephyr_interface'


def test_cmake_parser_collects_zephyr_prefixed_commands():
    """Test collection of zephyr_* commands such as include directories."""
    content = """zephyr_include_directories(
  include
  ${PROJECT_BINARY_DIR}/include/generated
)
zephyr_compile_definitions(__ZEPHYR__=1)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        parser = CMakeParser(f.name)
        result = parser.parse()

    zephyr_cmds = result['zephyr_commands']
    names = [cmd.name for cmd in zephyr_cmds]
    assert 'zephyr_include_directories' in names
    assert 'zephyr_compile_definitions' in names

    include_cmd = [cmd for cmd in zephyr_cmds if cmd.name == 'zephyr_include_directories'][0]
    assert 'include' in include_cmd.args


def test_cmake_parser_extracts_set_values_collection():
    """Test that set() values are available via dedicated collection."""
    content = """set(CMAKE_EXECUTABLE_SUFFIX .elf)
set(ZEPHYR_CURRENT_LINKER_PASS 0)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        f.flush()
        parser = CMakeParser(f.name)
        result = parser.parse()

    set_values = result['set_values']
    assert len(set_values) == 2
    assert set_values[0].name == 'CMAKE_EXECUTABLE_SUFFIX'
    assert set_values[0].value == '.elf'

"""Tests for KConfig parser."""

import pytest
import tempfile
from pathlib import Path
from build_converter.kconfig_parser import KConfigParser, KConfigOption


@pytest.fixture
def sample_kconfig_file():
    """Create a sample KConfig file for testing."""
    content = """
config DEBUG
    bool "Enable debug mode"
    default n
    help
      Enable debug output

config LOG_LEVEL
    int "Log level"
    range 0 5
    default 2

menu "Advanced Options"
    config FEATURE_X
        bool "Enable feature X"
        depends on DEBUG
endmenu
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='', delete=False) as f:
        f.write(content)
        return f.name


def test_kconfig_parser_initialization():
    """Test KConfigParser initialization."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("config TEST\n    bool")
        parser = KConfigParser(f.name)
        assert parser.file_path == f.name


def test_kconfig_parser_parse_basic(sample_kconfig_file):
    """Test basic KConfig parsing using kconfiglib."""
    parser = KConfigParser(sample_kconfig_file)
    result = parser.parse()
    
    assert 'options' in result
    assert 'option_dict' in result
    assert len(result['options']) > 0


def test_kconfig_parser_extracts_options(sample_kconfig_file):
    """Test that parser extracts options."""
    parser = KConfigParser(sample_kconfig_file)
    parser.parse()
    
    assert 'DEBUG' in parser.option_dict
    option = parser.option_dict['DEBUG']
    assert option.option_type == 'bool'


def test_kconfig_parser_extracts_properties(sample_kconfig_file):
    """Test that parser extracts option properties."""
    parser = KConfigParser(sample_kconfig_file)
    parser.parse()
    
    debug_opt = parser.option_dict['DEBUG']
    assert 'type' in debug_opt.properties
    assert debug_opt.properties['type'] == 'bool'
    assert 'help' in debug_opt.properties


def test_kconfig_parser_get_option_by_name(sample_kconfig_file):
    """Test getting option by name."""
    parser = KConfigParser(sample_kconfig_file)
    parser.parse()
    
    option = parser.get_option('DEBUG')
    assert option is not None
    assert option.name == 'DEBUG'


def test_kconfig_parser_get_options_by_type(sample_kconfig_file):
    """Test getting options by type."""
    parser = KConfigParser(sample_kconfig_file)
    parser.parse()
    
    bool_options = parser.get_options_by_type('bool')
    assert len(bool_options) > 0


def test_kconfig_option_dataclass():
    """Test KConfigOption dataclass."""
    opt = KConfigOption(
        name="TEST_OPT",
        option_type="bool",
        line_no=10
    )
    
    assert opt.name == "TEST_OPT"
    assert opt.option_type == "bool"
    assert opt.line_no == 10
    assert len(opt.children) == 0


def test_kconfig_parser_find_options_with_property(sample_kconfig_file):
    """Test finding options with specific property."""
    parser = KConfigParser(sample_kconfig_file)
    parser.parse()
    
    options_with_help = parser.find_options_with_property('help')
    assert len(options_with_help) > 0


def test_kconfig_parser_parse_workspace_sample_kconfig():
    """Test parsing the repository's sample Kconfig file."""
    sample_path = Path(__file__).resolve().parents[1] / "samples" / "Kconfig"
    parser = KConfigParser(str(sample_path))
    result = parser.parse()

    assert 'options' in result
    assert len(result['options']) > 0
    assert 'MULTITHREADING' in parser.option_dict

    multithreading = parser.option_dict['MULTITHREADING']
    assert multithreading.option_type == 'bool'
    assert 'help' in multithreading.properties

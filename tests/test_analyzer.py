"""Tests for analyzer module."""

import pytest
import tempfile
from build_converter.analyzer import Analyzer


@pytest.fixture
def sample_cmake_file():
    """Create a sample CMake file."""
    content = """
cmake_minimum_required(VERSION 3.20)
project(test_app)

set(SOURCES src/main.c src/utils.c)
set(HEADERS include/app.h)

add_executable(app ${SOURCES})
add_library(utils ${SOURCES})

target_link_libraries(app PRIVATE utils)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        return f.name


@pytest.fixture
def sample_kconfig_file():
    """Create a sample KConfig file."""
    content = """
config APP_DEBUG
    bool "Enable debugging"
    default n

config LOG_LEVEL
    int "Log level (0-5)"
    range 0 5
    default 2
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='', delete=False) as f:
        f.write(content)
        return f.name


def test_analyzer_initialization():
    """Test Analyzer initialization."""
    analyzer = Analyzer()
    assert analyzer.cmake_parser is None
    assert analyzer.kconfig_parser is None


def test_analyzer_with_cmake_file(sample_cmake_file):
    """Test Analyzer with CMake file."""
    analyzer = Analyzer(cmake_file=sample_cmake_file)
    assert analyzer.cmake_parser is not None


def test_analyzer_analyze_cmake(sample_cmake_file):
    """Test CMake analysis."""
    analyzer = Analyzer(cmake_file=sample_cmake_file)
    results = analyzer.analyze()
    
    cmake_results = results['cmake']
    assert 'total_commands' in cmake_results
    assert 'total_variables' in cmake_results
    assert 'total_targets' in cmake_results


def test_analyzer_analyze_kconfig(sample_kconfig_file):
    """Test KConfig analysis."""
    analyzer = Analyzer(kconfig_file=sample_kconfig_file)
    results = analyzer.analyze()
    
    kconfig_results = results['kconfig']
    assert 'total_options' in kconfig_results
    assert 'options_by_type' in kconfig_results


def test_analyzer_get_cmake_summary(sample_cmake_file):
    """Test getting CMake summary."""
    analyzer = Analyzer(cmake_file=sample_cmake_file)
    analyzer.analyze()
    summary = analyzer.get_cmake_summary()
    
    assert "CMake Analysis Summary" in summary
    assert "commands" in summary.lower()


def test_analyzer_get_kconfig_summary(sample_kconfig_file):
    """Test getting KConfig summary."""
    analyzer = Analyzer(kconfig_file=sample_kconfig_file)
    analyzer.analyze()
    summary = analyzer.get_kconfig_summary()
    
    assert "KConfig Analysis Summary" in summary
    assert "options" in summary.lower()


def test_analyzer_get_devicetree_summary_empty():
    """Devicetree summary should be empty message when no parse data exists."""
    analyzer = Analyzer()
    summary = analyzer.get_devicetree_summary()

    assert summary == "No Devicetree data available"


def test_analyzer_devicetree_summary_and_correlations_with_stub_parser(sample_kconfig_file):
    """Analyzer should summarize Devicetree data and compute compat correlations."""
    analyzer = Analyzer(kconfig_file=sample_kconfig_file)

    class StubDevicetreeParser:
        def parse(self, mode=None):
            return {
                "mode": "semantic",
                "nodes": [
                    {
                        "path": "/",
                        "properties": {},
                    }
                ],
                "labels": ["uart0"],
                "compat_index": {
                    "app,debug": ["/test-node"],
                },
                "chosen_nodes": {
                    "zephyr,console": "/test-node",
                },
            }

    analyzer.devicetree_parser = StubDevicetreeParser()
    analyzer.devicetree_mode = "semantic"

    results = analyzer.analyze()
    dt_summary = analyzer.get_devicetree_summary()

    assert "devicetree" in results
    assert results["devicetree"]["mode"] == "semantic"
    assert "kconfig_compatible_matches" in results["correlations"]
    assert "APP_DEBUG" in results["correlations"]["kconfig_compatible_matches"]
    assert "Devicetree Analysis Summary" in dt_summary
    assert "Chosen nodes" in dt_summary

#!/usr/bin/env python3
"""Test script demonstrating partial DTS file parsing with partial=True."""

import tempfile
from pathlib import Path
from build_converter.devicetree_parser import DevicetreeParser


def test_partial_dts_raw():
    """Parse a partial DTS fragment in raw mode."""
    # Create a partial fragment (no /dts-v1/ header or root node wrapper)
    fragment = """
my-device@1000 {
    compatible = "vendor,my-device";
    status = "okay";
    reg = <0x1000 0x100>;
};

another-device {
    compatible = "vendor,another";
    interrupts = <42>;
};
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsi", delete=False) as f:
        f.write(fragment)
        f.flush()
        temp_path = f.name

    try:
        # Parse with partial=True (auto-wraps with /dts-v1/ and root node)
        parser = DevicetreeParser(temp_path, partial=True, default_mode="raw")
        result = parser.parse()

        print("✓ Successfully parsed partial DTS fragment in raw mode")
        print(f"  - Found {len(result['nodes'])} nodes")
        print(f"  - Nodes: {[n['path'] for n in result['nodes']]}")
        
        # Verify the nodes are present
        node_paths = [n["path"] for n in result["nodes"]]
        assert "/" in node_paths, "Root node should exist"
        assert "/my-device@1000" in node_paths, "my-device should be parsed"
        assert "/another-device" in node_paths, "another-device should be parsed"
        
        return True
    finally:
        Path(temp_path).unlink()


def test_partial_dts_semantic():
    """Parse a partial DTS fragment in semantic mode."""
    fragment = """
test-device@2000 {
    compatible = "vendor,test";
    status = "okay";
    test-property = "value";
};
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".dtsi", delete=False) as f:
        f.write(fragment)
        f.flush()
        temp_path = f.name

    try:
        # Parse with partial=True in semantic mode
        parser = DevicetreeParser(
            temp_path,
            partial=True,
            bindings_dirs=[],
            default_mode="semantic",
        )
        result = parser.parse()

        print("✓ Successfully parsed partial DTS fragment in semantic mode")
        print(f"  - Found {len(result['nodes'])} nodes")
        print(f"  - Nodes: {[n['path'] for n in result['nodes']]}")
        
        # Verify the nodes are present
        node_paths = [n["path"] for n in result["nodes"]]
        assert "/" in node_paths, "Root node should exist"
        assert "/test-device@2000" in node_paths, "test-device should be parsed"
        
        return True
    finally:
        Path(temp_path).unlink()


if __name__ == "__main__":
    print("Testing partial DTS file parsing...\n")
    
    try:
        test_partial_dts_raw()
        print()
        test_partial_dts_semantic()
        print("\n✓ All partial DTS parsing tests passed!")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

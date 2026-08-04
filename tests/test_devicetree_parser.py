"""Tests for Devicetree parser raw and semantic modes."""

from pathlib import Path

import pytest

from build_converter.devicetree_parser import DevicetreeParser


pytest.importorskip("build_converter.devicetree.dtlib")
pytest.importorskip("build_converter.devicetree.edtlib")


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_devicetree_parser_raw_basic(tmp_path: Path):
    """Parse a simple DTS file in raw mode."""
    dts = tmp_path / "basic.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    model = "unit-test";
    test_node: test-node@0 {
        reg = <0x0 0x10>;
        status = "okay";
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), default_mode="raw")
    result = parser.parse()

    assert result["mode"] == "raw"
    assert "/" in result["node_dict"]
    assert "/test-node@0" in result["node_dict"]
    assert "test_node" in result["labels"]


def test_devicetree_parser_raw_include_path(tmp_path: Path):
    """Parse DTS that includes a DTSI without inlining it."""
    inc_dir = tmp_path / "inc"
    inc_dir.mkdir()

    include_file = inc_dir / "fragment.dtsi"
    _write(
        include_file,
        """/ {
    included: included-node {
        status = "okay";
    };
};
""",
    )

    dts = tmp_path / "with_include.dts"
    _write(
        dts,
        """/dts-v1/;
/include/ "fragment.dtsi"

/ {
    model = "include-test";
};
""",
    )

    parser = DevicetreeParser(str(dts), include_path=[str(inc_dir)], default_mode="raw")
    result = parser.parse_raw()

    assert result["mode"] == "raw"
    assert "/included-node" not in result["node_dict"]
    assert result["directives"]
    assert result["directives"][0]["target"] == "fragment.dtsi"
    assert result["source"]["text"] == dts.read_text(encoding="utf-8")
    assert "/" in result["node_dict"]
    assert "/model" not in result["node_dict"]


def test_devicetree_parser_semantic_basic_no_bindings(tmp_path: Path):
    """Parse a simple DTS file in semantic mode without binding metadata."""
    dts = tmp_path / "semantic.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    model = "semantic-test";
    chosen {
        zephyr,console = &uart0;
    };

    uart0: serial@40002000 {
        status = "okay";
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), bindings_dirs=[], default_mode="semantic")
    result = parser.parse()

    assert result["mode"] == "semantic"
    assert "/" in result["node_dict"]
    assert "/serial@40002000" in result["node_dict"]
    assert result["chosen_nodes"]["zephyr,console"] == "&uart0"


def test_devicetree_parser_semantic_prefers_label_reference_syntax(tmp_path: Path):
    """Semantic references should preserve &label syntax where possible."""
    dts = tmp_path / "references.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    chosen {
        zephyr,flash-controller = &msc;
    };

    soc {
        msc: flash-controller@50030000 {
            compatible = "vendor,flash";
            reg = <0x50030000 0x1000>;
        };

        client@0 {
            compatible = "vendor,client";
            flash = <&msc>;
        };
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), bindings_dirs=[], default_mode="semantic")
    result = parser.parse_semantic()

    assert result["chosen_nodes"]["zephyr,flash-controller"] == "&msc"


def test_devicetree_parser_unknown_mode_error(tmp_path: Path):
    """Unknown parse mode should raise ValueError."""
    dts = tmp_path / "basic.dts"
    _write(dts, "/dts-v1/;\n/ { };\n")

    parser = DevicetreeParser(str(dts))
    with pytest.raises(ValueError):
        parser.parse(mode="invalid-mode")


def test_devicetree_parser_missing_file_raw_error(tmp_path: Path):
    """Missing file in raw parse should raise wrapped ValueError."""
    missing = tmp_path / "missing.dts"
    parser = DevicetreeParser(str(missing), default_mode="raw")

    with pytest.raises(ValueError):
        parser.parse_raw()


def test_devicetree_parser_missing_file_semantic_error(tmp_path: Path):
    """Missing file in semantic parse should raise wrapped ValueError."""
    missing = tmp_path / "missing.dts"
    parser = DevicetreeParser(str(missing), bindings_dirs=[])

    with pytest.raises(ValueError):
        parser.parse_semantic()


def test_devicetree_parser_raw_symbolic_cell_value(tmp_path: Path):
    """Raw mode should preserve symbolic cell constants as strings."""
    dts = tmp_path / "symbolic_cell.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    i2c@4000c000 {
        clock-frequency = <I2C_BITRATE_STANDARD>;
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), default_mode="raw")
    result = parser.parse_raw()

    prop = result["node_dict"]["/i2c@4000c000"]["properties"]["clock-frequency"]
    assert prop["type"] == "num"
    assert prop["value"] == ["I2C_BITRATE_STANDARD"]


def test_devicetree_parser_raw_mixed_symbolic_and_numeric_cells(tmp_path: Path):
    """Raw mode should preserve source order for mixed symbolic/numeric cells."""
    dts = tmp_path / "mixed_cells.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    test@0 {
        values = <1 I2C_BITRATE_STANDARD 3>;
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), default_mode="raw")
    result = parser.parse_raw()

    prop = result["node_dict"]["/test@0"]["properties"]["values"]
    assert prop["type"] == "nums"
    assert prop["value"] == [1, "I2C_BITRATE_STANDARD", 3]


def test_devicetree_parser_raw_symbolic_expression_cell(tmp_path: Path):
    """Raw mode should preserve symbolic expressions without evaluating them."""
    dts = tmp_path / "symbolic_expr_cell.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
    i2c@4000c000 {
        clock-frequency = <(I2C_BITRATE_STANDARD + 1)>;
    };
};
""",
    )

    parser = DevicetreeParser(str(dts), default_mode="raw")
    result = parser.parse_raw()

    prop = result["node_dict"]["/i2c@4000c000"]["properties"]["clock-frequency"]
    assert prop["type"] == "num"
    assert prop["value"] == ["((I2C_BITRATE_STANDARD + 1))"]


def test_devicetree_parser_raw_unresolved_ref_fragment(tmp_path: Path):
    """Raw mode should preserve unresolved top-level label overlays separately."""
    dts = tmp_path / "unresolved_ref.dts"
    _write(
        dts,
        """/dts-v1/;

/ {
};

&nvic {
    arm,num-irq-priority-bits = <3>;
};
""",
    )

    parser = DevicetreeParser(str(dts), default_mode="raw")
    result = parser.parse_raw()

    assert result["unresolved_refs"]
    unresolved = result["unresolved_refs"][0]
    assert unresolved["reference"] == "nvic"
    assert unresolved["reference_syntax"] == "&nvic"
    assert unresolved["reference_kind"] == "label"
    prop = unresolved["fragment"]["properties"]["arm,num-irq-priority-bits"]
    assert prop["type"] == "num"
    assert prop["value"] == 3


def test_devicetree_parser_semantic_tolerates_missing_parent_cells(tmp_path: Path):
    """Semantic mode should tolerate reg mismatch when parent cells are missing."""
    dtsi = tmp_path / "missing_cells.dtsi"
    _write(
        dtsi,
        """/dts-v1/;

/ {
    soc {
        flash@400e0000 {
            reg = <0x400e0000 0x104>;
        };
    };
};
""",
    )

    parser = DevicetreeParser(
        str(dtsi),
        bindings_dirs=[],
        default_mode="semantic",
        partial=True,
    )
    result = parser.parse_semantic()

    assert result["mode"] == "semantic"
    assert result.get("semantic_fallback") == "missing-cells-tolerant"
    assert "/soc/flash@400e0000" in result["node_dict"]


def test_devicetree_parser_semantic_keeps_conflicting_cells_error(tmp_path: Path):
    """Semantic mode should still fail when explicit parent cells conflict."""
    dtsi = tmp_path / "conflicting_cells.dtsi"
    _write(
        dtsi,
        """/dts-v1/;

/ {
    soc {
        #address-cells = <2>;
        #size-cells = <1>;

        flash@400e0000 {
            reg = <0x400e0000 0x104>;
        };
    };
};
""",
    )

    parser = DevicetreeParser(
        str(dtsi),
        bindings_dirs=[],
        default_mode="semantic",
        partial=True,
    )
    with pytest.raises(ValueError):
        parser.parse_semantic()


def test_devicetree_parser_semantic_exposes_include_directives(tmp_path: Path):
    """Semantic mode should expose include directives in parser metadata."""
    _write(
        tmp_path / "base.dtsi",
        """/ {
    base-node {
        status = "okay";
    };
};
""",
    )

    dtsi = tmp_path / "with_include.dtsi"
    _write(
        dtsi,
        """/include/ "base.dtsi"

/ {
    node@0 {
        status = "okay";
    };
};
""",
    )

    parser = DevicetreeParser(
        str(dtsi),
        bindings_dirs=[],
        default_mode="semantic",
        partial=True,
    )
    result = parser.parse_semantic()

    assert result["directives"]
    assert result["directives"][0]["target"] == "base.dtsi"


def test_devicetree_parser_semantic_captures_unresolved_refs(tmp_path: Path):
    """Semantic mode should preserve unresolved top-level &label fragments."""
    dtsi = tmp_path / "unresolved_ref.dtsi"
    _write(
        dtsi,
        """/ {
};

&flash0 {
    reg = <0x08000000 0x1000>;
};
""",
    )

    parser = DevicetreeParser(
        str(dtsi),
        bindings_dirs=[],
        default_mode="semantic",
        partial=True,
    )
    result = parser.parse_semantic()

    assert result["unresolved_refs"]
    unresolved = result["unresolved_refs"][0]
    assert unresolved["reference"] == "flash0"
    assert unresolved["reference_syntax"] == "&flash0"
    assert unresolved["fragment"]["properties"]["reg"]["value"] == [0x08000000, 0x1000]

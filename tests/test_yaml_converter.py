"""Tests for YAML conversion with pre-output customization hooks."""

import pytest

from build_converter.yaml_converter import YAMLConversionError, YAMLConverter


def test_yaml_converter_build_structure_metadata():
    """Ensure build_structure includes metadata envelope."""
    converter = YAMLConverter()
    result = converter.build_structure({"key": "value"}, format="semantic")

    assert result["schema_version"] == "v1"
    assert result["format"] == "semantic"
    assert "data" in result


def test_yaml_converter_to_yaml_no_transform():
    """Ensure conversion works unchanged without transform hooks."""
    converter = YAMLConverter()
    output = converter.to_yaml({"b": 2, "a": 1})

    assert "schema_version: v1" in output
    assert "format: semantic" in output
    assert "data:" in output


def test_yaml_converter_transform_callback_renames_key():
    """Allow user callback to customize structure before serialization."""
    converter = YAMLConverter()

    def transform(structure):
        data = structure.pop("data")
        structure["payload"] = data
        return structure

    output = converter.to_yaml({"x": 1}, transform=transform)

    assert "payload:" in output
    assert "data:" not in output


def test_yaml_converter_transform_pipeline_order():
    """Ensure multiple transforms run in deterministic order."""
    converter = YAMLConverter()

    def step1(structure):
        structure["order"] = ["step1"]
        return structure

    def step2(structure):
        structure["order"].append("step2")
        return structure

    transformed = converter.transform_structure(
        converter.build_structure({}),
        transforms=[step1, step2],
    )

    assert transformed["order"] == ["step1", "step2"]


def test_yaml_converter_invalid_transform_type_rejected():
    """Reject invalid root values returned by transforms."""
    converter = YAMLConverter()

    def bad_transform(_structure):
        return "not-a-dict"

    with pytest.raises(YAMLConversionError):
        converter.to_yaml({"x": 1}, transform=bad_transform)


def test_yaml_converter_subclass_customize_structure_hook():
    """Allow subclass override for default customization behavior."""

    class CustomConverter(YAMLConverter):
        def customize_structure(self, structure):
            structure["customized"] = True
            return structure

    converter = CustomConverter()
    output = converter.to_yaml({"x": 1})

    assert "customized: true" in output


def test_yaml_converter_devicetree_semantic_shape_stable():
    """Normalize semantic Devicetree data into stable schema shape."""
    converter = YAMLConverter()
    semantic_data = {
        "file_path": "board.dts",
        "workspace_dir": "/workspace",
        "bindings_dirs": ["z/b", "a/b"],
        "include_path": ["z/inc", "a/inc"],
        "directives": [
            {
                "line_no": 2,
                "text": '/include/ "base.dtsi"',
                "target": "base.dtsi",
            }
        ],
        "unresolved_refs": [
            {
                "reference": "flash0",
                "reference_syntax": "&flash0",
                "reference_kind": "label",
                "label": None,
                "fragment": {
                    "name": "unresolved-ref-0",
                    "filename": "board.dts",
                    "line_no": 42,
                    "labels": [],
                    "properties": {
                        "reg": {
                            "type": "nums",
                            "value": [134217728, "DT_SIZE_K(1536)"],
                            "labels": [],
                        }
                    },
                    "children": [],
                },
            }
        ],
        "labels": ["label2", "label1"],
        "chosen_nodes": {
            "zephyr,flash": "/flash",
            "zephyr,console": "/uart",
        },
        "compat_index": {
            "vendor,b": ["/b", "/a"],
            "vendor,a": ["/x"],
        },
        "nodes": [
            {
                "path": "/b",
                "name": "b",
                "status": "okay",
                "labels": ["b1"],
                "aliases": ["alias-b"],
                "compats": ["vendor,b"],
                "matching_compat": "vendor,b",
                "binding_path": None,
                "parent_path": "/",
                "children": ["/b/c"],
                "depends_on": ["/a"],
                "required_by": [],
                "properties": {
                    "status": {"type": "string", "value": "okay", "description": None},
                    "reg": {"type": "array", "value": [0, 1], "description": None},
                },
            },
            {
                "path": "/a",
                "name": "a",
                "status": "disabled",
                "labels": [],
                "aliases": [],
                "compats": ["vendor,a"],
                "matching_compat": "vendor,a",
                "binding_path": None,
                "parent_path": "/",
                "children": [],
                "depends_on": [],
                "required_by": ["/b"],
                "properties": {},
            },
        ],
    }

    shaped = converter.build_structure(semantic_data, format="devicetree-semantic")

    assert shaped["data"]["source"]["bindings_dirs"] == ["a/b", "z/b"]
    assert shaped["data"]["source"]["include_path"] == ["a/inc", "z/inc"]
    assert shaped["data"]["source"]["directives"][0]["target"] == "base.dtsi"
    assert shaped["data"]["unresolved_refs"][0]["reference_syntax"] == "&flash0"
    assert shaped["data"]["summary"]["total_nodes"] == 2
    assert list(shaped["data"]["compat_index"].keys()) == ["vendor,a", "vendor,b"]
    assert shaped["data"]["nodes"][0]["path"] == "/a"
    assert [p["name"] for p in shaped["data"]["nodes"][1]["properties"]] == ["reg", "status"]


def test_yaml_converter_devicetree_semantic_requires_dict_input():
    """Semantic Devicetree shaping should reject non-dict input."""
    converter = YAMLConverter()

    with pytest.raises(YAMLConversionError):
        converter.build_structure(["not", "a", "dict"], format="devicetree-semantic")

"""YAML conversion utilities with pre-output structure customization hooks."""

from typing import Any, Callable, Dict, List, Optional, Sequence

import yaml


TransformFn = Callable[[Any], Any]


class YAMLConversionError(ValueError):
    """Raised when YAML conversion or structure transformation fails."""


class YAMLConverter:
    """Convert parsed structures to deterministic YAML.

    The conversion flow is intentionally split into two stages:
    1. build_structure() creates a mutable intermediate structure.
    2. transform_structure() allows callers to customize it before dumping.
    """

    def build_structure(self, data: Any, format: str = "semantic") -> Dict[str, Any]:
        """Build a mutable intermediate structure before YAML serialization.

        Args:
            data: Parsed input data to serialize.
            format: Logical format label to include in metadata.

        Returns:
            A dictionary ready for optional transformation.
        """
        if format == "devicetree-semantic":
            payload = self._shape_devicetree_semantic_data(data)
        else:
            payload = data

        return {
            "schema_version": "v1",
            "generator": "build_converter.yaml_converter",
            "format": format,
            "data": payload,
        }

    def _shape_devicetree_semantic_data(self, data: Any) -> Dict[str, Any]:
        """Normalize semantic Devicetree data into a stable schema shape."""
        if not isinstance(data, dict):
            raise YAMLConversionError(
                "devicetree-semantic format expects dict input"
            )

        nodes = data.get("nodes", [])
        if not isinstance(nodes, list):
            raise YAMLConversionError("devicetree-semantic data.nodes must be a list")

        shaped_nodes: List[Dict[str, Any]] = []
        for node in sorted(nodes, key=lambda item: item.get("path", "")):
            properties = node.get("properties", {})
            if not isinstance(properties, dict):
                properties = {}

            shaped_props = [
                {
                    "name": prop_name,
                    "type": prop_val.get("type") if isinstance(prop_val, dict) else None,
                    "value": prop_val.get("value") if isinstance(prop_val, dict) else prop_val,
                    "description": prop_val.get("description") if isinstance(prop_val, dict) else None,
                }
                for prop_name, prop_val in sorted(properties.items(), key=lambda item: item[0])
            ]

            shaped_nodes.append(
                {
                    "path": node.get("path"),
                    "name": node.get("name"),
                    "status": node.get("status"),
                    "labels": sorted(node.get("labels", [])),
                    "aliases": sorted(node.get("aliases", [])),
                    "compats": sorted(node.get("compats", [])),
                    "matching_compat": node.get("matching_compat"),
                    "binding_path": node.get("binding_path"),
                    "parent_path": node.get("parent_path"),
                    "children": sorted(node.get("children", [])),
                    "depends_on": sorted(node.get("depends_on", [])),
                    "required_by": sorted(node.get("required_by", [])),
                    "properties": shaped_props,
                }
            )

        compat_index = data.get("compat_index", {})
        if not isinstance(compat_index, dict):
            compat_index = {}

        chosen_nodes = data.get("chosen_nodes", {})
        if not isinstance(chosen_nodes, dict):
            chosen_nodes = {}

        unresolved_refs = data.get("unresolved_refs", [])
        if not isinstance(unresolved_refs, list):
            unresolved_refs = []

        directives = data.get("directives", [])
        if not isinstance(directives, list):
            directives = []
        shaped_directives = []
        for directive in directives:
            if not isinstance(directive, dict):
                continue
            shaped_directives.append(
                {
                    "line_no": directive.get("line_no"),
                    "text": directive.get("text"),
                    "target": directive.get("target"),
                }
            )

        include_path = data.get("include_path", [])
        if not isinstance(include_path, list):
            include_path = []

        return {
            "source": {
                "file_path": data.get("file_path"),
                "workspace_dir": data.get("workspace_dir"),
                "bindings_dirs": sorted(data.get("bindings_dirs", [])),
                "include_path": sorted(include_path),
                "directives": shaped_directives,
            },
            "summary": {
                "total_nodes": len(shaped_nodes),
                "total_compats": len(compat_index),
                "total_labels": len(data.get("labels", [])),
            },
            "unresolved_refs": unresolved_refs,
            "chosen_nodes": {
                key: chosen_nodes[key] for key in sorted(chosen_nodes.keys())
            },
            "compat_index": {
                key: sorted(compat_index[key])
                for key in sorted(compat_index.keys())
            },
            "nodes": shaped_nodes,
        }

    def customize_structure(self, structure: Any) -> Any:
        """Subclass hook for custom structure changes.

        Override this to apply organization-specific reshaping without
        requiring a callback at every callsite.
        """
        return structure

    def transform_structure(
        self,
        structure: Any,
        transform: Optional[TransformFn] = None,
        transforms: Optional[Sequence[TransformFn]] = None,
    ) -> Any:
        """Apply customization hooks to the intermediate structure.

        Args:
            structure: Structure from build_structure().
            transform: Optional single transform callback.
            transforms: Optional ordered transform pipeline.

        Returns:
            The transformed structure.

        Raises:
            YAMLConversionError: If transform output is invalid.
        """
        transformed = self.customize_structure(structure)
        self._ensure_valid_root(transformed, "customize_structure")

        if transform is not None:
            transformed = transform(transformed)
            self._ensure_valid_root(transformed, "transform")

        if transforms:
            for idx, fn in enumerate(transforms):
                transformed = fn(transformed)
                self._ensure_valid_root(transformed, f"transforms[{idx}]")

        return transformed

    def to_yaml(
        self,
        data: Any,
        format: str = "semantic",
        transform: Optional[TransformFn] = None,
        transforms: Optional[Sequence[TransformFn]] = None,
        sort_keys: bool = True,
    ) -> str:
        """Convert data to YAML after optional structure customization.

        Args:
            data: Parsed input data.
            format: Logical format label for metadata.
            transform: Optional single transform callback.
            transforms: Optional ordered transform pipeline.
            sort_keys: Whether YAML keys are sorted for deterministic output.

        Returns:
            YAML string.
        """
        try:
            structure = self.build_structure(data, format=format)
            structure = self.transform_structure(
                structure,
                transform=transform,
                transforms=transforms,
            )
            return yaml.safe_dump(
                structure,
                sort_keys=sort_keys,
                default_flow_style=False,
                allow_unicode=True,
            )
        except YAMLConversionError:
            raise
        except Exception as exc:
            raise YAMLConversionError(f"Failed to convert to YAML: {exc}") from exc

    @staticmethod
    def _ensure_valid_root(value: Any, source: str) -> None:
        """Validate the root structure type returned by a hook."""
        if not isinstance(value, (dict, list)):
            raise YAMLConversionError(
                f"{source} must return dict or list, got {type(value).__name__}"
            )

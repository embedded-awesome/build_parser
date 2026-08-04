"""Devicetree parser scaffold with raw source-preserving and semantic modes."""

from __future__ import annotations

import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .devicetree.dtlib import DT, Type
from .devicetree.edtlib import EDT


class DevicetreeParser:
    """Parser for DTS/DTSI files.

    This parser supports two modes:
    - raw: Uses dtlib to expose syntax-oriented node/property data.
    - semantic: Uses edtlib to expose binding-enriched node data.
    """

    def __init__(
        self,
        file_path: str,
        bindings_dirs: Optional[List[str]] = None,
        include_path: Optional[List[str]] = None,
        workspace_dir: Optional[str] = None,
        default_mode: str = "semantic",
        partial: bool = False,
    ):
        """Initialize parser.

        Args:
            file_path: Path to DTS file.
            bindings_dirs: Optional list of binding directories for edtlib.
            include_path: Optional list of include paths for dtlib.
            workspace_dir: Optional workspace root (currently unused for
                          devicetree 0.0.2; reserved for future use).
            default_mode: parse() default mode, either "semantic" or "raw".
            partial: If True, treats file as a partial fragment and wraps with
                    required /dts-v1/ header and root node. Useful for parsing
                    .dtsi files and device tree fragments.
        """
        self.file_path = file_path
        self.bindings_dirs = bindings_dirs or []
        self.include_path = include_path or []
        self.workspace_dir = workspace_dir
        self.default_mode = default_mode
        self.partial = partial

        self.raw_data: Dict[str, Any] = {}
        self.semantic_data: Dict[str, Any] = {}

    def parse(self, mode: Optional[str] = None) -> Dict[str, Any]:
        """Parse the Devicetree file.

        Args:
            mode: Parse mode. If None, uses default_mode.

        Returns:
            Parsed structure.
        """
        selected_mode = mode or self.default_mode
        if selected_mode == "raw":
            return self.parse_raw()
        if selected_mode == "semantic":
            return self.parse_semantic()
        raise ValueError(f"Unknown parse mode: {selected_mode}")

    def parse_raw(self) -> Dict[str, Any]:
        """Parse the file without expanding include directives.

        Raw mode keeps the original source available so callers can regenerate
        the file, while still exposing local node/property data for analysis.
        Include directives are recorded separately and are not inlined.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                original_source = f.read()
        except OSError as exc:
            raise ValueError(
                f"Failed to parse Devicetree file {self.file_path}: {exc}"
            ) from exc

        normalized_source, directives = self._normalize_raw_source(original_source)
        parse_path = self._write_temp_source(normalized_source)
        try:
            dt = DT(parse_path, include_path=(), force=True)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse Devicetree file {self.file_path}: {exc}"
            ) from exc

        nodes: List[Dict[str, Any]] = []
        node_dict: Dict[str, Dict[str, Any]] = {}

        for node in dt.node_iter():
            node_data = self._serialize_dt_node(node, Type)
            nodes.append(node_data)
            node_dict[node.path] = node_data

        unresolved_refs = [
            self._serialize_unresolved_ref(unresolved, Type)
            for unresolved in getattr(dt, "unresolved_refs", [])
        ]

        self.raw_data = {
            "mode": "raw",
            "file_path": self.file_path,
            "source": {
                "text": original_source,
                "line_count": len(original_source.splitlines()),
            },
            "directives": directives,
            "include_path": list(self.include_path),
            "nodes": nodes,
            "node_dict": node_dict,
            "unresolved_refs": unresolved_refs,
            "aliases": [],
            "labels": sorted(self._collect_labels(nodes)),
            "memreserves": [],
        }
        return self.raw_data

    def parse_semantic(self) -> Dict[str, Any]:
        """Parse using devicetree.edtlib for binding-enriched data."""
        unresolved_refs = self._collect_unresolved_refs(self.file_path)

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as exc:
            raise ValueError(
                f"Failed to parse semantic Devicetree {self.file_path}: {exc}"
            ) from exc

        _, directives = self._normalize_raw_source(source)

        parse_path = self.file_path
        if self.partial:
            normalized_source, _ = self._normalize_raw_source(source)
            parse_path = self._write_temp_source(normalized_source)
            unresolved_refs = self._collect_unresolved_refs(parse_path)

        try:
            edt = EDT(
                parse_path,
                self.bindings_dirs,
            )
        except Exception as exc:
            if self._is_tolerable_reg_cells_error(exc, parse_path):
                return self._parse_semantic_tolerant(parse_path, directives)
            raise ValueError(f"Failed to parse semantic Devicetree {self.file_path}: {exc}") from exc

        nodes: List[Dict[str, Any]] = []
        node_dict: Dict[str, Dict[str, Any]] = {}

        for node in edt.nodes:
            node_data = self._serialize_edt_node(node)
            nodes.append(node_data)
            node_dict[node.path] = node_data

        self.semantic_data = {
            "mode": "semantic",
            "file_path": self.file_path,
            "bindings_dirs": list(self.bindings_dirs),
            "include_path": list(self.include_path),
            "directives": directives,
            "workspace_dir": self.workspace_dir,
            "nodes": nodes,
            "node_dict": node_dict,
            "unresolved_refs": unresolved_refs,
            "chosen_nodes": {
                name: self._to_ref_syntax(chosen)
                for name, chosen in edt.chosen_nodes.items()
            },
            "labels": sorted(edt.label2node.keys()),
            "compat_index": {
                compat: [node.path for node in compat_nodes]
                for compat, compat_nodes in edt.compat2nodes.items()
            },
        }
        return self.semantic_data

    def _is_tolerable_reg_cells_error(self, exc: Exception, parse_path: str) -> bool:
        """Return True when reg validation failed due to incomplete parent cell data."""
        message = str(exc)
        if "'reg' property" not in message:
            return False
        if "#address-cells" not in message or "#size-cells" not in message:
            return False

        node_match = re.search(r"<Node\s+([^\s]+)\s+in\s+'[^']+'>", message)
        if not node_match:
            return False

        node_path = node_match.group(1)
        try:
            dt = DT(parse_path, include_path=(), force=True)
            node = dt.get_node(node_path)
        except Exception:
            return False

        parent = node.parent
        if parent is None:
            return False

        has_addr_cells = "#address-cells" in parent.props
        has_size_cells = "#size-cells" in parent.props

        # Keep strict behavior when parent explicitly specifies both values.
        if has_addr_cells and has_size_cells:
            return False

        return True

    def _parse_semantic_tolerant(
        self,
        parse_path: str,
        directives: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Fallback semantic parse for incomplete #*-cells context.

        This path uses dtlib structure data and avoids strict edtlib reg-length
        validation when parent cell metadata is incomplete.
        """
        try:
            dt = DT(parse_path, include_path=(), force=True)
        except Exception as exc:
            raise ValueError(
                f"Failed to parse semantic Devicetree {self.file_path}: {exc}"
            ) from exc

        nodes: List[Dict[str, Any]] = []
        node_dict: Dict[str, Dict[str, Any]] = {}
        compat_index: Dict[str, List[str]] = {}
        alias_map: Dict[str, List[str]] = {}

        for alias, alias_node in dt.alias2node.items():
            alias_map.setdefault(alias_node.path, []).append(alias)

        for node in dt.node_iter():
            compatible_prop = node.props.get("compatible")
            compats: List[str] = []
            if compatible_prop is not None:
                try:
                    compats = list(compatible_prop.to_strings())
                except Exception:
                    compats = []

            status_prop = node.props.get("status")
            status_value: Optional[str] = None
            if status_prop is not None:
                try:
                    status_value = status_prop.to_string()
                except Exception:
                    status_value = None

            node_data = {
                "name": node.name,
                "path": node.path,
                "filename": getattr(node, "filename", None),
                "line_no": getattr(node, "lineno", 0),
                "status": status_value,
                "labels": list(node.labels),
                "aliases": sorted(alias_map.get(node.path, [])),
                "compats": compats,
                "matching_compat": None,
                "binding_path": None,
                "parent_path": node.parent.path if node.parent else None,
                "children": sorted(child.path for child in node.nodes.values()),
                "depends_on": [],
                "required_by": [],
                "properties": {
                    name: self._serialize_dt_property(prop, Type)
                    for name, prop in node.props.items()
                },
            }

            nodes.append(node_data)
            node_dict[node.path] = node_data

            for compat in compats:
                compat_index.setdefault(compat, []).append(node.path)

        chosen_nodes: Dict[str, str] = {}
        try:
            chosen = dt.get_node("/chosen")
            for name, prop in chosen.props.items():
                try:
                    chosen_nodes[name] = self._to_ref_syntax(prop.to_path())
                except Exception:
                    continue
        except Exception:
            pass

        self.semantic_data = {
            "mode": "semantic",
            "file_path": self.file_path,
            "bindings_dirs": list(self.bindings_dirs),
            "include_path": list(self.include_path),
            "directives": directives,
            "workspace_dir": self.workspace_dir,
            "nodes": nodes,
            "node_dict": node_dict,
            "unresolved_refs": self._collect_unresolved_refs(parse_path),
            "chosen_nodes": chosen_nodes,
            "labels": sorted(dt.label2node.keys()),
            "compat_index": {
                compat: sorted(paths)
                for compat, paths in sorted(compat_index.items())
            },
            "semantic_fallback": "missing-cells-tolerant",
        }
        return self.semantic_data

    def _collect_unresolved_refs(self, parse_path: str) -> List[Dict[str, Any]]:
        """Collect unresolved top-level &label fragments from a DTS source."""
        try:
            dt = DT(parse_path, include_path=(), force=True)
        except Exception:
            return []

        return [
            self._serialize_unresolved_ref(unresolved, Type)
            for unresolved in getattr(dt, "unresolved_refs", [])
        ]

    def _normalize_raw_source(self, source: str) -> Tuple[str, List[Dict[str, Any]]]:
        """Remove include directives from the parse input while preserving source."""
        lines = source.splitlines(keepends=True)
        normalized_lines: List[str] = []
        directives: List[Dict[str, Any]] = []

        include_pattern = re.compile(
            r'(?:(?:/include/|#\s*include)\s+)(?:"([^"]+)"|<([^>]+)>)'
        )

        for line_no, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            include_match = include_pattern.match(stripped)
            if include_match:
                directive_target = include_match.group(1) or include_match.group(2)
                directives.append(
                    {
                        "line_no": line_no,
                        "text": line.rstrip("\n"),
                        "target": directive_target,
                    }
                )
                normalized_lines.append("\n" if line.endswith("\n") else "")
                continue

            normalized_lines.append(line)

        normalized_source = "".join(normalized_lines)
        if self.partial:
            has_header = bool(
                re.search(r"^\s*/dts-v1/\s*;", normalized_source, re.MULTILINE)
            )
            if not has_header:
                normalized_source = f"/dts-v1/;\n{normalized_source}"

            has_root = bool(
                re.search(r"^\s*/\s*\{", normalized_source, re.MULTILINE)
            )
            if not has_root:
                normalized_source = f"/ {{\n{normalized_source}\n}};\n"

        return normalized_source, directives

    @staticmethod
    def _write_temp_source(content: str) -> str:
        """Write content to a temporary DTS file and return its path."""
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".dts",
            delete=False,
            encoding="utf-8",
        )
        temp_file.write(content)
        temp_file.close()
        return temp_file.name

    @staticmethod
    def _collect_labels(nodes: List[Dict[str, Any]]) -> List[str]:
        labels: List[str] = []
        for node in nodes:
            labels.extend(node.get("labels", []))
        return labels

    def _serialize_dt_node(self, node: Any, type_enum: Any) -> Dict[str, Any]:
        """Serialize a dtlib node to a plain dictionary."""
        return {
            "name": node.name,
            "path": node.path,
            "filename": getattr(node, "filename", ""),
            "line_no": getattr(node, "lineno", 0),
            "unit_addr": node.unit_addr,
            "labels": list(node.labels),
            "parent_path": node.parent.path if node.parent else None,
            "children": sorted(child.path for child in node.nodes.values()),
            "properties": {
                name: self._serialize_dt_property(prop, type_enum)
                for name, prop in node.props.items()
            },
        }

    def _serialize_detached_dt_node(self, node: Any, type_enum: Any) -> Dict[str, Any]:
        """Serialize a detached dtlib node without path-based indexing."""
        return {
            "name": node.name,
            "filename": getattr(node, "filename", ""),
            "line_no": getattr(node, "lineno", 0),
            "labels": list(node.labels),
            "properties": {
                name: self._serialize_dt_property(prop, type_enum)
                for name, prop in node.props.items()
            },
            "children": [
                self._serialize_detached_dt_node(child, type_enum)
                for child in node.nodes.values()
            ],
        }

    def _serialize_unresolved_ref(self, unresolved: Any, type_enum: Any) -> Dict[str, Any]:
        """Serialize an unresolved top-level &label { ... } fragment."""
        return {
            "reference": unresolved.ref,
            "reference_syntax": f"&{unresolved.ref}",
            "reference_kind": "path" if str(unresolved.ref).startswith("{") else "label",
            "label": unresolved.label,
            "fragment": self._serialize_detached_dt_node(unresolved.node, type_enum),
        }

    def _serialize_dt_property(self, prop: Any, type_enum: Any) -> Dict[str, Any]:
        """Serialize a dtlib property with best-effort typed conversion."""
        ptype = prop.type
        type_name = ptype.name.lower() if hasattr(ptype, "name") else str(ptype)

        value: Any
        try:
            if ptype is type_enum.EMPTY:
                value = True
            elif ptype is type_enum.STRING:
                value = prop.to_string()
            elif ptype is type_enum.STRINGS:
                value = prop.to_strings()
            elif ptype is type_enum.NUM:
                cell_items = getattr(prop, "_cell_items", None)
                if isinstance(cell_items, list) and any(
                    isinstance(item, str) for item in cell_items
                ):
                    value = cell_items
                else:
                    value = self._to_num_signed_aware(prop)
            elif ptype is type_enum.NUMS:
                cell_items = getattr(prop, "_cell_items", None)
                if isinstance(cell_items, list) and any(
                    isinstance(item, str) for item in cell_items
                ):
                    value = cell_items
                else:
                    value = self._to_nums_signed_aware(prop)
            elif ptype is type_enum.BYTES:
                value = {"type": "bytes", "hex": prop.to_bytes().hex()}
            elif ptype is type_enum.PHANDLE:
                value = self._to_ref_syntax(prop.to_node())
            elif ptype is type_enum.PHANDLES:
                value = [self._to_ref_syntax(node) for node in prop.to_nodes()]
            elif ptype is type_enum.PATH:
                value = self._to_ref_syntax(prop.to_path())
            else:
                # Compound values are intentionally preserved as bytes for now.
                value = {"type": "compound", "hex": prop.value.hex()}
        except Exception:
            # Keep raw bytes representation when type-specific conversion fails.
            value = {"type": "raw", "hex": prop.value.hex()}

        return {
            "type": type_name,
            "value": value,
            "labels": list(prop.labels),
        }

    @staticmethod
    def _to_num_signed_aware(prop: Any) -> int:
        """Convert to int, preferring signed-aware conversion when available."""
        try:
            return prop.to_num(signed_aware=True)
        except TypeError:
            return prop.to_num()

    @staticmethod
    def _to_nums_signed_aware(prop: Any) -> List[int]:
        """Convert to list[int], preferring signed-aware conversion when available."""
        try:
            return prop.to_nums(signed_aware=True)
        except TypeError:
            return prop.to_nums()

    @staticmethod
    def _to_ref_syntax(node: Any) -> str:
        """Format a node reference as &label when available, else &{/path}."""
        labels = list(getattr(node, "labels", []) or [])
        if labels:
            return f"&{labels[0]}"

        path = getattr(node, "path", None)
        if isinstance(path, str) and path:
            return f"&{{{path}}}"

        return str(node)

    def _serialize_edt_node(self, node: Any) -> Dict[str, Any]:
        """Serialize an edtlib node to a plain dictionary."""
        return {
            "name": node.name,
            "path": node.path,
            "filename": getattr(node, "filename", None),
            "line_no": getattr(node, "lineno", 0),
            "status": node.status,
            "labels": list(node.labels),
            "aliases": list(node.aliases),
            "compats": list(node.compats),
            "matching_compat": node.matching_compat,
            "binding_path": node.binding_path,
            "parent_path": node.parent.path if node.parent else None,
            "children": sorted(child.path for child in node.children.values()),
            "depends_on": [dep.path for dep in node.depends_on],
            "required_by": [req.path for req in node.required_by],
            "properties": {
                name: self._serialize_edt_property(prop)
                for name, prop in node.props.items()
            },
        }

    def _serialize_edt_property(self, prop: Any) -> Dict[str, Any]:
        """Serialize an edtlib property object."""
        description = ""
        try:
            if prop.description:
                description = prop.description.strip()
        except (AttributeError, TypeError):
            pass
        
        return {
            "type": prop.type,
            "value": self._serialize_semantic_value(prop.val),
            "description": description,
        }

    def _serialize_semantic_value(self, value: Any) -> Any:
        """Serialize edtlib semantic values to plain JSON/YAML-compatible types."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, bytes):
            return {"type": "bytes", "hex": value.hex()}

        if isinstance(value, list):
            return [self._serialize_semantic_value(item) for item in value]

        if isinstance(value, dict):
            return {
                str(key): self._serialize_semantic_value(val)
                for key, val in value.items()
            }

        if hasattr(value, "path"):
            return self._to_ref_syntax(value)

        if hasattr(value, "controller") and hasattr(value, "data"):
            controller = getattr(value, "controller", None)
            return {
                "controller": self._to_ref_syntax(controller) if controller else None,
                "data": self._serialize_semantic_value(value.data),
                "name": getattr(value, "name", None),
                "basename": getattr(value, "basename", None),
            }

        return str(value)

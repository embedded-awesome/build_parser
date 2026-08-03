"""Render a DTSI file from converted YAML using a Jinja template."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined


def _format_bytes_hex(hex_value: str) -> str:
    """Render compact hex as DTS byte-array format, e.g. aabb -> [aa bb]."""
    cleaned = "".join(ch for ch in hex_value.strip().lower() if ch in "0123456789abcdef")
    if len(cleaned) % 2 != 0:
        cleaned = f"0{cleaned}"
    pairs = [cleaned[index:index + 2] for index in range(0, len(cleaned), 2)]
    return "[{}]".format(" ".join(pairs))


def _load_payload(yaml_path: Path) -> Dict[str, Any]:
    content = yaml_path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(content)
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping at YAML root: {yaml_path}")

    payload = loaded.get("data", loaded)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected `data` mapping in YAML: {yaml_path}")
    return payload


def render_dtsi(yaml_path: Path, template_path: Path) -> str:
    payload = _load_payload(yaml_path)

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["format_bytes_hex"] = _format_bytes_hex

    template = env.get_template(template_path.name)
    return template.render(payload=payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct DTS/DTSI text from converted semantic YAML"
    )
    parser.add_argument("yaml_file", type=Path, help="Input YAML file")
    parser.add_argument(
        "--template",
        type=Path,
        default=Path(__file__).resolve().parent / "templates" / "devicetree_reconstruct.dtsi.j2",
        help="Path to Jinja template",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output DTSI file path")

    args = parser.parse_args()

    rendered = render_dtsi(args.yaml_file, args.template)
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()

"""Example script: parse samples/dts files and print converted YAML."""

from pathlib import Path

from build_converter.devicetree_parser import DevicetreeParser
from build_converter.yaml_converter import YAMLConverter


def main() -> None:
  dts_dir = Path("samples/dts")
  files = sorted(list(dts_dir.glob("*.dts")) + list(dts_dir.glob("*.dtsi")))

  if not files:
    print(f"No DTS files found in {dts_dir}")
    return

  converter = YAMLConverter()

  # Semantic mode may fail without complete binding directories, so we fall
  # back to raw mode for a robust example.
  for file_path in files:
    print(f"\n=== {file_path} ===")

    is_partial = file_path.suffix == ".dtsi"
    parser = DevicetreeParser(
      str(file_path),
      bindings_dirs=[],
      default_mode="semantic",
      partial=is_partial,
    )

    try:
      parsed = parser.parse(mode="semantic")
      yaml_data = converter.to_yaml(parsed, format="devicetree-semantic")
    except Exception as exc:
      print(f"Semantic parse failed ({exc}); falling back to raw mode")
      try:
        parsed = parser.parse(mode="raw")
        source_info = parsed.get("source", {})
        directives = parsed.get("directives", [])
        print(
          "Raw parse preserved source "
          f"({source_info.get('line_count', 0)} lines) "
          f"and captured {len(directives)} include directives"
        )
        yaml_data = converter.to_yaml(parsed, format="raw")
      except Exception as raw_exc:
        print(f"Raw parse also failed ({raw_exc})")
        continue

    print(yaml_data)


if __name__ == "__main__":
  main()
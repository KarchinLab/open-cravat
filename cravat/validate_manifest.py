import argparse
import yaml


REQUIRED_FIELDS = ["name", "version", "description"]
OPTIONAL_FIELDS = ["homepage", "contact", "license"]


def validate_manifest(manifest_path):
    """Validate a module info.yaml manifest."""

    try:
        with open(manifest_path, "r", encoding="utf-8") as file:
            manifest = yaml.safe_load(file)
    except yaml.YAMLError as error:
        print(f"❌ Invalid YAML in {manifest_path}: {error}")
        return False
    except OSError as error:
        print(f"❌ Could not read {manifest_path}: {error}")
        return False

    if not isinstance(manifest, dict):
        print(f"❌ Invalid manifest format in {manifest_path}")
        return False

    module_name = manifest.get("name", manifest_path)

    valid = True

    # Check required fields.
    for field in REQUIRED_FIELDS:
        if field not in manifest or manifest[field] in (None, ""):
            print(f"❌ Required field '{field}' missing in module {module_name}")
            valid = False

    # Check optional fields.
    for field in OPTIONAL_FIELDS:
        if field not in manifest or manifest[field] in (None, ""):
            print(f"⚠️ Optional field '{field}' missing in module {module_name}")

    if valid:
        print(f"✅ Manifest validation passed for module {module_name}")

    return valid


def main():
    parser = argparse.ArgumentParser(
        description="Validate OpenCRAVAT module info.yaml manifests."
    )

    parser.add_argument(
        "manifest",
        nargs="+",
        help="Path to one or more info.yaml files",
    )

    args = parser.parse_args()

    all_valid = True

    for manifest_path in args.manifest:
        if not validate_manifest(manifest_path):
            all_valid = False

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
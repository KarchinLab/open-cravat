from validate_manifest import validate_manifest


def test_complete_manifest(tmp_path, capsys):
    manifest = tmp_path / "info.yaml"
    manifest.write_text(
        """
name: test_module
version: 1.0
description: Test OpenCRAVAT module
homepage: https://example.com
contact: test@example.com
license: MIT
""",
        encoding="utf-8",
    )

    assert validate_manifest(manifest) is True

    output = capsys.readouterr().out
    assert "Manifest validation passed" in output
    assert "Optional field" not in output


def test_missing_optional_fields(tmp_path, capsys):
    manifest = tmp_path / "info.yaml"
    manifest.write_text(
        """
name: test_module
version: 1.0
description: Test OpenCRAVAT module
""",
        encoding="utf-8",
    )

    assert validate_manifest(manifest) is True

    output = capsys.readouterr().out
    assert "Optional field 'homepage' missing" in output
    assert "Optional field 'contact' missing" in output
    assert "Optional field 'license' missing" in output
    assert "Manifest validation passed" in output


def test_missing_required_field(tmp_path, capsys):
    manifest = tmp_path / "info.yaml"
    manifest.write_text(
        """
name: test_module
version: 1.0
""",
        encoding="utf-8",
    )

    assert validate_manifest(manifest) is False

    output = capsys.readouterr().out
    assert "Required field 'description' missing" in output
    assert "Manifest validation passed" not in output


def test_invalid_yaml(tmp_path, capsys):
    manifest = tmp_path / "info.yaml"
    manifest.write_text(
        """
name: test_module
version: [1.0
description: Test OpenCRAVAT module
""",
        encoding="utf-8",
    )

    assert validate_manifest(manifest) is False

    output = capsys.readouterr().out
    assert "Invalid YAML" in output
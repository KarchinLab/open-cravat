"""Tests for `oc module freeze` / `oc module install-freeze` commands.

The command implementations live in cravat.cravat_admin as freeze_modules()
and install_freeze_modules(). They take a SimpleNamespace `args` object, which
makes them straightforward to exercise directly without going through argparse.
"""
import json
import sys
from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cravat import cravat_admin


def _module_info(name, version, type="annotator", hidden=False):
    return SimpleNamespace(
        name=name, version=version, type=type, hidden=hidden
    )


# ---------------------------------------------------------------------------
# freeze_modules
# ---------------------------------------------------------------------------


def test_freeze_outputs_all_modules_including_hidden(capsys):
    modules = {
        "m1": _module_info("m1", "1.0"),
        "hidden1": _module_info("hidden1", "2.0", hidden=True),
    }
    with patch("cravat.cravat_admin.au.search_local", return_value=["m1", "hidden1"]), \
         patch("cravat.cravat_admin.au.get_local_module_info", side_effect=lambda n: modules[n]):
        cravat_admin.freeze_modules(SimpleNamespace(md=None))
    data = json.loads(capsys.readouterr().out)
    assert {m["name"] for m in data} == {"m1", "hidden1"}
    by_name = {m["name"]: m for m in data}
    assert by_name["m1"] == {"name": "m1", "version": "1.0", "type": "annotator"}
    assert by_name["hidden1"]["version"] == "2.0"


def test_freeze_outputs_empty_when_no_modules(capsys):
    with patch("cravat.cravat_admin.au.search_local", return_value=[]):
        cravat_admin.freeze_modules(SimpleNamespace(md=None))
    assert json.loads(capsys.readouterr().out) == []


def test_freeze_sets_modules_dir_when_md_given(capsys):
    with patch("cravat.cravat_admin.au.search_local", return_value=[]), \
         patch("cravat.cravat_admin.constants") as mock_constants:
        cravat_admin.freeze_modules(SimpleNamespace(md="/some/path"))
    assert mock_constants.custom_modules_dir == "/some/path"


# ---------------------------------------------------------------------------
# install_freeze_modules
# ---------------------------------------------------------------------------


def _write_freeze_file(tmp_path, entries):
    p = tmp_path / "freeze.json"
    p.write_text(json.dumps(entries))
    return str(p)


def _entry(name, version):
    return {"name": name, "version": version, "type": "annotator"}


def test_install_freeze_installs_missing_modules(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0"), _entry("b", "2.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"):
        cravat_admin.install_freeze_modules(args)
    installed = {call.args[0]: call.kwargs["version"] for call in mock_install.call_args_list}
    assert installed == {"a": "1.0", "b": "2.0"}


def test_install_freeze_reads_from_stdin(tmp_path, monkeypatch, capsys):
    payload = json.dumps([_entry("a", "1.0")])
    monkeypatch.setattr(sys, "stdin", StringIO(payload))
    args = SimpleNamespace(
        freeze_file="-", force=False, yes=True,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"):
        cravat_admin.install_freeze_modules(args)
    assert mock_install.call_count == 1
    assert mock_install.call_args.args[0] == "a"


def test_install_freeze_skips_already_installed_at_same_version(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0"), _entry("b", "2.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=False, md=None,
    )
    # 'a' installed at 1.0 -> skipped; 'b' not installed -> installed
    local = {"a": _module_info("a", "1.0")}

    def fake_get_local(name):
        return local.get(name)

    with patch("cravat.cravat_admin.au.get_local_module_info", side_effect=fake_get_local), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"):
        cravat_admin.install_freeze_modules(args)
    out = capsys.readouterr().out
    assert "a:1.0" in out and "skipping" in out.lower()
    installed = [c.args[0] for c in mock_install.call_args_list]
    assert installed == ["b"]


def test_install_freeze_force_reinstalls_already_installed(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=True, yes=True,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info",
               return_value=_module_info("a", "1.0")), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"):
        cravat_admin.install_freeze_modules(args)
    assert mock_install.call_count == 1
    assert mock_install.call_args.kwargs["force"] is True


def test_install_freeze_all_already_installed_no_prompt_no_install(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=False,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info",
               return_value=_module_info("a", "1.0")), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input") as mock_input:
        cravat_admin.install_freeze_modules(args)
    out = capsys.readouterr().out
    assert "No modules to install" in out
    assert "skipping" in out.lower()
    mock_input.assert_not_called()
    mock_install.assert_not_called()


def test_install_freeze_empty_file_returns_early(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=False,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input") as mock_input:
        cravat_admin.install_freeze_modules(args)
    out = capsys.readouterr().out
    assert "No modules in freeze file" in out
    mock_input.assert_not_called()
    mock_install.assert_not_called()


def test_install_freeze_yes_skips_prompt(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module"), \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input") as mock_input:
        cravat_admin.install_freeze_modules(args)
    mock_input.assert_not_called()


def test_install_freeze_prompt_n_aborts(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=False,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input", return_value="n"):
        cravat_admin.install_freeze_modules(args)
    mock_install.assert_not_called()


def test_install_freeze_prompt_y_proceeds(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=False,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input", return_value="y"):
        cravat_admin.install_freeze_modules(args)
    assert mock_install.call_count == 1


def test_install_freeze_prompt_invalid_then_y(tmp_path, capsys):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=False,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"), \
         patch("builtins.input", side_effect=["x", "y"]) as mock_input:
        cravat_admin.install_freeze_modules(args)
    assert mock_input.call_count == 2
    assert mock_install.call_count == 1


@pytest.mark.parametrize("include_deps, expected", [(True, True), (False, False)])
def test_install_freeze_include_dependencies_flag(tmp_path, include_deps, expected):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=include_deps, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module") as mock_install, \
         patch("cravat.cravat_admin.Module"):
        cravat_admin.install_freeze_modules(args)
    assert mock_install.call_args.kwargs["install_pypi_dependency"] is expected


def test_install_freeze_sets_modules_dir_when_md_given(tmp_path):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=False, md="/custom/dir",
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module"), \
         patch("cravat.cravat_admin.Module"), \
         patch("cravat.cravat_admin.constants") as mock_constants:
        cravat_admin.install_freeze_modules(args)
    assert mock_constants.custom_modules_dir == "/custom/dir"


def test_install_freeze_invalidates_module_cache(tmp_path):
    freeze_file = _write_freeze_file(tmp_path, [_entry("a", "1.0")])
    args = SimpleNamespace(
        freeze_file=freeze_file, force=False, yes=True,
        include_dependencies=False, md=None,
    )
    with patch("cravat.cravat_admin.au.get_local_module_info", return_value=None), \
         patch("cravat.cravat_admin.au.install_module"), \
         patch("cravat.cravat_admin.Module") as mock_module:
        cravat_admin.install_freeze_modules(args)
    mock_module.invalidate_cache.assert_called_once()


# ---------------------------------------------------------------------------
# argparse wiring: oc module freeze / install-freeze exist & share parsers
# ---------------------------------------------------------------------------


def test_freeze_subparser_registered_on_oc():
    import cravat.oc as oc
    # The oc subparsers must exist and mirror the cravat_admin parsers' args.
    admin_freeze_dests = {a.dest for a in cravat_admin.parser_freeze._actions}
    oc_freeze_dests = {a.dest for a in oc.module_freeze_p._actions}
    # 'help' differs because oc uses add_help=False; the shared args must match.
    assert admin_freeze_dests - {"help"} <= oc_freeze_dests
    admin_if_dests = {a.dest for a in cravat_admin.parser_install_freeze._actions}
    oc_if_dests = {a.dest for a in oc.module_install_freeze_p._actions}
    assert admin_if_dests - {"help"} <= oc_if_dests


def test_freeze_parser_has_no_include_hidden():
    # --include-hidden was removed; freeze includes hidden modules by default.
    actions = {a.dest: a for a in cravat_admin.parser_freeze._actions}
    assert "include_hidden" not in actions


def test_install_freeze_parser_has_include_dependencies_not_skip():
    actions = {a.dest: a for a in cravat_admin.parser_install_freeze._actions}
    assert "include_dependencies" in actions
    assert "skip_dependencies" not in actions
    # default is opt-in (False)
    assert actions["include_dependencies"].default is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

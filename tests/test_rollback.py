import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


def test_rollback_preserves_other_mcp_changes(tmp_path):
    path = Path(__file__).resolve().parents[1] / "rollback.py"
    spec = importlib.util.spec_from_file_location("rollback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / ".agent-reach/tools/agent-reach-plus"
    backup = root / "backups/2026-10-05"
    backup.mkdir(parents=True)
    original = '[mcp_servers.agent-reach]\ncommand="old.exe"\nargs=[]\n\n[mcp_servers.other]\ncommand="previous.exe"\n'
    current = '[mcp_servers.agent-reach]\ncommand="new.exe"\nargs=[]\n\n[mcp_servers.agent-reach.env]\nPYTHONUTF8="1"\n\n[mcp_servers.other]\ncommand="user-new-setting.exe"\n'
    config = tmp_path / "config.toml"
    config.write_text(current)
    (backup / "config.toml.original").write_text(original)
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("extended")
    original_skill = backup / "agent-reach-skill"
    original_skill.mkdir()
    (original_skill / "SKILL.md").write_text("original")
    (root / "manifest.json").write_text(json.dumps({"codex_config": str(config), "skill_path": str(skill)}))
    with patch.object(module.Path, "home", return_value=tmp_path):
        module.main()
    result = config.read_text()
    assert 'command="old.exe"' in result
    assert 'command="user-new-setting.exe"' in result
    assert "agent-reach.env" not in result
    assert (skill / "SKILL.md").read_text() == "original"

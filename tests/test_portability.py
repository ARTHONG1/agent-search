import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_reach_plus import transport


def test_unix_venv_cli_found_without_activation(tmp_path):
    python = tmp_path / 'bin/python'
    python.parent.mkdir()
    python.touch()
    (python.parent / 'bili').touch()
    with patch.object(sys, 'platform', 'darwin'), patch.object(sys, 'executable', str(python)), patch('shutil.which', return_value=None):
        assert transport.cli_argv('bili') == [str(python.parent / 'bili')]


def test_node_binding_survives_empty_desktop_path(tmp_path):
    node = tmp_path / 'Homebrew Space/node'
    node.parent.mkdir()
    node.touch()
    package = tmp_path / 'node-tools/node_modules/mcporter'
    package.mkdir(parents=True)
    (package / 'package.json').write_text(json.dumps({'bin': {'mcporter': 'dist/cli.js'}}))
    (package / 'dist').mkdir()
    (package / 'dist/cli.js').touch()
    (tmp_path / 'bindings.json').write_text(json.dumps({'node': str(node)}))
    with patch.object(transport, 'ROOT', tmp_path), patch('shutil.which', return_value=None):
        assert transport.cli_argv('mcporter') == [str(node), str(package / 'dist/cli.js')]


def test_missing_ytdlp_not_reported_installed():
    with patch('importlib.util.find_spec', return_value=None):
        assert transport.has_cli('yt-dlp') is False


def test_posix_process_owner_uses_process_group():
    from agent_reach_plus.process_owner import ProcessOwner
    with patch('agent_reach_plus.process_owner.os.name', 'posix'), patch('os.killpg', create=True) as kill, patch('signal.SIGKILL', 9, create=True):
        owner = ProcessOwner()
        assert owner.launch_options() == {'start_new_session': True}
        owner.attach(type('Process', (), {'pid': 4321})())
        owner.close()
        kill.assert_called_once_with(4321, 9)


def test_fresh_install_and_rollback_preserve_other_settings(tmp_path):
    from agent_reach_plus.deployment import register, restore
    root = tmp_path / 'Installed Space'
    release = root / 'releases/new'
    release.mkdir(parents=True)
    config = tmp_path / 'codex/config.toml'
    config.parent.mkdir()
    config.write_text('# user comment\nmodel = "unchanged"\n[mcp_servers.other]\ncommand="old-other"\n')
    skill = tmp_path / 'skills/agent-reach'
    register(root, release, config, skill, Path('/Users/test/bin/python'))
    import tomllib
    data = tomllib.loads(config.read_text())
    assert data['mcp_servers']['agent-reach']['command'] == '/Users/test/bin/python'
    config.write_text(config.read_text().replace('old-other', 'user-edit'))
    restore(root)
    data = tomllib.loads(config.read_text())
    assert 'agent-reach' not in data['mcp_servers']
    assert data['mcp_servers']['other']['command'] == 'user-edit'
    assert '# user comment' in config.read_text()
    assert not (skill / 'SKILL.md').exists()


def test_upgrade_restores_quoted_entry_and_original_skill(tmp_path):
    from agent_reach_plus.deployment import register, restore
    root = tmp_path / 'root'
    release = root / 'releases/new'
    release.mkdir(parents=True)
    config = tmp_path / 'config.toml'
    original = '[mcp_servers."agent-reach"]\ncommand="old"\n[mcp_servers."agent-reach".env]\nCUSTOM="keep"\n[mcp_servers.other]\ncommand="other"\n'
    config.write_text(original)
    skill = tmp_path / 'skill'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('---\nname: agent-reach\n---\nOriginal rules\n')
    register(root, release, config, skill, Path('/Users/test/bin/python'))
    import tomllib
    assert tomllib.loads(config.read_text())['mcp_servers']['agent-reach']['env']['CUSTOM'] == 'keep'
    restore(root)
    assert tomllib.loads(config.read_text()) == tomllib.loads(original)
    assert (skill / 'SKILL.md').read_text() == '---\nname: agent-reach\n---\nOriginal rules\n'


def test_rollback_does_not_clobber_later_agent_edits(tmp_path):
    from agent_reach_plus.deployment import register, restore
    root = tmp_path / 'root'
    release = root / 'releases/new'
    release.mkdir(parents=True)
    config = tmp_path / 'config.toml'
    skill = tmp_path / 'skill'
    register(root, release, config, skill, Path('/Users/test/bin/python'))
    config.write_text(config.read_text().replace('120', '121'))
    before = config.read_bytes()
    with pytest.raises(RuntimeError, match='changed'):
        restore(root)
    assert config.read_bytes() == before


def test_skill_upgrade_removes_old_windows_prefix_and_preserves_original():
    from agent_reach_plus.deployment import skill_text
    text = '---\nname: agent-reach\n---\n\n# Agent-Reach Plus: Codex 검색·수집 MCP\n\nOld launcher C:/Users/example/old.py\n\n# Agent Reach — Original\nOriginal body\n'
    updated = skill_text(text)
    assert updated.startswith('---\nname: agent-reach\n---\n')
    assert 'C:/Users/example/old.py' not in updated
    assert '# Agent Reach — Original\nOriginal body\n' in updated


def test_registration_failure_restores_config_and_skill(tmp_path):
    import agent_reach_plus.deployment as deployment
    root = tmp_path / 'root'
    release = root / 'release'
    release.mkdir(parents=True)
    config = tmp_path / 'config.toml'
    config.write_text('model="unchanged"\n')
    skill = tmp_path / 'skill'
    skill.mkdir()
    (skill / 'SKILL.md').write_text('original rules')
    real_atomic = deployment.atomic_text
    def fail_manifest(path, text):
        if path == root / 'manifest.json':
            raise OSError('simulated write failure')
        real_atomic(path, text)
    with patch.object(deployment, 'atomic_text', side_effect=fail_manifest):
        with pytest.raises(OSError):
            deployment.register(root, release, config, skill, Path('/Users/test/bin/python'))
    assert config.read_text() == 'model="unchanged"\n'
    assert (skill / 'SKILL.md').read_text() == 'original rules'

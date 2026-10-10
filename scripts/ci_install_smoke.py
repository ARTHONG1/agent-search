"""Exercise a clean install, real MCP handshake and rollback in an isolated path."""
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def main():
    repo = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='agent-search smoke 한국 ') as directory:
        base = Path(directory)
        root = base / 'installed root'
        config = base / 'codex/config.toml'
        config.parent.mkdir()
        config.write_text('# preserve user comment\nmodel="test-model"\n[mcp_servers.other]\ncommand="keep-me"\n', encoding='utf-8')
        original = tomllib.loads(config.read_text(encoding='utf-8'))
        skill = base / 'skills/agent-reach'
        env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
        # The checkout PATH/root used for unit tests must not override the new install.
        env.pop('AGENT_REACH_PLUS_HOME', None)
        commands = [
            [sys.executable, str(repo / 'install.py'), '--root', str(root), '--config', str(config), '--skill', str(skill)],
            [sys.executable, str(repo / 'diagnose.py'), '--root', str(root), '--quick'],
            [sys.executable, str(repo / 'rollback.py'), '--root', str(root)],
        ]
        for command in commands:
            subprocess.run(command, cwd=repo, env=env, check=True, timeout=900)
        assert tomllib.loads(config.read_text(encoding='utf-8')) == original
        assert '# preserve user comment' in config.read_text(encoding='utf-8')
        assert not (skill / 'SKILL.md').exists()
        print('Clean install, MCP handshake and scoped rollback passed.')


if __name__ == '__main__':
    main()

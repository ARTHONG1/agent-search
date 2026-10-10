"""Restore only the Agent-Reach config entry and original skill; leave other settings intact."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

PATTERN = re.compile(r'^\[mcp_servers\.agent-reach\][\s\S]*?(?=^\[(?!mcp_servers\.agent-reach(?:\.|\]))|\Z)', re.MULTILINE)


def main(root=None):
    root = root or Path.home() / '.agent-reach/tools/agent-reach-plus'
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') == 2:
        release = Path(manifest['release'])
        python = release / ('runtime/Scripts/python.exe' if sys.platform == 'win32' else 'runtime/bin/python')
        raise SystemExit(subprocess.run([str(python), '-m', 'agent_reach_plus.deployment', '--root', str(root), '--restore'], timeout=30).returncode)
    config = Path(manifest['codex_config'])
    original = (root / 'backups/2026-10-05/config.toml.original').read_text(encoding='utf-8')
    current = config.read_text(encoding='utf-8')
    match = PATTERN.search(original)
    if not match:
        raise SystemExit('Original Agent-Reach section unavailable; no change made')
    replacement, count = PATTERN.subn(lambda _: match.group(), current, count=1)
    if count != 1:
        raise SystemExit('Current Agent-Reach section unavailable; no change made')
    tomllib.loads(replacement)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    shutil.copy2(config, root / 'backups' / f'config-before-rollback-{stamp}.toml')
    temporary = config.with_name(config.name + '.agent-reach-restore.tmp')
    temporary.write_text(replacement, encoding='utf-8')
    os.replace(temporary, config)
    skill = Path(manifest['skill_path'])
    shutil.copytree(skill, root / 'backups' / f'skill-before-rollback-{stamp}')
    shutil.copytree(root / 'backups/2026-10-05/agent-reach-skill', skill, dirs_exist_ok=True)
    # Added upstream docs can remain as unused reference material.
    print('Original Agent-Reach entry and skill restored. Reload MCP connections in Codex.')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path)
    main(parser.parse_args().root)

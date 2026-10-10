"""Reject tracked machine state; also inspect binary archive members."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

FORBIDDEN_DIRS = {'.codex', '.agent-reach', '.opencli', '.ssh', 'backups', 'runtime', 'runtimes', 'releases', 'node_modules', 'work', '__pycache__', '.venv'}
FORBIDDEN_FILES = {'config.toml', 'config.yaml', 'config.yml', '.npmrc', 'bindings.json', 'hosts.yml', 'auth.json', 'credentials.json'}


def forbidden(name):
    path = Path(name)
    return bool(set(path.parts) & FORBIDDEN_DIRS) or path.name in FORBIDDEN_FILES or path.name.startswith('.env') or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.log', '.db', '.sqlite', '.pyc'}


def main():
    repo = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=repo).decode('utf-8').split('\0')
    names = [name for name in names if name]
    if not names:
        raise SystemExit('No tracked files to inspect; stage the publication first.')
    failures = []
    for name in names:
        if forbidden(name):
            failures.append(name)
        path = repo / name
        if path.suffix in {'.whl', '.zip'}:
            with zipfile.ZipFile(path) as archive:
                failures.extend(f'{name}: {member}' for member in archive.namelist() if forbidden(member))
    manifest = json.loads((repo / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'portable-source' or any(key in manifest for key in ('installed_entry', 'backup', 'installed_root', 'codex_config', 'skill_path')):
        failures.append('manifest.json is machine state instead of public source metadata')
    if failures:
        print('Publication blocked by file names:', '\n'.join(failures), file=sys.stderr)
        raise SystemExit(1)
    print(f'Publication file guard passed: {len(names)} tracked files; archives inspected.')


if __name__ == '__main__':
    main()

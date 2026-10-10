"""Portable, staged installation. Register only after a real MCP handshake."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import venv
from datetime import datetime
from pathlib import Path

SOURCE = Path(__file__).resolve().parent


def run(argv, *, env=None, timeout=900):
    print('Running:', Path(str(argv[0])).name, ' '.join(str(a) for a in argv[1:3]), flush=True)
    child_env = dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    child_env.update(env or {})
    subprocess.run([str(a) for a in argv], check=True, env=child_env, timeout=timeout)


def executable(name: str, explicit=None):
    if explicit:
        path = Path(explicit).expanduser().absolute()
        if not path.is_file():
            raise RuntimeError(f'{name} executable unavailable')
        return str(path)
    found = shutil.which(name)
    if found:
        return found
    if sys.platform == 'darwin':
        for directory in ('/opt/homebrew/opt/node@24/bin', '/usr/local/opt/node@24/bin', '/opt/homebrew/bin', '/usr/local/bin'):
            path = Path(directory) / name
            if path.is_file() and os.access(path, os.X_OK):
                return str(path)
    return None


def npm_script(node: str) -> Path:
    directory = Path(node).parent
    candidates = [directory / 'node_modules/npm/bin/npm-cli.js', directory.parent / 'lib/node_modules/npm/bin/npm-cli.js']
    npm = shutil.which('npm')
    if npm:
        resolved = Path(npm).resolve()
        if resolved.suffix == '.js':
            candidates.insert(0, resolved)
        candidates.append(resolved.parent / 'node_modules/npm/bin/npm-cli.js')
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError('npm-cli.js unavailable; install Node.js 24 with npm')


def install(root, config, skill, node, gh):
    metadata = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    wheel = SOURCE / metadata['upstream_wheel']
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != metadata['upstream_wheel_sha256']:
        raise RuntimeError('Bundled upstream wheel hash mismatch')
    npm = npm_script(node)
    version = subprocess.check_output([node, '--version'], text=True, timeout=10).strip()
    match = re.fullmatch(r'v(\d+)\.\d+\.\d+', version)
    if not match or int(match[1]) < 24:
        raise RuntimeError('mcporter 0.12.4 requires Node.js 24 or newer')
    # Never move a venv after creation: POSIX shebangs contain its original path.
    release = root / 'releases' / ('0.2.0-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    release.mkdir(parents=True, mode=0o700)
    runtime = release / 'runtime'
    venv.EnvBuilder(with_pip=True).create(runtime)
    python = runtime / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    run([python, '-m', 'pip', 'install', '--only-binary=cryptography', '-r', SOURCE / 'requirements.lock.txt', wheel, str(SOURCE) + '[social]'])
    node_tools = release / 'node-tools'
    node_tools.mkdir()
    for name in ('package.json', 'package-lock.json'):
        shutil.copy2(SOURCE / 'node-tools' / name, node_tools / name)
    env = dict(os.environ, PATH=str(Path(node).parent) + os.pathsep + os.environ.get('PATH', ''), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    run([node, npm, 'ci', '--prefix', node_tools, '--omit=dev', '--ignore-scripts', '--no-audit', '--no-fund'], env=env)
    # npm install hooks are disabled: adapters and daemon activation remain explicit.
    bindings = {'node': node}
    if gh:
        bindings['gh'] = gh
    (release / 'bindings.json').write_text(json.dumps(bindings, indent=2), encoding='utf-8')
    for name in ('launcher.py', 'diagnose.py', 'rollback.py'):
        shutil.copy2(SOURCE / name, release / name)
    shutil.copytree(SOURCE / 'skill', release / 'skill')
    run([python, '-m', 'pip', 'check'])
    run([python, release / 'diagnose.py', '--root', release, '--inside', '--quick'], env=env, timeout=60)
    # Existing MCP config/runtime are untouched until all staging checks pass.
    run([python, '-m', 'agent_reach_plus.deployment', '--root', root, '--release', release, '--config', config, '--skill', skill], env=env, timeout=30)
    for name in ('diagnose.py', 'rollback.py'):
        shutil.copy2(SOURCE / name, root / name)
    print('Installed:', root)
    print('Reload MCP connections. Login and Chrome extension state are local to this computer.')


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    if not (3, 12) <= sys.version_info[:2] < (3, 14):
        raise RuntimeError('Use Python 3.12 (recommended) or 3.13')
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=home / '.agent-reach/tools/agent-reach-plus')
    parser.add_argument('--config', type=Path, default=Path(os.environ.get('CODEX_HOME', str(home / '.codex'))) / 'config.toml')
    parser.add_argument('--skill', type=Path, default=home / '.agents/skills/agent-reach')
    parser.add_argument('--node', help='Absolute Node executable, useful for desktop/Homebrew PATH')
    parser.add_argument('--gh', help='Optional absolute GitHub CLI executable')
    args = parser.parse_args()
    node = executable('node', args.node)
    if not node:
        raise RuntimeError('Install Node.js 24 with npm, then rerun')
    install(args.root.expanduser().absolute(), args.config.expanduser().absolute(), args.skill.expanduser().absolute(), node, executable('gh', args.gh))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f'Installation stopped: {type(error).__name__}: {error}', file=sys.stderr)
        raise SystemExit(1) from None

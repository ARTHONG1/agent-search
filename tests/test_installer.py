import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


def installer():
    path = Path(__file__).resolve().parents[1] / 'install.py'
    spec = importlib.util.spec_from_file_location('portable_installer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_brew_npm_layout_uses_node_script(tmp_path):
    module = installer()
    prefix = tmp_path / 'homebrew/opt/node@24'
    (prefix / 'bin').mkdir(parents=True)
    node = prefix / 'bin/node'
    node.touch()
    npm = prefix / 'lib/node_modules/npm/bin/npm-cli.js'
    npm.parent.mkdir(parents=True)
    npm.touch()
    with patch('shutil.which', return_value=None):
        assert module.npm_script(str(node)) == npm


def test_bad_bundle_does_not_mutate_active_install(tmp_path):
    module = installer()
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'upstream.whl').write_bytes(b'changed-package')
    (source / 'manifest.json').write_text(json.dumps({'upstream_wheel': 'upstream.whl', 'upstream_wheel_sha256': '0' * 64}))
    root = tmp_path / 'active'
    root.mkdir()
    (root / 'manifest.json').write_text('existing-runtime')
    config = tmp_path / 'config.toml'
    config.write_text('existing-config')
    with patch.object(module, 'SOURCE', source):
        with pytest.raises(RuntimeError, match='hash mismatch'):
            module.install(root, config, tmp_path / 'skill', 'unused', None)
    assert config.read_text() == 'existing-config'
    assert (root / 'manifest.json').read_text() == 'existing-runtime'
    assert not (root / 'releases').exists()


def test_install_root_uses_physical_path_for_npm_prefix(tmp_path):
    module = installer()
    physical = tmp_path / 'physical'
    physical.mkdir()
    alias = tmp_path / 'alias'
    if os.name == 'nt':
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(alias), str(physical)], check=True, capture_output=True)
    else:
        alias.symlink_to(physical, target_is_directory=True)
    selected = []
    # Avoid package downloads while observing the path used by the real CLI.
    def install(root, config, skill, node, gh):
        selected.append(root)
        root.mkdir(parents=True)
        (root / 'marker.txt').write_text('staged')
    with patch.object(sys, 'argv', ['install.py', '--root', str(alias / 'new'), '--node', sys.executable]), patch.object(module, 'install', side_effect=install):
        module.main()
    assert selected == [physical.resolve() / 'new']
    assert (physical / 'new/marker.txt').read_text() == 'staged'

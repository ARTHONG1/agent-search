"""Run pinned upstream Gitleaks with SHA-256 verification and redacted output."""
import hashlib
import io
import platform
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = '8.30.1'
ASSETS = {
    ('Linux', 'x86_64'): ('linux_x64.tar.gz', '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'),
    ('Windows', 'AMD64'): ('windows_x64.zip', 'd29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e'),
    ('Darwin', 'arm64'): ('darwin_arm64.tar.gz', 'b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5'),
    ('Darwin', 'x86_64'): ('darwin_x64.tar.gz', 'dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709'),
}


def main():
    repo = Path(__file__).resolve().parents[1]
    suffix, digest = ASSETS[(platform.system(), platform.machine())]
    filename = f'gitleaks_{VERSION}_{suffix}'
    url = f'https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/{filename}'
    with urllib.request.urlopen(url, timeout=60) as response:
        content = response.read(32 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != digest:
        raise SystemExit('Gitleaks download hash mismatch')
    binary_name = 'gitleaks.exe' if platform.system() == 'Windows' else 'gitleaks'
    if filename.endswith('.zip'):
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            binary = archive.read(binary_name)
    else:
        with tarfile.open(fileobj=io.BytesIO(content), mode='r:gz') as archive:
            binary = archive.extractfile(binary_name).read()
    with tempfile.TemporaryDirectory(prefix='agent-search-gitleaks-') as directory:
        executable = Path(directory) / binary_name
        executable.write_bytes(binary)
        executable.chmod(0o700)
        subprocess.run([str(executable), 'dir', str(repo), '--redact=100', '--max-archive-depth=2', '--no-banner'], check=True, timeout=120)


if __name__ == '__main__':
    main()

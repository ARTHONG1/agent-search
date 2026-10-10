"""Local MCP handshake and optional live public-source checks; no account copies."""
from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path


async def check(root: Path, live: bool, quick: bool):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = dict(os.environ, AGENT_REACH_PLUS_HOME=str(root), PYTHONUTF8='1', PYTHONIOENCODING='utf-8')
    report = {'os': platform.system(), 'architecture': platform.machine(), 'python': platform.python_version(), 'cryptography': importlib.metadata.version('cryptography'), 'checks': []}
    failed = False
    async with stdio_client(StdioServerParameters(command=sys.executable, args=[str(root / 'launcher.py')], env=env)) as (read, write):
        async with ClientSession(read, write) as client:
            async with asyncio.timeout(40):
                await client.initialize()
                tools = {tool.name for tool in (await client.list_tools()).tools}
                expected = {'get_status', 'agent_reach_web_search', 'agent_reach_code_search', 'agent_reach_fetch_url', 'agent_reach_youtube_subtitles', 'agent_reach_rss_read', 'agent_reach_social_search', 'agent_reach_social_read', 'agent_reach_v2ex_topics'}
                failed |= tools != expected
                report['tools'] = sorted(tools)
                report['checks'].append({'case': 'mcp_tools', 'passed': tools == expected})
                result = await client.call_tool('agent_reach_fetch_url', {'url': 'http://127.0.0.1/'})
                payload = json.loads(result.content[0].text)
                safe = payload.get('ok') is False and payload.get('error', {}).get('code') == 'invalid_url'
                failed |= not safe
                report['checks'].append({'case': 'reject_private_url', 'passed': safe})
            if not quick:
                result = await client.call_tool('get_status', {})
                payload = json.loads(result.content[0].text)
                report['checks'].append({'case': 'configuration_diagnosis', 'passed': payload.get('ok') is True, 'backends': payload.get('data', {}).get('backends', {})})
                failed |= payload.get('ok') is not True
            if live:
                for label, name, args in [('web_read', 'agent_reach_fetch_url', {'url': 'https://example.com/'}), ('web_search', 'agent_reach_web_search', {'query': 'Python official documentation', 'limit': 2}), ('rss', 'agent_reach_rss_read', {'url': 'https://hnrss.org/frontpage', 'limit': 2})]:
                    result = await client.call_tool(name, args)
                    payload = json.loads(result.content[0].text)
                    passed = payload.get('ok') is True
                    failed |= not passed
                    report['checks'].append({'case': label, 'passed': passed, 'error_code': payload.get('error', {}).get('code')})
    report['passed'] = not failed
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    root = args.root.expanduser().absolute()
    manifest_path = root / 'manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('restored'):
            raise SystemExit('Agent-Reach registration was restored. Run install.py to register again.')
        if manifest.get('schema') == 2:
            root = Path(manifest['release'])
    if args.inside:
        return asyncio.run(check(root, args.live, args.quick))
    python = root / ('runtime/Scripts/python.exe' if sys.platform == 'win32' else 'runtime/bin/python')
    if not python.is_file():
        raise SystemExit('Installed runtime unavailable. Run install.py on this computer first.')
    command = [str(python), str(root / 'diagnose.py'), '--inside', '--root', str(root)]
    if args.live:
        command.append('--live')
    if args.quick:
        command.append('--quick')
    return subprocess.run(command, timeout=240).returncode


if __name__ == '__main__':
    raise SystemExit(main())

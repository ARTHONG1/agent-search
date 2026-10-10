import asyncio

from agent_reach_plus.server import execute


def test_all_platform_failures_not_reported_as_success():
    async def result():
        return {"results": [], "errors": [{"platform": "reddit", "code": "setup_required", "message": "Login required"}]}
    data = asyncio.run(execute(result()))
    assert data["ok"] is False
    assert data["error"]["code"] == "all_platforms_failed"


def test_partial_platform_results_marked_partial():
    async def result():
        return {"results": [{"platform": "github", "data": []}], "errors": [{"platform": "reddit", "code": "setup_required"}]}
    data = asyncio.run(execute(result()))
    assert data["ok"] is True
    assert data["partial"] is True

import pytest

from praetor_api.services import mcp_client


class FakeResponse:
    def __init__(self, payload: dict, headers: dict[str, str] | None = None):
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class FakeAsyncClient:
    calls: list[dict] = []

    def __init__(self, timeout: int):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url: str, headers: dict | None = None, json: dict | None = None):
        headers = headers or {}
        payload = json or {}
        method = payload.get("method")
        self.calls.append({"url": url, "headers": headers, "json": payload})
        if method == "initialize":
            assert headers["Mcp-Method"] == "initialize"
            assert headers["Authorization"] in {"Bearer test-token", "Bearer oauth-token"}
            return FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {
                            "tools": {"listChanged": False},
                            "resources": {"listChanged": False},
                            "prompts": {"listChanged": False},
                        },
                        "serverInfo": {"name": "fake-mcp", "version": "1"},
                    },
                },
                {"MCP-Session-Id": "sess-test"},
            )
        assert headers["MCP-Session-Id"] == "sess-test"
        assert headers["MCP-Protocol-Version"] == "2025-06-18"
        assert headers["Mcp-Method"] == method
        if method == "tools/list":
            return FakeResponse({"jsonrpc": "2.0", "id": payload["id"], "result": {"tools": [{"name": "open_pr"}]}})
        if method == "resources/list":
            return FakeResponse({"jsonrpc": "2.0", "id": payload["id"], "result": {"resources": [{"uri": "stub://repo"}]}})
        if method == "prompts/list":
            return FakeResponse({"jsonrpc": "2.0", "id": payload["id"], "result": {"prompts": [{"name": "review"}]}})
        if method == "tools/call":
            assert headers["Mcp-Name"] == "open_pr"
            return FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "content": [{"type": "text", "text": '{"url":"https://example.test/pr/1"}'}],
                        "isError": False,
                    },
                }
            )
        return FakeResponse({"jsonrpc": "2.0", "id": payload["id"], "error": {"code": -32601}})


class FakeOAuthClient:
    calls: list[dict] = []

    def __init__(self, timeout: int):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, url: str):
        self.calls.append({"method": "GET", "url": url})
        if url.endswith("/.well-known/oauth-protected-resource"):
            return FakeResponse({"authorization_servers": ["https://auth.example"]})
        if url == "https://auth.example/.well-known/oauth-authorization-server":
            return FakeResponse({"registration_endpoint": "https://auth.example/register"})
        raise AssertionError(url)

    async def post(self, url: str, headers: dict | None = None, json: dict | None = None):
        self.calls.append({"method": "POST", "url": url, "json": json})
        if url.endswith("/mcp"):
            return FakeResponse({"jsonrpc": "2.0", "id": (json or {})["id"], "error": {"code": 401}})
        if url == "https://auth.example/register":
            assert json["token_endpoint_auth_method"] == "none"
            assert "http://localhost:8000/oauth/mcp/callback" in json["redirect_uris"]
            return FakeResponse({"client_id": "praetor-client", "client_secret": "secret-value"})
        raise AssertionError(url)


@pytest.mark.asyncio
async def test_mcp_health_negotiates_session_and_lists_capabilities(monkeypatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setenv("MCP_TEST_TOKEN", "test-token")
    monkeypatch.setattr(mcp_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await mcp_client.health("http://mcp.example", "secret:mcp_test_token")

    assert result.ok is True
    assert result.outputs["mode"] == "mcp-streamable-http"
    assert result.outputs["protocol_version"] == "2025-06-18"
    assert result.outputs["tools_count"] == 1
    assert result.outputs["resources_count"] == 1
    assert result.outputs["prompts_count"] == 1


@pytest.mark.asyncio
async def test_mcp_call_sends_session_and_method_name_headers(monkeypatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setenv("MCP_TEST_TOKEN", "test-token")
    monkeypatch.setattr(mcp_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await mcp_client.call("http://mcp.example", "open_pr", {"branch": "praetor"}, True, "secret:mcp_test_token")

    assert result.ok is True
    assert result.outputs["url"] == "https://example.test/pr/1"
    assert result.outputs["_mcp"]["session_id"] == "sess...test"


@pytest.mark.asyncio
async def test_mcp_call_prefers_oauth_token_over_auth_ref(monkeypatch) -> None:
    FakeAsyncClient.calls = []
    monkeypatch.setenv("MCP_TEST_TOKEN", "static-token")
    monkeypatch.setattr(mcp_client.httpx, "AsyncClient", FakeAsyncClient)

    result = await mcp_client.call(
        "http://mcp.example",
        "open_pr",
        {"branch": "praetor"},
        True,
        "secret:mcp_test_token",
        oauth_token="oauth-token",
    )

    assert result.ok is True
    assert FakeAsyncClient.calls[0]["headers"]["Authorization"] == "Bearer oauth-token"


@pytest.mark.asyncio
async def test_mcp_health_discovers_and_registers_oauth_client(monkeypatch) -> None:
    FakeOAuthClient.calls = []
    monkeypatch.setattr(mcp_client.httpx, "AsyncClient", FakeOAuthClient)

    result = await mcp_client.health("https://mcp.example/mcp")

    assert result.ok is True
    assert result.outputs["mode"] == "mcp-oauth-registration"
    assert result.outputs["oauth"]["client"]["client_id"] == "praetor-client"
    assert result.outputs["oauth"]["client"]["client_secret"] == "[redacted]"
    assert any(call["url"] == "https://auth.example/register" for call in FakeOAuthClient.calls)

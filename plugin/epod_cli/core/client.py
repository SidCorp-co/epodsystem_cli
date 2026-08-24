"""The MCP transport. Knows epod's protocol and nothing about any use case.

Every write path in every pack lands here, so this is the one place UTF-8 is
guaranteed: the body is always json.dumps(..., ensure_ascii=False).encode("utf-8")
with charset=utf-8 declared, which is what keeps Vietnamese intact end to end.
"""
import json
import os

import requests

from . import auth

MCP_URL = os.environ.get("EPOD_MCP_URL", "https://mcp.epodsystem.com/mcp")


class Epod:
    def __init__(self):
        self.token = auth.load_token()
        self.sid = None
        self._id = 0
        self._init()

    def _headers(self):
        h = {"Authorization": f"Bearer {self.token}",
             "Content-Type": "application/json; charset=utf-8",
             "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        return h

    def _post(self, payload):
        # UTF-8 bytes, never str — a str body is latin-1 encoded by the layer below.
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        r = requests.post(MCP_URL, headers=self._headers(), data=data, timeout=90)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r

    def _rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        r = self._post(payload)
        out = None
        for line in r.text.splitlines():
            if line.startswith("data:"):
                out = json.loads(line[5:].strip())
        if not self.sid:
            self.sid = r.headers.get("mcp-session-id")
        return out

    def _init(self):
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "epod-cli", "version": "2"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tools(self):
        """Every tool the server exposes — the surface a new pack is built from."""
        res = self._rpc("tools/list", {})
        return ((res or {}).get("result") or {}).get("tools") or []

    def tool(self, name, args):
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        if not res or "result" not in res:
            raise SystemExit(f"tool {name} failed: {json.dumps(res, ensure_ascii=False)[:400]}")
        txt = "".join(p.get("text", "") for p in res["result"].get("content", [])
                      if p.get("type") == "text")
        try:
            return json.loads(txt)
        except ValueError:
            return txt

    # --- graphql ---
    def query(self, gql, variables=None):
        args = {"query": gql}
        if variables is not None:
            args["variables"] = variables
        return self.tool("graphql_query", args)

    def mutation(self, gql, variables=None):
        args = {"query": gql}
        if variables is not None:
            args["variables"] = variables
        return self.tool("graphql_mutation", args)

    def clear_cache(self):
        return self.tool("clear_storefront_cache", {})

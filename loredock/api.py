"""Minimal localhost-only AnythingLLM client, without proxy or redirect leakage."""

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import JSONObject


class APIError(RuntimeError):
    """An unavailable, malformed, or unsuccessful upstream operation."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, request: Any, fp: Any, code: int, message: str, headers: Any, new_url: str
    ) -> None:
        return None


class Client:
    """Adapter for the localhost AnythingLLM API, with redacted errors."""

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 180) -> None:
        url = urllib.parse.urlsplit(base_url)
        if (
            url.scheme != "http"
            or url.hostname not in ("127.0.0.1", "localhost", "::1")
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError(
                "Use a localhost HTTP origin, such as http://127.0.0.1:3001."
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )

    def request(
        self,
        method: str,
        path: str,
        body: JSONObject | None = None,
        auth: bool = True,
        expect_json: bool = True,
    ) -> JSONObject:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("API paths must be absolute paths on the local service.")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if auth:
            if not self.api_key:
                raise APIError(
                    "No application key. Run `python3 -m loredock configure` first."
                )
            headers["Authorization"] = "Bearer " + self.api_key
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
                result = json.loads(payload) if payload and expect_json else {}
        except urllib.error.HTTPError as error:
            raise APIError(
                f"{method} {path}: HTTP {error.code}. Check the local service and credentials."
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise APIError(
                f"Local service unavailable for {method} {path}: {type(error).__name__}"
            ) from None
        except json.JSONDecodeError:
            raise APIError(f"{method} {path} returned invalid JSON.") from None
        if isinstance(result, dict) and (
            result.get("success") is False or result.get("error")
        ):
            # Do not echo arbitrary server content or potentially private documents to logs.
            raise APIError(
                f"{method} {path} reported an application error. Inspect private service logs."
            )
        if not isinstance(result, dict):
            raise APIError(f"{method} {path} returned an unexpected JSON shape.")
        return result

    def get(self, path: str) -> JSONObject:
        return self.request("GET", "/api/v1" + path)

    def post(self, path: str, body: JSONObject) -> JSONObject:
        return self.request("POST", "/api/v1" + path, body)

    def workspace(self, slug: str) -> JSONObject:
        result = self.get("/workspace/" + urllib.parse.quote(slug, safe=""))
        workspace = result.get("workspace")
        if isinstance(workspace, list):
            workspace = workspace[0] if workspace else None
        if not isinstance(workspace, dict) or not workspace:
            raise APIError("Workspace not found: " + slug)
        return workspace

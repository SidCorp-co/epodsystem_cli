"""OpenAI-compatible chat client over urllib. No third-party dependencies."""

import json
import time
import urllib.error
import urllib.request

from .util import CliError

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}
# Cloudflare in front of the gateway rejects the default urllib agent with 1010.
USER_AGENT = "epod-vi/2.1"


class Client:
    def __init__(self, config, timeout=180, retries=3, verbose=False):
        self.config = config
        self.timeout = timeout
        self.retries = retries
        self.verbose = verbose
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0

    def _request(self, path, payload):
        url = self.config.base_url + path
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("Authorization", "Bearer " + self.config.api_key)
        request.add_header("Content-Type", "application/json")
        request.add_header("User-Agent", USER_AGENT)
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def chat(self, system, user, temperature=0.3, max_tokens=None, json_mode=True):
        """One completion. Returns the assistant text with reasoning stripped out."""
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens

        last = None
        for attempt in range(self.retries):
            try:
                data = self._request("/chat/completions", payload)
                return self._extract(data)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:400]
                last = CliError("gateway returned %s: %s" % (exc.code, detail))
                if exc.code not in RETRY_STATUS:
                    raise last
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last = CliError("gateway request failed: %s" % exc)
            if attempt < self.retries - 1:
                time.sleep(2 ** attempt)
        raise last

    def _extract(self, data):
        """`content` only.

        The gateway also returns `reasoning_content` — the model thinking out loud,
        in English. Concatenating it would ship chain-of-thought into a locale file.
        """
        choices = data.get("choices") or []
        if not choices:
            raise CliError("gateway returned no choices: %s" % json.dumps(data)[:300])
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content or not content.strip():
            reason = choices[0].get("finish_reason")
            raise CliError("model returned empty content (finish_reason=%s)" % reason)
        usage = data.get("usage") or {}
        self.calls += 1
        self.prompt_tokens += usage.get("prompt_tokens") or 0
        self.completion_tokens += usage.get("completion_tokens") or 0
        return content

    def models(self):
        url = self.config.base_url + "/models"
        request = urllib.request.Request(url)
        request.add_header("Authorization", "Bearer " + self.config.api_key)
        request.add_header("User-Agent", USER_AGENT)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8")).get("data", [])
        except urllib.error.HTTPError as exc:
            raise CliError("gateway returned %s listing models" % exc.code)
        except urllib.error.URLError as exc:
            raise CliError("cannot reach %s: %s" % (url, exc))

    def usage_note(self):
        return "%d call(s), %d in / %d out tokens" % (
            self.calls, self.prompt_tokens, self.completion_tokens
        )

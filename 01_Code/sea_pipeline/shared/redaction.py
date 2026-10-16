"""Keep environment credentials and signed URL credentials out of reports/logs."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import parse_qsl, quote, quote_plus, urlsplit


_SECRET_NAME = re.compile(r"TOKEN|PASSWORD|SECRET|API_KEY|SAS_URL|CONNECTION_STRING", re.I)
_SIGNED_QUERY = re.compile(
    r"([?&](?:amp;)?(?:sig|signature|x-amz-signature|x-amz-credential|x-amz-security-token|awsaccesskeyid)=)[^\s\"'<>\\&]+",
    re.I,
)


class SecretRedactor:
    def __init__(self, extra_values=()):
        values = [value for key, value in os.environ.items() if _SECRET_NAME.search(key)]
        values.extend(value for value in extra_values if value)
        self.values = set()
        for value in values:
            if len(value) < 4:
                continue
            self.values.update((value, quote(value, safe=""), quote_plus(value),
                                json.dumps(value)[1:-1], repr(value)[1:-1]))
            if value.startswith(("https://", "http://")):
                for key, token in parse_qsl(urlsplit(value).query):
                    if key.lower() in {"sig", "signature", "x-amz-signature", "x-amz-security-token"}:
                        self.values.update((token, quote(token, safe=""), quote_plus(token)))
        self.values = sorted(self.values, key=len, reverse=True)
        self.pending = {}

    def text(self, value: str) -> str:
        for secret in self.values:
            value = value.replace(secret, "[REDACTED]")
        return _SIGNED_QUERY.sub(r"\1[REDACTED]", value)

    def stream(self, channel: str, value: str, *, final: bool = False) -> str:
        # A Jupyter stream can split a token across messages. Emit complete lines.
        buffered = self.pending.get(channel, "") + value
        end = len(buffered) if final else buffered.rfind("\n") + 1
        self.pending[channel] = buffered[end:]
        return self.text(buffered[:end])

    def data(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {key: self.data(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.data(item) for item in value]
        return value


def redact_text(value: str, extra_values=()) -> str:
    return SecretRedactor(extra_values).text(value)

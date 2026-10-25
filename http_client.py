from typing import Protocol, runtime_checkable

from curl_cffi import requests as cffiRequests


@runtime_checkable
class HttpClient(Protocol):
    """Abstraction over the HTTP layer.

    Consumers depend on this protocol instead of a concrete client
    (dependency inversion), so the transport can be swapped freely.
    """

    def get(self, url: str, params: dict = None, headers: dict = None) -> str:
        ...


class CurlCffiHttpClient:
    """HTTP client that impersonates Chrome's TLS fingerprint.

    Plain ``requests`` is challenged (403) by Cloudflare because of its TLS
    fingerprint, while curl/browser fingerprints pass. curl_cffi reproduces a
    browser fingerprint from Python.
    """

    def __init__(self, impersonate: str = "chrome", timeout: int = 30):
        self.impersonate = impersonate
        self.timeout = timeout

    def get(self, url: str, params: dict = None, headers: dict = None) -> str:
        response = cffiRequests.get(
            url, params=params, headers=headers, impersonate=self.impersonate, timeout=self.timeout
        )
        response.raise_for_status()
        return response.text

"""Block non-public destinations for server-side URL fetches (SSRF hardening)."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
        "kubernetes.default",
        "kubernetes.default.svc",
    }
)

_BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".corp")

MAX_REDIRECTS = 5


class UnsafeUrlError(ValueError):
    """URL targets a non-public or otherwise disallowed destination."""


@dataclass(frozen=True)
class SafeHttpDestination:
    """Validated public HTTP(S) target with a DNS-pinned connect address."""

    scheme: str
    hostname: str
    pinned_ip: str
    port: int | None
    path: str
    params: str
    query: str

    def connect_url(self) -> str:
        """URL whose host is the pinned IP (for the TCP/TLS connect)."""
        if ":" in self.pinned_ip and not self.pinned_ip.startswith("["):
            host = f"[{self.pinned_ip}]"
        else:
            host = self.pinned_ip
        if self.port is not None:
            netloc = f"{host}:{self.port}"
        else:
            netloc = host
        return urlunparse((self.scheme, netloc, self.path, self.params, self.query, ""))

    def host_header(self) -> str:
        """Host header / SNI name for the original hostname."""
        if self.port is None:
            return self.hostname
        default = 443 if self.scheme == "https" else 80
        if self.port == default:
            return self.hostname
        return f"{self.hostname}:{self.port}"


def assert_safe_http_url(url: str) -> None:
    """Raise UnsafeUrlError unless url is http(s) to a public destination."""
    validate_http_destination(url)


def validate_http_destination(url: str) -> SafeHttpDestination:
    """Validate url and return a destination pinned to one resolved public IP."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError("URL must use http or https")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("URL must not contain credentials")

    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise UnsafeUrlError("URL host is missing")
    if host in _BLOCKED_HOSTNAMES or host.endswith(_BLOCKED_SUFFIXES):
        raise UnsafeUrlError("URL host is not allowed")

    pinned_ip = resolve_public_ip(host)
    path = parsed.path or "/"
    return SafeHttpDestination(
        scheme=parsed.scheme,
        hostname=host,
        pinned_ip=pinned_ip,
        port=parsed.port,
        path=path,
        params=parsed.params,
        query=parsed.query,
    )


def resolve_public_ip(hostname: str) -> str:
    """Resolve hostname (or accept an IP literal) and return one public address string.

    Raises if any resolved address is non-public (blocks dual-homed rebinding hosts).
    """
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        return _resolve_hostname_public_ip(hostname)

    if not _is_public_ip(literal):
        raise UnsafeUrlError("URL host is not a public address")
    return str(literal)


def _resolve_hostname_public_ip(hostname: str) -> str:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError("Unable to resolve URL host") from exc

    if not infos:
        raise UnsafeUrlError("Unable to resolve URL host")

    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    seen: set[str] = set()
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        ip = ipaddress.ip_address(sockaddr[0])
        key = str(ip)
        if key in seen:
            continue
        seen.add(key)
        addresses.append(ip)

    if not addresses:
        raise UnsafeUrlError("Unable to resolve URL host")
    if any(not _is_public_ip(ip) for ip in addresses):
        raise UnsafeUrlError("URL host resolves to a non-public address")
    return str(addresses[0])


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.version == 6 and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_global)

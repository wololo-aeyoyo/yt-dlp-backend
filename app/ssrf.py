"""SSRF guard: reject non-public URL targets before yt-dlp touches them."""
import ipaddress
import socket
from urllib.parse import urlparse


def _is_blocked_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return (
        addr.is_private        # 10/8, 172.16/12, 192.168/16, fd00::/8
        or addr.is_loopback    # 127/8, ::1
        or addr.is_link_local  # 169.254/16 — incl. cloud metadata 169.254.169.254
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified  # 0.0.0.0
    )


def validate_url(url: str) -> None:
    """Raise ValueError unless url is an http(s) URL resolving to a public address."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError("Could not resolve host")
    # Block if ANY resolved address is non-public (defeats split-horizon tricks).
    for info in infos:
        if _is_blocked_ip(info[4][0]):
            raise ValueError("URL resolves to a non-public address")
    # ponytail: input-host check only. yt-dlp follows redirects / does its own DNS,
    # so DNS-rebinding and redirect-to-internal still need an egress firewall on the
    # container. Upgrade path: pin DNS + block egress to RFC1918/link-local at infra.


if __name__ == "__main__":
    def _blocked(u):
        try:
            validate_url(u); return False
        except ValueError:
            return True

    assert _blocked("file:///etc/passwd")
    assert _blocked("ftp://example.com/x")
    assert _blocked("http://169.254.169.254/latest/meta-data/")
    assert _blocked("http://127.0.0.1:8000/")
    assert _blocked("http://localhost/")
    assert _blocked("http://[::1]/")
    assert _blocked("http://10.0.0.5/")
    assert _blocked("http://0.0.0.0/")
    assert _blocked("not-a-url")
    assert not _blocked("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    print("ssrf guard ok")

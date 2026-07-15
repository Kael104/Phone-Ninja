"""Generate / load a local self-signed TLS certificate for HTTPS + WSS."""

from __future__ import annotations

import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


DEFAULT_CERT_DIR = Path(__file__).resolve().parent / "certs"
CERT_FILE = DEFAULT_CERT_DIR / "cert.pem"
KEY_FILE = DEFAULT_CERT_DIR / "key.pem"


def _lan_ips() -> list[str]:
    ips: list[str] = ["127.0.0.1"]
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except OSError:
        pass
    # Also try UDP trick for primary outbound interface
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        if ip not in ips:
            ips.insert(0, ip)
    except OSError:
        pass
    return ips


def ensure_self_signed_cert(
    cert_path: Path = CERT_FILE,
    key_path: Path = KEY_FILE,
    common_name: str = "Phone Ninja Local",
) -> tuple[Path, Path]:
    """Create cert/key if missing. Includes LAN IPs as SANs for Android Chrome."""
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Phone Ninja"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    san_list: list[x509.GeneralName] = [
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    for ip in _lan_ips():
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            continue

    # Deduplicate
    seen: set[str] = set()
    unique_sans: list[x509.GeneralName] = []
    for name in san_list:
        key_s = str(name)
        if key_s not in seen:
            seen.add(key_s)
            unique_sans.append(name)

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(unique_sans), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path


def get_primary_lan_ip() -> str:
    ips = _lan_ips()
    for ip in ips:
        if not ip.startswith("127."):
            return ip
    return ips[0] if ips else "127.0.0.1"

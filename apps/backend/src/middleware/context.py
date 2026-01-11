from dataclasses import dataclass

from fastapi import Request
from ua_parser import user_agent_parser

from src.core.security import hash_fingerprint


@dataclass
class RequestContext:
    fingerprint_raw: str | None
    fingerprint_hash: str | None
    ip_address: str
    user_agent: str | None
    login_flow_id: str | None
    # Soft binding metadata
    os_family: str | None
    ua_family: str | None
    asn: str | None
    country_code: str | None


def _extract_client_ip(request: Request) -> str:
    """
    Extracts the real client IP from request headers;
    Cloud Run appends the real client IP as the RIGHTMOST value in X-Forwarded-For
    """
    forwarded_for = request.headers.get("X-Forwarded-For", "")

    if forwarded_for:
        ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
        if ips:
            return ips[-1]

    if request.client and request.client.host:
        return request.client.host

    return "0.0.0.0"


def _parse_user_agent(ua_string: str | None) -> tuple[str | None, str | None]:
    """Returns (os_family, ua_family) from User-Agent string"""
    if not ua_string:
        return None, None

    try:
        parsed = user_agent_parser.Parse(ua_string)
        os_family = parsed.get("os", {}).get("family")
        ua_family = parsed.get("user_agent", {}).get("family")
        return os_family, ua_family
    except Exception:
        return None, None


def _extract_gcp_metadata(request: Request) -> tuple[str | None, str | None]:
    """
    Returns (asn, country_code) from GCP-injected headers;
    supports Cloud Armor and App Engine header formats
    """
    country = (
        request.headers.get("X-AppEngine-Country") or
        request.headers.get("X-GCP-Country") or
        request.headers.get("CF-IPCountry")
    )
    asn = request.headers.get("X-GCP-ASN")

    # Normalize country code to uppercase 2-letter
    if country:
        country = country.upper()[:2]

    return asn, country


async def get_request_context(request: Request) -> RequestContext:
    """Extracts and validates request context for auth flows"""
    fingerprint_raw = request.headers.get("X-Device-Fingerprint")
    fingerprint_hash = None
    if fingerprint_raw:
        fingerprint_hash = hash_fingerprint(fingerprint_raw)

    ip_address = _extract_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    login_flow_id = request.cookies.get("login_flow_id")

    os_family, ua_family = _parse_user_agent(user_agent)
    asn, country_code = _extract_gcp_metadata(request)

    return RequestContext(
        fingerprint_raw=fingerprint_raw,
        fingerprint_hash=fingerprint_hash,
        ip_address=ip_address,
        user_agent=user_agent,
        login_flow_id=login_flow_id,
        os_family=os_family,
        ua_family=ua_family,
        asn=asn,
        country_code=country_code,
    )


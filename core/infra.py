"""Infrastructure & data-location mapper — owned by the security engine (Ahmad).

Answers: where is the server, which cloud/region, is a CDN hiding the origin,
who hosts email, where do third-party trackers send data, are SPF/DMARC set.
All lookups are public DNS / RDAP data.
"""
from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from pathlib import Path

import dns.resolver

CLOUD_DIR = Path(__file__).resolve().parent.parent / "data" / "cloud_ranges"

CDN_HEADER_HINTS = {
    "cf-ray": "Cloudflare", "x-amz-cf-id": "Amazon CloudFront", "x-served-by": "Fastly",
    "x-fastly-request-id": "Fastly", "x-akamai-transformed": "Akamai", "x-azure-ref": "Azure Front Door",
    "x-vercel-id": "Vercel", "x-nf-request-id": "Netlify",
}
ASN_PROVIDER_HINTS = {
    "AMAZON": "AWS", "MICROSOFT": "Azure", "GOOGLE": "Google Cloud", "CLOUDFLARE": "Cloudflare",
    "DIGITALOCEAN": "DigitalOcean", "HETZNER": "Hetzner", "OVH": "OVHcloud", "LINODE": "Akamai/Linode",
    "AKAMAI": "Akamai", "FASTLY": "Fastly", "ORACLE": "Oracle Cloud", "ALIBABA": "Alibaba Cloud",
    "ORANGE": "Orange Jordan", "ZAIN": "Zain Jordan", "UMNIAH": "Umniah", "DAMAMAX": "Damamax",
}
CDN_PROVIDERS = {"Cloudflare", "Akamai", "Fastly", "Amazon CloudFront", "Azure Front Door", "Vercel", "Netlify"}
MX_PROVIDERS = {"google.com": "Google Workspace", "googlemail.com": "Google Workspace",
                "outlook.com": "Microsoft 365", "protection.outlook.com": "Microsoft 365",
                "zoho": "Zoho Mail", "mailgun": "Mailgun", "secureserver.net": "GoDaddy"}


def _resolver() -> dns.resolver.Resolver:
    r = dns.resolver.Resolver()
    r.lifetime = 6
    return r


def dns_records(host: str) -> dict:
    r, out = _resolver(), {"A": [], "AAAA": [], "MX": [], "TXT": [], "DMARC": []}
    for rtype in ("A", "AAAA", "MX", "TXT"):
        try:
            out[rtype] = [a.to_text().strip('"') for a in r.resolve(host, rtype)]
        except Exception:  # noqa: BLE001 — NXDOMAIN / no answer is a normal result
            pass
    try:
        out["DMARC"] = [a.to_text().strip('"') for a in r.resolve(f"_dmarc.{host}", "TXT")]
    except Exception:  # noqa: BLE001
        pass
    out["SPF"] = [t for t in out["TXT"] if t.lower().startswith("v=spf1")]
    return out


@lru_cache(maxsize=256)
def ip_owner(ip: str) -> dict:
    """RDAP lookup: ASN, owner org and country of an IP."""
    try:
        from ipwhois import IPWhois
        d = IPWhois(ip, timeout=8).lookup_rdap(depth=0)
        desc = d.get("asn_description") or ""
        provider = next((v for k, v in ASN_PROVIDER_HINTS.items() if k in desc.upper()), None)
        return {"ip": ip, "asn": d.get("asn"), "asn_description": desc,
                "country": d.get("asn_country_code"), "provider": provider}
    except Exception as e:  # noqa: BLE001
        return {"ip": ip, "error": e.__class__.__name__}


@lru_cache(maxsize=1)
def _load_cloud_ranges() -> list[tuple]:
    """Loads AWS / GCP published IP ranges (run scripts/update_cloud_ranges.py once, with internet)."""
    nets = []
    aws = CLOUD_DIR / "aws.json"
    if aws.exists():
        for p in json.loads(aws.read_text())["prefixes"]:
            nets.append((ipaddress.ip_network(p["ip_prefix"]), "AWS", p["region"], p["service"]))
    gcp = CLOUD_DIR / "gcp.json"
    if gcp.exists():
        for p in json.loads(gcp.read_text())["prefixes"]:
            pref = p.get("ipv4Prefix") or p.get("ipv6Prefix")
            nets.append((ipaddress.ip_network(pref), "Google Cloud", p.get("scope"), p.get("service")))
    return nets


# Region code → country (enough for the regions people actually pick)
REGION_COUNTRY = {
    "eu-central-1": "DE", "eu-west-1": "IE", "eu-west-2": "GB", "eu-west-3": "FR", "eu-north-1": "SE",
    "eu-south-1": "IT", "me-south-1": "BH", "me-central-1": "AE", "il-central-1": "IL",
    "us-east-1": "US", "us-east-2": "US", "us-west-1": "US", "us-west-2": "US",
    "ap-south-1": "IN", "ap-southeast-1": "SG", "europe-west3": "DE", "europe-west1": "BE",
    "europe-west4": "NL", "me-central1": "QA", "me-west1": "IL", "us-central1": "US",
}


def cloud_region(ip: str) -> dict | None:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    best = None
    for net, provider, region, service in _load_cloud_ranges():
        if addr.version == net.version and addr in net and (best is None or net.prefixlen > best[0].prefixlen):
            best = (net, provider, region, service)
    if not best:
        return None
    return {"provider": best[1], "region": best[2], "service": best[3],
            "region_country": REGION_COUNTRY.get(best[2] or "")}


def detect_cdn(headers: dict, owners: list[dict]) -> str | None:
    h = {k.lower(): v for k, v in (headers or {}).items()}
    for key, name in CDN_HEADER_HINTS.items():
        if key in h:
            return name
    if "cloudflare" in (h.get("server") or "").lower():
        return "Cloudflare"
    for o in owners:
        if o.get("provider") in CDN_PROVIDERS:
            return o["provider"]
    return None


def mx_provider(mx: list[str]) -> str | None:
    for rec in mx:
        for k, v in MX_PROVIDERS.items():
            if k in rec.lower():
                return v
    return None


def tracker_locations(tracker_domains: list[str], limit: int = 6) -> list[dict]:
    out, r = [], _resolver()
    for dom in tracker_domains[:limit]:
        try:
            ip = r.resolve(dom, "A")[0].to_text()
            o = ip_owner(ip)
            out.append({"domain": dom, "ip": ip, "country": o.get("country"), "org": o.get("asn_description")})
        except Exception:  # noqa: BLE001
            out.append({"domain": dom, "country": None})
    return out


def map_infra(host: str, headers: dict | None = None, tracker_domains: list[str] | None = None) -> dict:
    recs = dns_records(host)
    owners = [ip_owner(ip) for ip in recs["A"][:3]]
    clouds = [c for c in (cloud_region(ip) for ip in recs["A"][:3]) if c]
    cdn = detect_cdn(headers or {}, owners)

    hosting_country, confidence = None, "low"
    if clouds and clouds[0].get("region_country"):
        hosting_country, confidence = clouds[0]["region_country"], "high"
    elif owners and owners[0].get("country") and not cdn:
        hosting_country, confidence = owners[0]["country"], "medium"

    return {
        "dns": recs,
        "ip_owners": owners,
        "cloud": clouds[0] if clouds else None,
        "cdn": cdn,
        "origin_hidden": bool(cdn),
        "hosting_country": hosting_country,       # None when a CDN hides the origin — ask the user
        "hosting_confidence": confidence,
        "mx_provider": mx_provider(recs["MX"]),
        "spf": recs["SPF"],
        "dmarc": recs["DMARC"],
        "tracker_locations": tracker_locations(tracker_domains or []),
    }


if __name__ == "__main__":
    import sys
    print(json.dumps(map_infra(sys.argv[1]), indent=2, default=str))

"""SHARED CONTRACT between the security engine (Ahmad) and the AI/UI half (teammate).
Announce in the team chat before changing anything here."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
Role = Literal["owner", "developer", "legal"]
Lang = Literal["ar", "en"]


class CompanyProfile(BaseModel):
    name: str
    domain: str
    sector: str = "other"                      # health, finance, telecom, energy, government, education, ecommerce, other
    is_critical_sector: bool = False           # one of the NCSC critical sectors
    is_government: bool = False
    data_types: list[str] = Field(default_factory=list)   # basic, health, financial, biometric, children, location
    user_countries: list[str] = Field(default_factory=lambda: ["JO"])  # ISO-2 codes
    hosting_country: str | None = None         # ISO-2; None = let the scanner detect it
    expanding_to_eu: bool = False
    employees: int = 10
    processing_is_core_activity: bool = False  # is handling personal data the main business?


class Finding(BaseModel):
    id: str                                    # e.g. "COOKIE_BEFORE_CONSENT"
    title: str
    title_ar: str = ""
    severity: Severity
    evidence: dict = Field(default_factory=dict)
    source: Literal["detected", "user_confirmed", "profile"] = "detected"
    jurisdictions: list[str] = Field(default_factory=list)   # ["JO", "EU"]
    refs: list[str] = Field(default_factory=list)            # ["PDPL:Art.12", "GDPR:Art.32", "ISO:A.8.24"]
    fix_effort: Literal["low", "medium", "high"] = "medium"


class Applicability(BaseModel):
    framework: str            # "PDPL", "NCSC", "GDPR", "ISO27001", "CYBERCRIME_LAW"
    applies: bool
    reason: str
    reason_ar: str = ""
    confidence: Literal["low", "medium", "high"] = "medium"


class ScanResult(BaseModel):
    target: str
    final_url: str | None = None
    https: dict = Field(default_factory=dict)
    headers: dict = Field(default_factory=dict)
    tls: dict = Field(default_factory=dict)
    cookies: list[dict] = Field(default_factory=list)
    third_party_scripts: list[str] = Field(default_factory=list)
    consent_banner: bool | None = None
    privacy_policy: dict = Field(default_factory=dict)
    forms: list[dict] = Field(default_factory=list)
    infra: dict = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class Report(BaseModel):
    profile: CompanyProfile
    applicability: list[Applicability]
    findings: list[Finding]
    engagement_id: str | None = None
    score: int = 100          # 0-100 compliance score

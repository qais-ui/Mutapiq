"""Demo-only legal-review types. Independent of the original security schema."""
from dataclasses import asdict, dataclass, field


@dataclass
class BusinessProfile:
    name: str = "Shifa Health"
    jurisdiction: str = "JO"
    sector: str = "health"
    has_employees: bool = True
    serves_consumers: bool = True
    eu_activity: str = "unknown"  # yes / no / unknown; Article 3 needs professional review


@dataclass
class LegalCheck:
    id: str
    category: str
    title: str
    title_ar: str
    law: str
    reference: str
    source_url: str
    requirement: str
    requirement_ar: str
    question: str
    question_ar: str
    action: str
    action_ar: str
    terms: tuple[str, ...] = ()
    applicability: str = "always"


@dataclass
class LegalFinding:
    check: LegalCheck
    status: str  # evidence_found / review_needed / needs_confirmation / self_reported / out_of_scope
    reason: str
    reason_ar: str
    evidence: str = ""
    evidence_url: str = ""
    note: str = ""


@dataclass
class LegalReport:
    profile: BusinessProfile
    findings: list[LegalFinding]
    documents: list[dict]
    created_at: str
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        statuses = ("evidence_found", "review_needed", "needs_confirmation", "self_reported", "out_of_scope")
        return {status: sum(f.status == status for f in self.findings) for status in statuses}

    def to_dict(self) -> dict:
        return asdict(self)

"""Fast offline tests for the law-first demo; no Ollama or client database access."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from legal_catalog import AREAS, CHECKS
from legal_models import BusinessProfile, LegalReport
from legal_review import _assess, _read_page, export_legal_report, update_review


class LegalReviewTests(unittest.TestCase):
    def report(self, **profile):
        return LegalReport(
            BusinessProfile(**profile), [],
            [{"kind": "privacy", "title": "Privacy", "url": "http://127.0.0.1:5001/privacy",
              "text": "We use your details for booking an appointment. We respect your privacy."}],
            datetime.now(timezone.utc).isoformat(),
        )

    def findings(self, report, answers=None):
        return {f.check.id: f for f in update_review(report, answers or {}).findings}

    def test_catalog_has_all_supported_areas_and_unique_ids(self):
        self.assertEqual(set(AREAS), {c.category for c in CHECKS})
        self.assertEqual(len(CHECKS), len({c.id for c in CHECKS}))
        self.assertGreater(len(CHECKS), 20)
        self.assertTrue(all(c.source_url.startswith("https://") for c in CHECKS))

    def test_disclosure_signal_is_not_a_compliance_pass(self):
        f = self.findings(self.report())["jo_notice"]
        self.assertEqual(f.status, "evidence_found")
        self.assertIn("booking", f.evidence)
        self.assertIn("not proof", f.reason)
        self.assertNotIn("passed", f.status)

    def test_missing_phrase_is_review_not_violation(self):
        f = self.findings(self.report())["jo_rights"]
        self.assertEqual(f.status, "review_needed")
        self.assertIn("before calling", f.reason)

    def test_internal_records_cannot_be_inferred(self):
        self.assertEqual(self.findings(self.report())["tax_records"].status, "needs_confirmation")
        self.assertEqual(self.findings(self.report())["company_records"].status, "needs_confirmation")

    def test_gdpr_is_conditional_until_profile_confirmed(self):
        unknown = self.findings(self.report())
        self.assertTrue(all(f.status == "needs_confirmation" for f in unknown.values() if f.check.category == "gdpr"))
        excluded = self.findings(self.report(eu_activity="no"))
        self.assertTrue(all(f.status == "out_of_scope" for f in excluded.values() if f.check.category == "gdpr"))
        included = self.findings(self.report(eu_activity="yes"))
        self.assertEqual(included["gdpr_notice"].status, "evidence_found")

    def test_business_profile_changes_scope(self):
        items = self.findings(self.report(has_employees=False, serves_consumers=False, sector="services"))
        for key in ("employment_terms", "social_security", "consumer_redress", "health_licensing", "aml_scope"):
            self.assertEqual(items[key].status, "out_of_scope")
        self.assertEqual(self.findings(self.report(sector="finance"))["aml_scope"].status, "needs_confirmation")

    def test_claims_require_notes_and_remain_unverified(self):
        report = self.report()
        no_note = self.findings(report, {"tax_records": {"answer": "in_place", "note": ""}})
        self.assertEqual(no_note["tax_records"].status, "needs_confirmation")
        claimed = self.findings(report, {"tax_records": {"answer": "in_place", "note": "Reviewed sample ledger."}})
        self.assertEqual(claimed["tax_records"].status, "self_reported")
        self.assertIn("unverified", claimed["tax_records"].reason)
        gap = self.findings(report, {"tax_records": {"answer": "gap", "note": "No sample ledger."}})
        self.assertEqual(gap["tax_records"].status, "review_needed")
        na = self.findings(report, {"tax_records": {"answer": "not_applicable", "note": "Accountant to check."}})
        self.assertEqual(na["tax_records"].status, "self_reported")

    def test_user_cannot_override_unconfirmed_gdpr_scope(self):
        f = self.findings(self.report(), {"gdpr_notice": {"answer": "in_place", "note": "We believe this is complete."}})
        self.assertEqual(f["gdpr_notice"].status, "needs_confirmation")

    def test_updates_are_pure_and_exports_contain_current_escaped_answers(self):
        report = self.report()
        updated = update_review(report, {"tax_records": {"answer": "in_place", "note": "<script>demo</script>"}})
        self.assertEqual(report.findings, [])
        exported = export_legal_report(updated)
        self.assertIn("&lt;script&gt;demo&lt;/script&gt;", exported)
        self.assertNotIn("<script>", exported)
        self.assertIn("Self-reported", exported)
        self.assertIn("not a legal opinion", exported)
        self.assertIn("lang='ar'", export_legal_report(updated, "ar"))
        self.assertEqual(sum(updated.counts().values()), len(CHECKS))

    def test_external_requests_and_redirects_are_blocked(self):
        with patch("legal_review.requests.get") as get:
            with self.assertRaises(ValueError):
                _read_page("https://example.com/privacy", "privacy")
            get.assert_not_called()
            get.return_value.is_redirect = True
            with self.assertRaises(RuntimeError):
                _read_page("http://127.0.0.1:5001/privacy", "privacy")
            self.assertFalse(get.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()

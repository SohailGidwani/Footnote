"""Checks that chat replies use the glossary and the read-only digest."""

import unittest
from unittest.mock import patch

from footnote import answer_text, load_pack


class AnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack()

    @patch("footnote.fetch_digest")
    def test_known_term_and_alias_include_owner(self, get_digest):
        for question in ("What does Bluebird mean at Halcyon?", "what is fleet control service?"):
            answer = answer_text(question, self.pack, "http://localhost:8000")
            self.assertIn("Owner:", answer)
        self.assertIn("Priya Raman (Autonomy)", answer_text("Bluebird?", self.pack, ""))
        self.assertIn("Marcus Lindqvist (Platform)", answer_text("what is FCS?", self.pack, ""))
        get_digest.assert_not_called()

    def test_unknown_term_is_not_invented(self):
        answer = answer_text("What does HAL-9 mean at Halcyon?", self.pack, "")
        self.assertIn("do not have HAL-9", answer)

    @patch("footnote.fetch_digest")
    def test_unknown_glossary_term_can_use_a_recent_meeting_definition(self, get_digest):
        get_digest.return_value = {"terms_learned": [{
            "term": "Cedar Point", "meaning": "Telemetry migration to a new cluster",
            "owner_name": "Dana Okafor", "owner_team": "Reliability", "source": "llm",
        }]}
        answer = answer_text("What does Cedar Point mean at Halcyon?", self.pack, "http://localhost:8000")
        self.assertIn("Cedar Point: Telemetry migration to a new cluster", answer)
        self.assertIn("Inferred", answer)
        self.assertIn("Suggested contact: Dana Okafor (Reliability)", answer)
        self.assertNotIn("Owner:", answer)
        get_digest.assert_called_once_with("http://localhost:8000")

    @patch("footnote.fetch_digest", return_value={"terms_learned": [{
        "term": "Red Line", "meaning": "Telemetry migration to a new cluster",
        "owner_name": "Marcus Lindqvist", "owner_team": "Platform", "source": "llm",
    }]})
    def test_different_names_are_not_treated_as_the_same_project(self, get_digest):
        answer = answer_text("What does Ridgeline mean at Halcyon?", self.pack, "http://localhost:8000")
        self.assertIn("do not have Ridgeline", answer)
        self.assertNotIn("Telemetry migration", answer)
        get_digest.assert_called_once()

    @patch("footnote.fetch_digest", side_effect=OSError("offline"))
    def test_unknown_term_lookup_reports_when_meeting_history_is_unavailable(self, get_digest):
        answer = answer_text("What does Pinecrest mean at Halcyon?", self.pack, "http://localhost:8000")
        self.assertIn("cannot check your recent meeting terms", answer)
        self.assertIn("Pinecrest", answer)

    @patch("footnote.fetch_digest")
    def test_platform_sync_prep_has_five_pack_terms_and_never_calls_backend(self, get_digest):
        answer = answer_text("Prep me for my 2pm platform sync", self.pack, "http://localhost:8000")
        self.assertEqual(answer.count("Owner:"), 5)
        for term in ("2pm platform sync", "FCS", "golden path", "Bluebird", "DRI"):
            self.assertIn(term + ":", answer)
        self.assertIn("Marcus Lindqvist (Platform)", answer)
        get_digest.assert_not_called()

    @patch("footnote.fetch_digest")
    def test_digest_questions_are_read_only(self, get_digest):
        get_digest.return_value = {
            "terms_learned": [{"term": "Bluebird", "meaning": "v3 navigation stack rewrite"}],
            "people_to_meet": [{"name": "Priya Raman", "team": "Autonomy", "terms": ["Bluebird"]}],
        }
        self.assertIn("Bluebird: v3 navigation stack rewrite", answer_text("What did I learn today?", self.pack, "http://localhost:8000"))
        self.assertIn("Priya Raman (Autonomy)", answer_text("Who should I meet?", self.pack, "http://localhost:8000"))
        self.assertEqual(get_digest.call_count, 2)

    @patch("footnote.fetch_digest", side_effect=OSError("offline"))
    def test_backend_unavailable_has_useful_reply(self, _get_digest):
        self.assertIn("cannot reach", answer_text("Who should I meet?", self.pack, "http://localhost:8000"))


if __name__ == "__main__":
    unittest.main()

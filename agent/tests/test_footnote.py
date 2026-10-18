"""Checks that chat replies use the glossary and the read-only digest."""

import io
import json
import os
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

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_platform_sync_prep_keeps_five_pack_terms_without_stepfun(self, get_digest):
        answer = answer_text("Prep me for my 2pm platform sync", self.pack, "http://localhost:8000")
        self.assertEqual(answer.count("Owner:"), 5)
        for term in ("2pm platform sync", "FCS", "golden path", "Bluebird", "DRI"):
            self.assertIn(term + ":", answer)
        self.assertIn("Marcus Lindqvist (Platform)", answer)
        self.assertIn("Suggested questions", answer)
        self.assertIn("keyword", answer.lower())
        get_digest.assert_called_once_with("http://localhost:8000")

    @patch.dict(os.environ, {"STEPFUN_API_KEY": "test-key"})
    @patch("urllib.request.urlopen")
    @patch("footnote.fetch_digest")
    def test_prep_uses_agenda_and_meeting_terms_with_saved_meanings(self, get_digest, post):
        get_digest.return_value = {"terms_learned": [{
            "term": "Ridgeline", "meaning": "Telemetry migration to the new cluster",
            "owner_name": "Marcus Lindqvist", "owner_team": "Platform", "source": "llm",
            "seen_count": 1, "muted": False,
        }], "people_to_meet": [], "sent": []}
        plan = {"term_ids": ["meeting:0", "t_fcs"], "questions": [
            {"term_id": "meeting:0", "text": "What remains to validate for the telemetry migration?"},
            {"term_id": "t_fcs", "text": "Which dispatch behavior should I understand first?"},
            {"term_id": "meeting:0", "text": "Where can I find the migration notes?"},
        ]}
        post.return_value = io.BytesIO(json.dumps({"choices": [{
            "finish_reason": "stop", "message": {"content": json.dumps(plan)},
        }]}).encode())

        answer = answer_text("Prepare me for a telemetry review about Ridgeline and FCS", self.pack,
                             "http://localhost:8000")
        self.assertIn("Ridgeline: Telemetry migration to the new cluster", answer)
        self.assertIn("Inferred", answer)
        self.assertIn("Suggested contact: Marcus Lindqvist (Platform)", answer)
        self.assertIn("FCS: Fleet Control Service; dispatches robots", answer)
        self.assertIn("Owner: Marcus Lindqvist (Platform)", answer)
        self.assertIn("What remains to validate", answer)
        self.assertIn("StepFun", answer)
        request_body = json.loads(post.call_args.args[0].data)
        context = json.loads(request_body["messages"][1]["content"])
        self.assertIn("Ridgeline and FCS", context["agenda"])
        self.assertTrue(any(t["term"] == "Ridgeline" for t in context["terms"]))
        self.assertLessEqual(len(context["terms"]), 12)
        self.assertNotIn("email", json.dumps(context))
        self.assertEqual(post.call_args.args[0].get_method(), "POST")
        self.assertEqual(post.call_args.kwargs["timeout"], 45)
        get_digest.assert_called_once_with("http://localhost:8000")

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest", side_effect=OSError("offline"))
    def test_prep_fallback_follows_a_different_agenda_when_backend_is_offline(self, _get_digest):
        answer = answer_text("Prep me for an incident review about SLO and run book", self.pack,
                             "http://localhost:8000")
        self.assertIn("SLO: Reliability target", answer)
        self.assertIn("runbook: Step-by-step incident response guide", answer)
        self.assertNotIn("Bluebird:", answer)
        self.assertIn("unavailable", answer.lower())
        self.assertIn("Suggested questions", answer)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": "test-key"})
    @patch("urllib.request.urlopen")
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_invalid_model_plans_fall_back_instead_of_showing_invented_details(self, _get_digest, post):
        questions = [{"term_id": "t_fcs", "text": text} for text in (
            "What should I read first?", "What remains to validate?", "Where is the documentation?"
        )]
        invalid_plans = (
            [],
            {"term_ids": ["invented-project"], "questions": questions},
            {"term_ids": ["t_fcs", "t_fcs"], "questions": questions},
            {"term_ids": ["t_fcs"], "questions": []},
            {"term_ids": ["t_fcs"], "questions": [{"term_id": "t_arr", "text": "Invented fact?"}] * 3},
            {"term_ids": ["t_fcs"], "questions": [{"term_id": "t_fcs", "text": None}] * 3},
            {"term_ids": ["t_fcs"], "questions": questions, "meaning": "Invented fact"},
            {"term_ids": ["t_arr"], "questions": [{"term_id": "t_arr", "text": "Invented fact?"}] * 3},
        )
        for plan in invalid_plans:
            with self.subTest(plan=plan):
                post.return_value = io.BytesIO(json.dumps({"choices": [{
                    "finish_reason": "stop", "message": {"content": json.dumps(plan)},
                }]}).encode())
                answer = answer_text("Prep me for a review of FCS", self.pack, "http://localhost:8000")
                self.assertIn("FCS: Fleet Control Service; dispatches robots", answer)
                self.assertIn("keyword", answer.lower())
                self.assertNotIn("Invented fact", answer)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": "test-key"})
    @patch("urllib.request.urlopen", side_effect=TimeoutError("slow model"))
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_stepfun_timeout_returns_a_useful_keyword_brief(self, _get_digest, _post):
        answer = answer_text("Prep me for a hardware review about Tern and rev B", self.pack,
                             "http://localhost:8000")
        self.assertIn("Tern: Charging dock firmware project", answer)
        self.assertIn("rev B: Second hardware revision of the robot", answer)
        self.assertIn("Hana Sato (Hardware)", answer)
        self.assertIn("keyword", answer.lower())
        self.assertIn("Suggested questions", answer)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": "test-key"})
    @patch("urllib.request.urlopen")
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_broken_or_truncated_model_responses_use_fallback(self, _get_digest, post):
        for response in (b"not JSON", b"{}", b'{"choices": []}',
                         b'{"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}'):
            with self.subTest(response=response):
                post.return_value = io.BytesIO(response)
                answer = answer_text("Prep me for an Atlas mapping meeting", self.pack, "http://localhost:8000")
                self.assertIn("Atlas: HD map build pipeline for navigation", answer)
                self.assertIn("Jules Moreau (Data & Maps)", answer)
                self.assertIn("keyword", answer.lower())

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest", return_value={"terms_learned": [], "people_to_meet": [], "sent": []})
    def test_unmatched_agenda_asks_for_context_instead_of_unrelated_terms(self, _get_digest):
        answer = answer_text("Prep me for a lunch catchup", self.pack, "http://localhost:8000")
        self.assertIn("Add a project name", answer)
        self.assertNotIn("Bluebird:", answer)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest", return_value={"terms_learned": [{
        "term": "Bluebird", "meaning": "An outdated meeting guess",
        "owner_name": "Wrong Person", "owner_team": "Wrong Team", "source": "llm",
        "seen_count": 1, "muted": False,
    }], "people_to_meet": [], "sent": []})
    def test_glossary_facts_win_when_meeting_history_contains_a_conflicting_definition(self, _get_digest):
        answer = answer_text("Prep me for a Bluebird review", self.pack, "http://localhost:8000")
        self.assertIn("Bluebird: v3 navigation stack rewrite", answer)
        self.assertIn("Priya Raman (Autonomy)", answer)
        self.assertNotIn("outdated meeting guess", answer)
        self.assertNotIn("Wrong Person", answer)

    @patch.dict(os.environ, {"STEPFUN_API_KEY": ""})
    @patch("footnote.fetch_digest")
    def test_malformed_digest_still_allows_glossary_prep(self, get_digest):
        for digest in ([], {"terms_learned": None}, {"terms_learned": [{"term": "Ridgeline"}]},
                       {"terms_learned": [{"term": "Ridgeline", "meaning": None,
                        "owner_name": "Marcus Lindqvist", "owner_team": "Platform", "source": "llm"}]},
                       {"terms_learned": [{"term": "Ridgeline", "meaning": "Telemetry migration",
                        "owner_name": "Marcus Lindqvist", "owner_team": "Platform", "source": "unknown"}]}):
            with self.subTest(digest=digest):
                get_digest.return_value = digest
                answer = answer_text("Prep me for an FCS meeting", self.pack, "http://localhost:8000")
                self.assertIn("FCS: Fleet Control Service; dispatches robots", answer)
                self.assertIn("history is unavailable", answer)

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

"""Public card checks use no application fixtures or real messages."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deposium_bench import chat_intent_corpus as corpus


class ChatIntentCardsTests(unittest.TestCase):
    def test_ten_canonical_bilingual_cards(self):
        cards = corpus.load_cards()
        self.assertEqual([c["id"] for c in cards["intents"]], list(corpus.INTENTS))
        self.assertEqual([c["option_id"] for c in cards["intents"]], list("abcdefghij"))
        self.assertEqual(cards["max_state_chars"], 1500)
        for language in ("fr", "en"):
            descriptions = [c["description"][language] for c in cards["intents"]]
            self.assertEqual(len(set(descriptions)), 10)
            self.assertTrue(all(isinstance(t, str) and t.strip() for t in descriptions))
            self.assertEqual(corpus.options(language), [
                {"id": c["option_id"], "description": c["description"][language]}
                for c in cards["intents"]])

    def test_public_text_names_no_application_component(self):
        cards = corpus.load_cards()
        text = json.dumps({k: cards[k] for k in ("intro", "question", "intents")}, ensure_ascii=False).lower()
        for forbidden in ("deposium_", "mcp", "duckdb", "supabase", "mistral", "groq",
                          "bed-llm", "intent-mapping", "llm", "bm25", "regex"):
            self.assertNotIn(forbidden, text)

    def test_return_values_are_independent(self):
        cards, choices = corpus.load_cards(), corpus.options("fr")
        cards["intents"][0]["id"] = "changed"
        choices.reverse()
        self.assertEqual(corpus.load_cards()["intents"][0]["id"], "greeting")
        self.assertEqual(corpus.options("fr")[0]["id"], "a")

    def test_invalid_card_contracts_fail(self):
        original = corpus.load_cards()
        mutations = (
            lambda c: c.update(max_state_chars=0),
            lambda c: c["intents"].reverse(),
            lambda c: c["intents"][0].update(option_id="b"),
            lambda c: c["intents"][0]["description"].update(fr=""),
            lambda c: c["intents"][0]["description"].update(fr=c["intents"][1]["description"]["fr"]),
            lambda c: c["intro"].update(fr="{other}"),
            lambda c: c["question"].pop("en"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cards.json"
            for mutate in mutations:
                cards = deepcopy(original)
                mutate(cards)
                path.write_text(json.dumps(cards), encoding="utf-8")
                with patch.object(corpus, "CARDS_PATH", path), self.assertRaises(ValueError):
                    corpus.load_cards()
        with self.assertRaises(ValueError):
            corpus.options("de")


if __name__ == "__main__":
    unittest.main()

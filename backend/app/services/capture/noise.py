"""Words that carry no field — the one list, in a module both sides can import.

⚠️ IT LIVED IN `typed_extraction` AND HAD TO MOVE, BECAUSE A RATCHET FORBIDS IMPORTING
THAT MODULE. `test_whole_text_extraction.py::test_only_the_typed_path_imports_the_extractor`
asserts the E6 guarantee — *"If a second module ever imports this, the mention policy
stops being isolated to the typed path"* — and it caught `held.py` doing exactly that
for this constant. The gate found it; review did not.

⚠️ A LEAF MODULE, IMPORTING NOTHING, which is what makes it safe for both sides to take.
`typed_extraction` reads it under its old private name so none of its six use sites
change, and `held.py` reads it directly. One list, two readers, and the ratchet's
invariant intact.

⚠️ AND THE SPLIT INSIDE THE LIST IS LOAD-BEARING, so it is preserved verbatim rather
than tidied. The second group — `service`, `burial`, `cemetery`, `funeral`, `home`,
`print`, `date`, `time`, `day` — are "label words a director says around a value rather
than as one", and they are why `held.py` needs this at all: without them "vaalt" would
suggest "Vault", which appears inside dozens of terms, and every near-miss would be
ambiguous.
"""
from __future__ import annotations

#: Words that carry no field and must not be reported as unrecognized.
NOISE_WORDS: frozenset = frozenset({
    "a", "an", "the", "and", "for", "with", "to", "at", "on", "in", "of", "is",
    "it", "its", "please", "thanks", "ok", "okay", "also", "plus", "then",
    "order", "vault", "need", "needs", "want", "wants", "get", "put", "add",
    "new", "start", "create", "make", "enter", "take", "going", "goes", "be",
    "will", "we", "they", "he", "she", "her", "his", "their", "this", "that",
    "no", "not", "none", "only", "just", "both", "all", "some", "there",
    # Label words a director says around a value rather than as one.
    "service", "burial", "cemetery", "funeral", "home", "decedent", "deceased",
    "print", "design", "date", "time", "day", "section", "lot", "space",
})

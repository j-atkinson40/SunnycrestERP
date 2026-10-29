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


# ── moved here 2026-10-29, for the reason NOISE_WORDS was ────────────────────
#
# ⚠️ MOVED OUT OF `typed_extraction` BECAUSE CLAUSE 2 NEEDS IT AND THE E6 RATCHET
# FORBIDS IMPORTING THAT MODULE. `test_only_the_typed_path_imports_the_extractor`
# allows exactly one importer (`session_service`), and it parses rather than greps —
# so a lazy import inside a function is caught too, which is how this move was
# forced. Measured: the ratchet went red on `services/capture/names.py` before
# anything else did.
#
# ⚠️ AND THE ALTERNATIVE WAS A SECOND COPY, which is the defect this codebase keeps
# recording. The surname rules and clause 2 both need "is this word something other
# than a name", and two closed classes would drift apart on the first edit while both
# still looked right — the same argument the town pattern and the casing rule each had
# to have made for them after the fact.
#: English function words: a span must never take one as a name.
#:
#: ⚠️ A CLASS, NOT A STOPLIST OF WORDS THAT HAPPENED TO BURN US. James's walk of
#: 2026-10-26 produced the deceased name **"Smith It"** from
#:
#:     "… in st. marys last name smith it is 1 oclock church service 1pm friday"
#:
#: and the ruling was "fix it in the name rules (not a one-word stoplist)". Adding `it`
#: alone would have been exactly that — and measured, the whole class absorbs:
#: `smith is`, `smith he`, `smith was`, `smith has`, `smith will`, `smith that` all
#: came back as two-word names. One word was the symptom.
#:
#: ⚠️ AND IT SATISFIES THIS FILE'S OWN DOCTRINE RATHER THAN BENDING IT.
#: `_trim_absorbed_word` says the test is "a closed list of words that are something
#: else, not a guess at what a name looks like", because surnames are an OPEN set and
#: any rule about their shape is wrong about somebody's family. A function word has
#: another job: it is a pronoun, a copula, an auxiliary or a determiner. What makes
#: this admissible where "common words" would not be is that the class is CLOSED —
#: English gains surnames constantly and gains pronouns about once a century — so this
#: set is complete in a way a frequency list never is.
#:
#: ⚠️ THE SEPARATORS ARE ALREADY IN `_SPAN_TAIL_STOPS` and are not repeated here; the
#: two sets are unioned below. Kept apart because they are admitted for different
#: reasons — those are words `party_resolver.normalize` strips, which is a fact about
#: this codebase; these are a fact about English.
FUNCTION_WORDS: frozenset = frozenset(
    {
        # pronouns, including possessive and reflexive forms
        "i", "me", "my", "mine", "myself",
        "you", "your", "yours", "yourself", "yourselves",
        "he", "him", "his", "himself",
        "she", "her", "hers", "herself",
        "it", "its", "itself",
        "we", "us", "our", "ours", "ourselves",
        "they", "them", "their", "theirs", "themselves",
        "who", "whom", "whose", "which", "what",
        # determiners and demonstratives not already in `_SPAN_TAIL_STOPS`
        "that", "these", "those", "there", "here",
        "any", "some", "each", "every", "both", "either", "neither", "no", "none",
        # the copula and the auxiliaries
        "is", "am", "are", "was", "were", "be", "been", "being",
        "do", "does", "did", "done",
        "has", "have", "had",
        "will", "would", "shall", "should", "can", "could", "may", "might", "must",
        # conjunctions and the remaining prepositions `_SPAN_TAIL_STOPS` does not hold
        "but", "or", "nor", "so", "if", "then", "than", "because", "while", "when",
        "from", "by", "about", "into", "over", "under", "after", "before", "until",
        "up", "down", "out", "off", "through",
        # the possessive clitic, which arrives as its own token after a split
        "'s",
    }
)

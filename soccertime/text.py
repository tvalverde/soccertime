import unicodedata
from functools import lru_cache


@lru_cache(maxsize=2048)
def fold(text: str) -> str:
    """Lower case and drop the diacritics, so two spellings of a name compare equal.

    Born in the link importer: 67 of the 568 channels in production carry an accent and
    the published lists usually do not — "Aragon TV" found no channel, and every link
    naming it was dropped. The channels page now folds the same way to build the text its
    client-side filter matches against, so "futbol" typed without the accent still finds
    "Fútbol". Only comparisons are folded; whatever reaches the database or the screen
    keeps its accents.

    Cached because both callers ask about the same few hundred names over and over —
    the importer once per entry in a run, the view once per link per render.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(character for character in decomposed if not unicodedata.combining(character))

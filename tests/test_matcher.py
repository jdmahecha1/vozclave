import pytest

from vozclave.config import Command
from vozclave.matcher import UNKNOWN, Matcher, normalize


def test_normalize():
    assert normalize("  Pon   MÚSICA ") == "pon musica"
    assert normalize("ciérrate") == "cierrate"


def test_match_ignores_case_and_accents(commands):
    m = Matcher(commands)
    assert m.match("pon musica").name == "music"
    assert m.match("ABRE SPOTIFY").name == "music"
    assert m.match("cierra spotify").name == "close music"


def test_unknown_or_partial_speech_does_not_match(commands):
    m = Matcher(commands)
    assert m.match("") is None
    assert m.match("[unk]") is None
    assert m.match("pon [unk]") is None
    assert m.match("pon") is None


def test_grammar_lists_every_phrase_plus_unknown(commands):
    grammar = Matcher(commands).grammar()
    assert grammar[-1] == UNKNOWN
    assert set(grammar[:-1]) == {"pon música", "abre spotify", "cierra spotify"}


def test_words(commands):
    assert Matcher(commands).words() == {"pon", "música", "abre", "spotify", "cierra"}


def test_same_phrase_in_two_commands_is_an_error():
    a = Command("a", ("abre spotify",), "open", "x")
    b = Command("b", ("Abre Spotify",), "close", "y")
    with pytest.raises(ValueError, match="both"):
        Matcher([a, b])

"""Translations must expose the same keys and interpolation parameters."""

from string import Formatter

import pytest

from resprint.frontend.i18n import configure_language, normalize_language, t
from resprint.frontend.i18n.en import TRANSLATIONS as EN
from resprint.frontend.i18n.fr import TRANSLATIONS as FR


def test_catalogs_have_matching_keys_and_format_parameters():
    assert FR.keys() == EN.keys()
    formatter = Formatter()
    for key in FR:
        french = {name for _, name, _, _ in formatter.parse(FR[key]) if name}
        english = {name for _, name, _, _ in formatter.parse(EN[key]) if name}
        assert french == english, key
        params = dict.fromkeys(french, 1)
        for language in ("fr", "en"):
            configure_language(language)
            assert t(key, **params)


@pytest.mark.parametrize(
    "value, expected", [(None, "fr"), (" EN ", "en"), ("FR", "fr")]
)
def test_language_normalization(value, expected):
    assert normalize_language(value) == expected


def test_invalid_language_and_missing_translation():
    with pytest.raises(ValueError, match="Unsupported frontend language"):
        configure_language("invalid")
    assert t("missing.translation") == "missing.translation"

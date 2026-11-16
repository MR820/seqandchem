from presets import PRESETS
from seo_copy import PRESET_EXTRAS


def test_unindexed_presets_have_long_copy():
    assert set(PRESET_EXTRAS) <= set(PRESETS)
    for slug, extra in PRESET_EXTRAS.items():
        assert "Frequently asked questions" in extra
        assert len(PRESETS[slug]["prose"]) >= 1900

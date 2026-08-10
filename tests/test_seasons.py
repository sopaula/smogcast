from smogcast.processing.seasons import is_heating_season


def test_heating_season_months() -> None:
    assert is_heating_season(10) is True
    assert is_heating_season(1) is True
    assert is_heating_season(3) is True


def test_non_heating_season_months() -> None:
    assert is_heating_season(4) is False
    assert is_heating_season(7) is False
    assert is_heating_season(9) is False

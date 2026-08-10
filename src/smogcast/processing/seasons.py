def is_heating_season(month: int) -> bool:
    """Return True for heating-season months: October through March."""
    return month in {10, 11, 12, 1, 2, 3}

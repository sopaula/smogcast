import pandas as pd

from smogcast.processing.clean import clean_pm_data
from smogcast.processing.clean import remove_negative_values


def test_remove_negative_values():
    df = pd.DataFrame(
        {
            "Wartość": [
                10.0,
                -5.0,
                20.0,
            ]
        }
    )

    result = remove_negative_values(df)

    assert result["Wartość"].tolist() == [
        10.0,
        20.0,
    ]


def test_smoke_peak_is_preserved():
    df = pd.DataFrame(
        {
            "Wartość": [
                10.0,
                350.0,
                20.0,
            ]
        }
    )

    result = remove_negative_values(df)

    assert 350.0 in result["Wartość"].values


def test_nan_is_preserved():
    df = pd.DataFrame(
        {
            "Wartość": [
                10.0,
                None,
                20.0,
            ]
        }
    )

    result = remove_negative_values(df)

    assert result["Wartość"].isna().sum() == 1


def test_clean_pm_data_resets_index():
    df = pd.DataFrame(
        {
            "Wartość": [
                10.0,
                -5.0,
                20.0,
            ]
        }
    )

    result = clean_pm_data(df)

    assert result.index.tolist() == [0, 1]

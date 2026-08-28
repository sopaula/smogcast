import pandas as pd


# Usuwa pomiary PM o fizycznie niemożliwych wartościach ujemnych
# Wartości NaN oraz wysokie piki smogowe pozostają bez zmian
def remove_negative_values(
    df: pd.DataFrame,
    value_column: str = "Wartość",
) -> pd.DataFrame:
    cleaned_df = df[df[value_column].isna() | (df[value_column] >= 0)].copy()

    return cleaned_df


# Przygotowuje dane PM do dalszego przetwarzania
# Na tym etapie usuwa tylko fizycznie niemożliwe wartości ujemne
# Braków i wysokich wartości smogowych nie usuwa
def clean_pm_data(
    df: pd.DataFrame,
    value_column: str = "Wartość",
) -> pd.DataFrame:
    cleaned_df = remove_negative_values(
        df,
        value_column=value_column,
    )

    return cleaned_df.reset_index(drop=True)

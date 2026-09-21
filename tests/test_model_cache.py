from smogcast.model import predict


def test_model_cache_reloads_after_file_change(
    monkeypatch,
    tmp_path,
):
    model_path = tmp_path / "model.joblib"
    model_path.write_text("model")

    loaded_models = []

    def fake_load(path):
        loaded_models.append(path)

        return {
            "model": object(),
            "feature_columns": [],
        }

    monkeypatch.setattr(
        predict,
        "MODEL_PATH",
        model_path,
    )

    monkeypatch.setattr(
        predict.joblib,
        "load",
        fake_load,
    )

    predict._load_model_bundle.cache_clear()

    # Pierwsze wczytanie modelu.
    first = predict.load_model_bundle()

    # Drugie używa cache.
    second = predict.load_model_bundle()

    assert first is second
    assert len(loaded_models) == 1

    # Symuluje zapis nowej wersji modelu.
    model_path.write_text("new model version")

    third = predict.load_model_bundle()

    # Nowa wersja zostaje ponownie wczytana.
    assert len(loaded_models) == 2
    assert third is not first

    predict._load_model_bundle.cache_clear()

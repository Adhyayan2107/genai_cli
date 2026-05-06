"""Smoke test — package imports. Real tests land alongside each build step."""


def test_package_imports() -> None:
    import scaler_cloner

    assert scaler_cloner.__version__

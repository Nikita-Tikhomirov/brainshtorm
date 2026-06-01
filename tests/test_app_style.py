from brainshtorm.app import APP_STYLE


def test_app_style_uses_streamlit_theme_tokens():
    assert "background:" not in APP_STYLE
    assert "background-color:" not in APP_STYLE
    assert "background: #f7f8fb" not in APP_STYLE
    assert "background: #ffffff" not in APP_STYLE

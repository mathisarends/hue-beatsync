import hue_beatsync


def test_public_api_exports_library_components():
    assert hue_beatsync.visual_names() == ("spectrum", "pulse", "sweep")
    assert hue_beatsync.SpectralAnalyzer
    assert hue_beatsync.AudioCapture
    assert hue_beatsync.create_visual

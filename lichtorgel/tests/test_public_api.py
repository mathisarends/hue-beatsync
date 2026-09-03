import lichtorgel


def test_public_api_exports_library_components():
    assert lichtorgel.visual_names() == ("spectrum", "pulse", "sweep")
    assert lichtorgel.SpectralAnalyzer
    assert lichtorgel.AudioCapture
    assert lichtorgel.Lichtorgel
    assert lichtorgel.SoundDeviceCapture
    assert lichtorgel.create_visual

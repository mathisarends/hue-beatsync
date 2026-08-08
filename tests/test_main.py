from main import main


def test_main_prints_greeting(capsys):
    main()

    captured = capsys.readouterr()
    assert "Hello from hue-beatsync!" in captured.out

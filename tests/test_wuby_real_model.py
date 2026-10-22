"""Manual real-model validation. No inference during pytest collection."""
if __name__ == "__main__":
    from wuby_studio.cli import main
    main(["test-voice"])

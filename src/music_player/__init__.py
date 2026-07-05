__version__ = "0.1.0"

__all__ = ["MusicPlayer", "main"]


def __getattr__(name):
    if name in __all__:
        from music_player.player import MusicPlayer, main
        return {"MusicPlayer": MusicPlayer, "main": main}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

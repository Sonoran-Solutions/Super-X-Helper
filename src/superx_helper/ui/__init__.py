"""GTK4 / Libadwaita user interface for Super X Helper."""

__all__ = ["SuperXApplication", "SuperXWindow"]


def __getattr__(name: str):
    if name == "SuperXApplication":
        from superx_helper.ui.app import SuperXApplication
        return SuperXApplication
    if name == "SuperXWindow":
        from superx_helper.ui.window import SuperXWindow
        return SuperXWindow
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

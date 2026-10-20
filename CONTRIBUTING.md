# Contributing

Thanks for your interest! This is a small personal project and is **work in progress**.

- Bug reports and ideas: open an issue (the form asks for version, Cura version, OS and `cura.log`).
- Pull requests are welcome. By contributing you agree that your contribution is licensed under the same
  [PolyForm Noncommercial License 1.0.0](LICENSE.md) as the rest of the project.
- Please run `python3 tests/test_core.py` and `python3 tests/test_launchers.py` before sending a change.
- Keep the plugin free of extra dependencies: Cura only ships numpy and PyQt6.
- Never add an SVG icon to the plugin folder (an SVG icon attribute once crashed Cura at start-up in another plugin).

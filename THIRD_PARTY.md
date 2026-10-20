# Third-party software

The PolyForm Noncommercial licence of this project covers **only Matthew Armstrong's own code and documents**.
Everything below keeps its own licence. Nothing from these projects is copied into this repository.

| Software | Used for | Licence (see their sites) |
|---|---|---|
| [UltiMaker Cura](https://github.com/Ultimaker/Cura) and [Uranium](https://github.com/Ultimaker/Uranium) | Host program and plugin API the plugin runs in | LGPL-3.0 |
| [numpy](https://numpy.org/) | Geometry (shipped with Cura) | BSD-3-Clause |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) / Qt | Cura's interface, the settings dialog | GPL-3.0 / commercial (Qt: LGPL) |
| [matplotlib](https://matplotlib.org/), [Pillow](https://python-pillow.org/) | Only for drawing the documentation pictures | PSF-style / HPND |
| [PrusaSlicer](https://github.com/prusa3d/PrusaSlicer) | Only used to test-slice the examples | AGPL-3.0 |

The plugin uses Cura's public plugin interfaces. Reading Cura's source code showed how its package manager
installs plugins and how per-object settings behave; that knowledge is described in
[DESIGN_NOTES.md](DESIGN_NOTES.md), no code was taken.

**No affiliation:** this project is not affiliated with, endorsed by or supported by UltiMaker, Prusa Research or
any other company named here.

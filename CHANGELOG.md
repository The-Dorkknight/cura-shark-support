# Changelog

All notable changes. Versions follow semantic versioning; `-wip` marks pre-releases.

## 0.2.1.dev0 - 2026-10-20

First published version.

## [0.2.1-wip] - 2026-10-19 (built 2026-10-19 21:40)

### Added
- The research paper *Fin-ally Supported* (v1.0) in `paper/`: Markdown, PDF, figures and its CC BY-SA 4.0 licence.
  It is also published on its own as `The-Dorkknight/fin-ally-supported`.
- `CITATION.cff`, so GitHub shows **Cite this repository**.

No change to the plugin's behaviour or the fin shapes.

## [0.2.0-wip] - 2026-10-18 (built 2026-10-18 21:50)

### Added
- **Toolbar button** in Cura's left toolbar (under move, scale, rotate...) with a panel: **Pick face**, **Auto**,
  **Remove all**, **Settings...**.
- **Pick face**: click the underside face to support with the mouse; fins go under that one face. Picking it again
  replaces its fins. Picked faces ignore the Auto angle and size limits.
- *Auto* and picking replace a model's earlier fins instead of stacking new ones on top.
- Self-check now also tests face picking and that the toolbar button is registered.

### Changed
- Fins stop at 85 % of their height (*Top left free*, 15 %) and end in a **blunt 5 mm flat top**, then go
  **straight down**. No more sharp tip with tiny slow top layers. Test box: 1.68 m of filament and about 40 min for
  the fins (0.1.2: 1.76 m, about 43 min).
- Optional back leaning out to the bed (*Lean the back out*, 20°) for a wider base.
- Crossbar now sits under the tip.
- Settings are stored under a new key, so saved settings reset to the new defaults once.

## [0.1.2-wip] - 2026-10-17 (built 2026-10-17 21:50)

### Changed
- Twice as many teeth: tooth spacing 3 mm (was 6 mm).
- The first 2 teeth of each fin (*anchor teeth*) now reach 0.1 mm into the part so they bond slightly and hold
  the start of the overhang. Settings *Anchor teeth* and *Anchor overlap* (0 anchors turns it off).
- All other tips stop 0.15 mm under the part (was 0.2 mm).
- The self-check now accepts the anchor overlap and still fails if anything else reaches into the part.

## [0.1.1-wip] - 2026-10-17 (built 2026-10-17 21:40)

### Changed
- Fins are now plain triangles: straight back edge at the tall end instead of the round back. About 23 % less
  plastic in the fins and a few minutes less printing on the test box. The round back is an option
  (*Round back edge* in the settings, `--back round` on the command line; `--back concave` for the shark look).
- The first tooth now starts right at the fin's low end instead of up to ~15 % in, and a last tooth sits at the
  tall end.
- Settings are stored under a new key, so earlier saved settings reset to the new defaults once.

## [0.1.0-wip] - 2026-10-16 (built 2026-10-16 15:13)

First proof of concept. **WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.**

### Added
- Shark-fin supports under flat tilted faces, found automatically: tapered fins along the downhill direction,
  1 mm relief gap with teeth that stop 0.2 mm under the part, round (or concave) back edge, crossbar foot,
  4 mm one-layer brim pad.
- Cura plugin (SDK 8, Cura 5.x): Extensions > Shark Support menu, settings dialog, self-check, Remove all fins,
  undo, optional experimental support-mesh mode, turns off normal support for the model.
- Installer window (`install.py`) with Linux, Windows and Mac double-click launchers; text mode fallback;
  checks Cura's own log; uninstall.
- `.curapackage` builder for Cura's drag-and-drop install.
- Command line tool `shark_cli.py` for any slicer.
- Tests, Cura test driver, example STLs, documentation, Pages site.

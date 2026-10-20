# How Shark Support works

**WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.** Plain-English description of version 0.2.1-wip.

## What it reads

- The triangles of the model(s) you selected, already placed and rotated in Cura (their world position).
- Your saved Shark Support settings (Cura preferences, keys starting `sharksupport/`).
- The printer profile's **first layer height** (`layer_height_0`), for the brim pad thickness.

## How you use it in Cura

- A **toolbar tool** (the shark-fin button in the left toolbar) with a panel: *Pick face*, *Auto*, *Remove all*,
  *Settings...*. In pick mode a left click on the selected model asks Cura for the 3D point under the mouse
  (Cura's own picking render pass, the same one its support blocker uses), finds the triangle at that point, and
  makes fins under the flat face that triangle belongs to.
- A **menu**, Extensions > Shark Support, with the same actions plus self-check and About.

## What it changes

- Adds a new object per model (Auto) or per picked face, named `Shark fins (<model name>...)`, containing the fins.
  Picking the same face again, or pressing Auto, replaces the earlier fins of that model instead of stacking them.
  It is a normal printable object with three per-object settings: infill 100 %, support off, and
  "Union overlapping volumes" on (so the fin, its crossbar and its pad print as one piece).
  In *support mesh* mode it instead gets "Support mesh" on and "Drop down support mesh" off.
- If *Turn off normal support for the model* is ticked (default), it sets the per-object setting
  **Generate Support = off on your model**, so Cura does not add its own supports under the same face.
  This is visible in Cura's per-model settings and can be changed back.
- Both are ordinary Cura operations: **Ctrl+Z** undoes them.

## What it never does

- It never edits your model's shape, your profiles, or files on disk (apart from its own preferences and a
  self-check report in your temp folder).
- It does not talk to the internet.
- It does not change global settings such as brim, adhesion or support density.

## How the fins are made

1. **Find the faces.** Picked: the face under the mouse click. Auto: triangles that face downwards are grouped into flat faces when they share an edge and
   point the same way (within 3°). In Auto a face qualifies when its overhang angle is in the chosen range (Cura's
   convention, 0° = vertical wall, 90° = flat ceiling), and it is big enough and reaches far enough along its slope.
2. **Downhill.** For each face the steepest-descent direction inside its plane is worked out and flattened onto
   the bed: that is the direction a ball would roll. Fins run along it; across the face they are spaced evenly,
   keeping a margin from the sides.
3. **Measure the underside.** Along each fin line, vertical rays go up from the bed every 0.5 mm. The first thing
   a ray hits is the lowest point of the part above. (For a closed mesh that is always a downward-facing triangle,
   so only those are indexed, in a grid, which keeps it fast.) The fin keeps the longest stretch whose hits belong
   to the face and are above the start height.
4. **Where it stops.** The fin follows the part up to 85 % of the height it would reach (*Top left free*: 15 %);
   the part bridges the rest.
5. **Shape the top edge.** The edge sits 1 mm under the measured underside. Teeth ramp up, stay flat for 0.6 mm
   and ramp down again. The first tooth starts right at the fin's low end, then one every 3 mm, and a last one where
   the fin stops. The first two (*anchor teeth*) reach 0.1 mm into the part so they bond
   slightly; all others stop 0.15 mm under it.
6. **Blunt tip and back.** At 85 % the fin turns into a flat top 5 mm long, then goes straight down to the bed, so
   no layer of the fin is shorter than 5 mm (tiny layers make the printer brake and accelerate for nothing).
   Optionally the back leans out 20° (wider base), or is round or concave (command line), all checked against
   the part. Teeth near the cut are flattened to the top so nothing pokes above it.
7. **Thickness.** The fin is 2.4 mm thick at the bed and 1.2 mm at its top edge, tapering with height.
8. **Crossbar and brim.** A 4 mm high bar across the fin under its tip (and one in the middle on long fins),
   lowered if the part is close above it. A one-layer pad 4 mm wider than the fin and each crossbar, trimmed where
   the part comes close to the bed.
9. Each piece is a closed, outward-facing mesh. The Cura plugin turns Cura's Y-up scene coordinates into Z-up
   millimetres for this, and back.

## Files

| File | Job |
|---|---|
| `SharkSupport/shark_core.py` | All geometry, numpy only (also used by the command line tool and the tests) |
| `SharkSupport/SharkActions.py` | Everything shared: settings, making and removing fin objects, self-check |
| `SharkSupport/SharkSupportTool.py` | The toolbar button: panel actions and face picking |
| `SharkSupport/SharkSupportExtension.py` | The Extensions menu |
| `SharkSupport/qml/SharkSupportTool.qml` | The toolbar panel |
| `SharkSupport/icons/shark_tool.svg` | The toolbar icon (no fill on its `<svg>` tag: Cura adds its own) |
| `SharkSupport/qml/SharkSupportDialog.qml` | Settings window |
| `install.py` + `Install-*.sh/.bat/.command` | Installer and its double-click launchers |
| `shark_cli.py` | Command line tool |
| `tools/` | Package builder, pictures, G-code side view |
| `tests/` | Geometry tests, launcher tests, and the Cura test driver used during development |

## How the installer decides "installed"

1. It looks for Cura's data folders (`~/.local/share/cura/5.x`, the Flatpak folder, `%APPDATA%\cura\5.x`,
   `~/Library/Application Support/cura/5.x`).
2. It copies the plugin to `<data>/plugins/SharkSupport/SharkSupport/`, which is where Cura's own package manager
   puts plugins, and adds the same kind of entry Cura writes to `packages.json`, so it appears in Cura's plugin list.
3. It reads every file back and compares checksums.
4. Only after Cura has been started does it say **LOADED**: the plugin writes a line to `cura.log` and a small
   marker file when Cura loads it, and the installer checks both are newer than the install.

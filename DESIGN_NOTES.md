# Design notes and research (0.2.1-wip)

Everything learned while building 0.1.0 to 0.2.0, kept so it is not lost. Statements about Cura come from reading Cura
and Uranium source (main branch, October 2026, version 5.15.0-alpha.0, plugin SDK 8.13.0) and from running it,
unless marked otherwise.

## Goal (from the brief, 16 Oct 2026)

- Large objects printed tilted, e.g. a long rectangular box stood on one long edge with its base tilted up,
  so the long walls are strong. The base becomes a long 30–55° overhang. Short overhangs at that angle print
  unsupported, but a long one sags and curls, so it needs help.
- A "shark fin": a fin that follows the angle of the part and the bed.
- Built from primitives (like the Hybrid Supports towers).
- Contact with the print at points, not along whole layers, for easy removal.
- A brim around the fin, about 4 mm.
- A crossbar about ¼ of the fin length and about 4 mm high to brace it.
- Self-contained (not part of Hybrid Supports), reusing ideas where that is cheaper.

## Decisions

### Fins are solid parts, not Cura support meshes (default)

- **Cura's "support brim" is the wrong thing.** In the 5.x releases `support_brim_enable` ("Enable Support Brim")
  prints a brim *inside* the support area on the first layer, not around it. The current main branch renames it
  "Inner Support Base" and adds `support_outer_brim_enable`, which is not in any release we could check. So a
  4 mm brim *around* each fin cannot come from Cura's settings: the plugin builds it as geometry, a pad one
  first-layer high, 4 mm wider than the fin. That works in every slicer.
- **Support meshes print at the support density.** `support_infill_rate`, `support_wall_count` and similar are not
  settable per object (`settable_per_mesh: false`), so a fin made as a support mesh would be printed at, for
  example, 15 % lines: useless for a 1–2 mm plate. As a normal object with 100 % infill the fin prints solid.
- **Rejected alternative:** support mesh + changing the user's global support density and walls. It changes every
  other support in the print, which the user did not ask for.
- The support-mesh route is still offered as an experimental switch for comparison.
- Consequence: the plugin controls the gap itself (Cura adds no support Z distance between two models). The teeth
  stop `contact_gap` (0.2 mm in 0.1.0, 0.15 mm since 0.1.2) under the part; between teeth the edge is `relief`
  (1 mm) away.

### Points, not lines

- A plain fin whose top edge follows the slope already touches each layer only briefly, because the face rises
  as the fin goes back. The teeth reduce that to a dotted line: 0.6 mm × fin top thickness (1.2 mm) every 6 mm (every 3 mm since 0.1.2).
- **Same-layer closeness (not print-tested):** on a face at angle θ from horizontal, a vertical tip gap g means the
  part's outline and the tooth tip are g / tan θ apart horizontally in the same layer. For the 35° test box:
  0.2 / tan 35° ≈ 0.29 mm, less than a 0.4 mm line width, so tips and part slightly overlap in XY and will bond a
  little. That is the intended point contact. If it bonds too well, raise the tip gap (0.3 mm gives ≈ 0.43 mm).
  An option for a horizontal tip clearance is an idea for later.

### Downhill direction, longest run

- Fins run along the steepest descent inside the face's plane, flattened to the bed. Across that direction the
  face is level, so a fin's top edge is at the same height across its thickness.
- Rays are cast up from the bed: the first hit from below on a closed mesh is always a downward-facing triangle,
  so only those are put in a uniform XY grid. 196,608 triangles: about 2 s total on the build machine (1.6-2.3 s across runs).
- A fin keeps only the **longest** stretch of rays that hit its own face above the start height, so it never
  climbs onto a neighbouring face or crosses a gap.

### Shape

- **Tapered thickness** (2.4 mm at the bed, 1.2 mm at the top): stiffer at the root where the bending is.
- **Straight back edge (triangle) by default since 0.1.1.** 0.1.0 had a round back (quarter ellipse, 0.35 × height
  long). Reviewing the profile picture, Matthew pointed out it costs plastic for no clear benefit: the crossbar at
  the tall end already braces the fin against tipping, and the round back only adds a strip of material beyond the
  part. Measured on the test box: fins 4.4 cm³ instead of 5.7 cm³ (−23 %), PrusaSlicer 2.7.2 1.74 m instead of
  2.27 m of filament, about 42 instead of 48 minutes. Round and concave backs stay as options.
- **First tooth at the low end (0.1.1).** 0.1.0 centred the row of teeth along the fin, so the first contact could
  sit up to half a tooth spacing plus a tooth (about 15 % of a short fin) in from the low end, leaving the start of
  the overhang unheld. Now the first tooth's ramp starts at the fin's first millimetre, teeth follow every 6 mm (3 mm from 0.1.2) and
  a last tooth sits at the tall end. Note the fin itself still starts where the face is 4 mm above the bed
  (*Start height*); below that the face is short enough to print unsupported.
- **More teeth and anchor teeth (0.1.2, Matthew's call).** Tooth spacing halved from 6 to 3 mm (5 → 9 teeth per fin
  on the test box, 25 → 45 in total). The first two teeth from the low end now reach 0.1 mm *into* the part
  (half a 0.2 mm layer) so they bond slightly and hold the start of the overhang, where curling begins; every
  other tip stops 0.15 mm short (was 0.2). Cost: fins 1.76 m of filament instead of 1.74 m, about 43 instead of
  42 minutes. In PrusaSlicer 2.7.2 G-code the anchor teeth's lines run straight into the part's outer wall while
  the other teeth leave a visible gap (`docs/images/gcode-anchor.webp`). With separate objects, an overlap of
  0.1 mm is enough for the slicer to place fin and part lines side by side in the same layer; neither Cura nor
  PrusaSlicer merges them, so the bond is a weld between neighbouring lines, not a solid joint. Not print-tested.
- **Cut at 85 %, blunt top, straight back (0.2.0, Matthew's review of a Cura preview).** The fin no longer runs
  to the top of the face: the part is held by the lower 85 % and bridges the rest (*Top left free*, 15 %, his
  10–20 %). It ends in a flat top 5 mm long, then goes straight down. A sharp triangle tip means the last layers
  are a few millimetres or less: the printer brakes and accelerates for tiny moves and the tip prints badly. With
  the flat top no fin layer is shorter than 5 mm. Teeth near the cut are clamped to the flat top so none pokes
  above it. The crossbar moved under the tip, where the fin is tallest.
  - Matthew sketched the back as a line leaning out to the bed. Measured, that costs more than going straight
    down: test box fins (PrusaSlicer 2.7.2, 0.2 mm) - straight down 1.68 m / 40 min; leaning 20° 1.97 m /
    42 min; 0.1.2 (sharp tip to the top) 1.74 m / 43 min. Straight down is the default; the lean is a setting
    (*Lean the back out*) for when a wider base is wanted.
  - His screenshot still showed the 0.1.0 round back; 0.1.1 had already replaced it with a straight back.
- **Pick a face (0.2.0).** The toolbar tool asks Cura for the 3D point under the mouse with its picking render
  pass (`picking_selected`), the same mechanism Cura's support blocker uses in every 5.x version. The plugin then
  finds the triangle containing that point (within 1 mm of its plane, or 1 % of the model size) and uses the flat
  face that triangle belongs to. Picked faces skip the Auto angle and size limits but must face down (an
  upward face or a flat ceiling is refused with a message). Cura 5.11+ also has a face-ID render pass and
  deprecated the old `Selection.setFaceSelectMode` route; the point-picking route avoids both and works the same
  on old and new versions. On 5.11+ the picking pass is only rendered while a tool asks for it
  (`getRequiredExtraRenderingPasses`); older versions create a `PickingPass` on demand like their support blocker.
- **Teeth as islands, and a live patent (0.2.1 paper review).** In the top layers of a fin each tooth tip is a
  separate small island in the slice, so slicers retract and travel (and may lift) between them. US 9,469,057
  (3D Systems, active to about 2034) claims a method of printing FFF supports that meet the part at discrete
  "fine points" with a retract, lift, move, lower sequence between them. How that relates to Shark Support has
  not been assessed; see the paper, section 2. Not legal advice.
- **Toolbar button.** A Cura tool plugin can also be an extension: `register()` returns both. The toolbar loads
  the icon from the plugin folder when the theme has no icon of that name, and recolours it by inserting a
  `fill` attribute into the `<svg` tag (`UM/ColorImage.py`), so the SVG must not carry its own `fill` there (a
  duplicate attribute makes it invalid XML; a test checks this). Uranium keeps only the last-registered object per
  plugin id, so both share one `SharkActions` instance.
- With 3 mm spacing and 1 mm ramps the valleys between teeth are only 0.4 mm long: the top edge is effectively a
  saw-tooth. If that holds too well, 4 mm spacing or 0.8 mm ramps open the valleys again.
- **Crossbar at the tall end**, because that is where leverage is worst. A second one in the middle for fins with a
  footprint over 100 mm. Crossbars are lowered if the part comes within `relief` above them, and skipped if that
  leaves less than 1.5 mm.
- **Brim pad** trimmed at the low end until the part is at least `brim_clearance` (1 mm) above it, so it never
  touches the part's edge on the bed.

## Cura facts found on the way (useful for other plugins)

- **Uranium signals keep weak references.** `engineCreatedSignal.connect(lambda: ...)` silently never fires because
  the lambda is garbage-collected. Connect a bound method.
- **`isSupportMesh` is cached.** `SettingOverrideDecorator` stores `_is_support_mesh` and only refreshes it in
  `_onSettingChanged`. Adding a `SettingInstance` the way Cura's own SupportEraser does leaves the cache stale
  (the stack property reads True, the decoration reads False). The plugin calls the decorator's
  `_onSettingChanged` after setting a value.
- **Plugins load before the file logger.** Lines logged in a plugin's constructor appear on the console but not in
  `cura.log`. The plugin logs its "loaded" line again on `engineCreatedSignal`, and the installer also checks a
  marker file.
- **`UM.Dialog`'s default property holds Items only.** A `Connections` object placed directly in it makes the
  whole dialog fail to load ("Cannot assign object of type QQmlConnections"). Put it inside the layout.
- **Install location** used by Cura's package manager: `<data>/plugins/<id>/<id>/`, plus an entry under
  `installed` in `<data>/packages.json`. Dropping a `.curapackage` on Cura copies it to the cache and lists it
  under `to_install`; Cura moves it into place on the next start. Both routes were checked in Cura from source.
- `CuraSceneNode` mesh data from `getTransformed(getWorldTransformation())` may have no index array (a triangle
  soup), so vertices are welded first.
- Cura's scene is Y-up with Z toward the front: printer (x, y, z) = scene (x, −z, y).

## Measurements

| Model | Result |
|---|---|
| Box 150 × 40 × 25 mm on a long edge, base tilted 35° (55° overhang) | 5 fins, 40 teeth (10 anchors), 5 crossbars; fins 4.3 cm³ including pads and crossbars (0.1.2: 4.4 cm³; leaning back 5.0 cm³) |
| Same box at 45° | both faces next to the edge qualify: 10 fins |
| Same box also rolled 12° (standing on a corner) | 10 fins; with anchors off the closest tip is 0.15 mm under the part (0.2 mm in 0.1.0) |
| Subdivided box, 196,608 triangles | about 2 s (1.6-2.3 s across runs) |

## How it was tested

- `tests/test_core.py`: geometry checks (see the README).
- `tests/cura_harness/`: a test-only Cura plugin that drives Shark Support inside a running Cura: sets up an Elegoo
  Neptune 4, loads the test box, adds fins, checks the fin object, opens the dialog, runs the self-check, tries
  support-mesh mode and removal, checks Cura's package manager lists the plugin. It was run against Cura from
  source with Python stand-ins for the C++ modules (pyArcus, pynest2d, pySavitar, pyUvula). Slicing therefore could
  not be tested in Cura.
- PrusaSlicer 2.7.2 command line sliced the merged test box; `tools/gcode_side_view.py` drew the G-code slice.

## Ideas and to-do

- Horizontal tip clearance setting, so the same-layer overlap can be controlled directly.
- Fins under gently curved faces (follow the surface with the same raycasts, drop the flat-face grouping).
- Paint exactly where on a face fins go (picking whole faces exists since 0.2.0).
- Re-generate the fins automatically when the model is moved (watch the node's transform).
- Run the work in a background job for very large meshes.
- An OrcaSlicer/PrusaSlicer flow: their plugin APIs do not take Python, so the CLI tool is the route for now.
- Share the ray caster and primitive builder with Hybrid Supports later, as a small library both vendor in.

## Relationship to other projects

- **cura-hybrid-supports**: same family (Cura support plugins built from primitives and raycasts). Shark Support is
  deliberately standalone; the raycast-down and primitive-building ideas were rewritten here rather than imported.
- **ShiftLoK / FlatLock**: also slicer plugins, but about walls, no overlap.

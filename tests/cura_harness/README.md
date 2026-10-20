# Cura test driver (development only)

`SharkSupportHarness/` is a test-only Cura plugin. It is **not** installed by the installer. Copied next to
Shark Support in a Cura data folder's `plugins/` directory, it drives the plugin inside a running Cura and writes
`HARNESS:` lines (PASS/FAIL) to the log: sets up an Elegoo Neptune 4 if there is no printer, loads the STL in
`SHARK_HARNESS_STL`, adds fins, checks the fin object and its per-object settings, opens the dialog, runs the
self-check, tries support-mesh mode and removal, and checks Cura's package manager lists the plugin.
With `SHARK_HARNESS_CURAPACKAGE=<file>` it instead schedules a `.curapackage` install (Cura's own route).

For 0.1.0 it ran against **Cura from source** (Cura and Uranium main branches, October 2026) under Xvfb, with
`stubs_sitecustomize.py` standing in for pyArcus, pynest2d, pySavitar and pyUvula. `run_cura_from_source.sh`
is the script used. Because the slicing engine was a stand-in, slicing in Cura was not tested.

You can also use it in a real Cura: copy `SharkSupportHarness` into `<cura data>/plugins/`, set the environment
variables, start Cura, and read `cura.log`. Remove it afterwards.

#!/usr/bin/env python3
# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
#
# Shark Support installer - WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN
#
# Finds every UltiMaker Cura 5.x on this computer, installs the plugin the way Cura's
# own package manager does (files under <cura data>/plugins/SharkSupport/SharkSupport
# plus an "installed" entry in packages.json, so it shows in Cura's plugin list),
# reads the files back, and then confirms from cura.log that Cura really loaded it.
# Standard library only. Text mode: python3 install.py --cli [--uninstall]
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
import package_info as pi  # noqa: E402

VERSION = pi.plugin_version() + "-wip"
BUILD_DATE = "2026-10-19 21:40"
TITLE = "Shark Support installer %s (Built %s)" % (VERSION, BUILD_DATE)
LOADED_RE = re.compile(r"Shark Support (\S+) \(built ([^)]*)\) loaded")
SYSTEM = platform.system()


# ---------------------------------------------------------------- finding Cura
def data_roots():
    """Folders that hold Cura's per-version data folders (5.0, 5.11, ...)."""
    home = os.path.expanduser("~")
    roots = []
    if SYSTEM == "Windows":
        appdata = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        roots.append(os.path.join(appdata, "cura"))
    elif SYSTEM == "Darwin":
        roots.append(os.path.join(home, "Library", "Application Support", "cura"))
    else:
        xdg = os.environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        roots.append(os.path.join(xdg, "cura"))
        roots.append(os.path.join(home, ".var", "app", "com.ultimaker.cura", "data", "cura"))  # Flatpak
    return roots


def _vkey(name):
    try:
        return tuple(int(x) for x in name.split("."))
    except ValueError:
        return (0,)


def find_cura_data():
    """[(version, data_dir, flavour)] for Cura 5.x, newest first."""
    out = []
    for root in data_roots():
        if not os.path.isdir(root):
            continue
        flavour = "Flatpak" if "com.ultimaker.cura" in root else "standard"
        for name in os.listdir(root):
            d = os.path.join(root, name)
            if os.path.isdir(d) and re.fullmatch(r"\d+\.\d+", name) and _vkey(name) >= (5, 0):
                out.append((name, d, flavour))
    out.sort(key=lambda t: _vkey(t[0]), reverse=True)
    return out


def find_cura_programs():
    """Things that start Cura: [(label, argv)]."""
    home = os.path.expanduser("~")
    found = []
    if SYSTEM == "Windows":
        for base in filter(None, [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                                  os.environ.get("LOCALAPPDATA") and os.path.join(os.environ["LOCALAPPDATA"], "Programs")]):
            if not os.path.isdir(base):
                continue
            for name in os.listdir(base):
                if "cura" in name.lower():
                    for exe in ("UltiMaker-Cura.exe", "Ultimaker-Cura.exe", "Cura.exe"):
                        p = os.path.join(base, name, exe)
                        if os.path.isfile(p):
                            found.append((name, [p]))
    elif SYSTEM == "Darwin":
        for base in ("/Applications", os.path.join(home, "Applications")):
            if os.path.isdir(base):
                for name in os.listdir(base):
                    if "cura" in name.lower() and name.endswith(".app"):
                        found.append((name[:-4], ["open", "-n", os.path.join(base, name)]))
    else:
        for base in (home, os.path.join(home, "Applications"), os.path.join(home, "Downloads"),
                     os.path.join(home, "Desktop"), "/opt"):
            if os.path.isdir(base):
                for name in os.listdir(base):
                    if "cura" in name.lower() and name.lower().endswith(".appimage"):
                        found.append((name, [os.path.join(base, name)]))
        if shutil.which("flatpak"):
            try:
                r = subprocess.run(["flatpak", "info", "com.ultimaker.cura"], capture_output=True, timeout=10)
                if r.returncode == 0:
                    found.append(("Cura (Flatpak)", ["flatpak", "run", "com.ultimaker.cura"]))
            except (OSError, subprocess.SubprocessError):
                pass
        for exe in ("cura", "UltiMaker-Cura"):
            p = shutil.which(exe)
            if p:
                found.append((exe, [p]))
    return found


# ---------------------------------------------------------------- install / check
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def plugin_target(data_dir):
    return os.path.join(data_dir, "plugins", pi.PLUGIN_ID, pi.PLUGIN_ID)


def _load_packages(data_dir):
    p = os.path.join(data_dir, "packages.json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as fh:
                return p, json.load(fh)
        except (OSError, ValueError):
            pass
    return p, {"version": 3, "installed": {}, "to_remove": [], "to_install": {}, "dismissed": []}


def _save_packages(path, data):
    tmp = path + ".sharktmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, sort_keys=True, indent=4)
    os.replace(tmp, path)


def install(data_dir):
    """Copy, register, read back. Returns a list of problems (empty = good)."""
    problems = []
    target = plugin_target(data_dir)
    outer = os.path.dirname(target)
    if os.path.isdir(outer):
        shutil.rmtree(outer)
    os.makedirs(target, exist_ok=True)
    files = pi.plugin_files()
    for rel, src in files:
        dst = os.path.join(target, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
    # read back
    for rel, src in files:
        dst = os.path.join(target, rel)
        if not os.path.isfile(dst) or _sha(dst) != _sha(src):
            problems.append("copy check failed: " + rel)
    # register like Cura's package manager does after an install
    path, data = _load_packages(data_dir)
    info = pi.package_json()
    info.update({"is_active": True, "is_bundled": False, "is_installed": True})
    data.setdefault("installed", {})[pi.PLUGIN_ID] = {"package_info": info, "filename": ""}
    if pi.PLUGIN_ID in data.get("to_remove", []):
        data["to_remove"].remove(pi.PLUGIN_ID)
    data.get("to_install", {}).pop(pi.PLUGIN_ID, None)
    _save_packages(path, data)
    _, again = _load_packages(data_dir)
    if pi.PLUGIN_ID not in again.get("installed", {}):
        problems.append("packages.json entry did not stick")
    with open(os.path.join(outer, ".shark_installed_at"), "w") as fh:
        fh.write(str(time.time()))
    return problems


def uninstall(data_dir):
    outer = os.path.dirname(plugin_target(data_dir))
    if os.path.isdir(outer):
        shutil.rmtree(outer)
    path, data = _load_packages(data_dir)
    if os.path.isfile(path) and pi.PLUGIN_ID in data.get("installed", {}):
        del data["installed"][pi.PLUGIN_ID]
        _save_packages(path, data)
    return not os.path.exists(outer)


def installed_version(data_dir):
    pj = os.path.join(plugin_target(data_dir), "plugin.json")
    try:
        with open(pj, encoding="utf-8") as fh:
            return json.load(fh).get("version")
    except (OSError, ValueError):
        return None


def installed_at(data_dir):
    try:
        with open(os.path.join(os.path.dirname(plugin_target(data_dir)), ".shark_installed_at")) as fh:
            return float(fh.read().strip())
    except (OSError, ValueError):
        return None


def loaded_marker(data_dir):
    """(version, build, time) the plugin wrote when Cura last loaded it, or None."""
    try:
        with open(os.path.join(os.path.dirname(plugin_target(data_dir)), ".shark_loaded")) as fh:
            ver, rest = fh.read().strip().split(" ", 1)
            build, t = rest.rsplit(" ", 1)
            return ver, build, float(t)
    except (OSError, ValueError):
        return None


def log_status(data_dir):
    """('loaded', text) | ('error', text) | ('not yet', text) from Cura's own log."""
    log = os.path.join(data_dir, "cura.log")
    if not os.path.isfile(log):
        return "not yet", "no cura.log yet - start Cura once"
    since = installed_at(data_dir) or 0
    if os.path.getmtime(log) < since:
        return "not yet", "Cura not started since install"
    try:
        with open(log, encoding="utf-8", errors="replace") as fh:
            text = fh.read()[-3_000_000:]
    except OSError as ex:
        return "not yet", "cannot read cura.log: %s" % ex
    # look at the newest Cura session only
    starts = [m.start() for m in re.finditer(r"Initializing (?:UltiMaker|Ultimaker) Cura", text)]
    session = text[starts[-1]:] if starts else text
    errs = [ln for ln in session.splitlines()
            if ("SharkSupport" in ln or "Shark Support" in ln) and (" - ERROR - " in ln or " - CRITICAL - " in ln)]
    m = None
    for m in LOADED_RE.finditer(session):
        pass
    if errs:
        return "error", errs[0].split("] ", 1)[-1][:160]
    mk = loaded_marker(data_dir)
    if m and mk and mk[2] >= since:
        return "loaded", "LOADED by Cura - %s, built %s (log and marker agree)" % (m.group(1), m.group(2))
    if m:
        return "loaded", "LOADED by Cura - %s, built %s (cura.log)" % (m.group(1), m.group(2))
    if mk and mk[2] >= since:
        return "loaded", "LOADED by Cura - %s, built %s (at %s)" % (mk[0], mk[1], time.strftime("%H:%M", time.localtime(mk[2])))
    return "not yet", "Cura has not loaded it yet (restart Cura)"


# ---------------------------------------------------------------- text mode
def cli(args):
    print(TITLE)
    print("WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN. No warranty.")
    found = find_cura_data()
    if not found:
        print("No Cura 5 data folder found. Start Cura once, close it, then run this again.")
        for r in data_roots():
            print("  looked in:", r)
        return 1
    rc = 0
    for ver, d, flav in found:
        if args.uninstall:
            print("Cura %s (%s): %s" % (ver, flav, "removed" if uninstall(d) else "could not remove"))
            continue
        if args.check:
            st, txt = log_status(d)
            print("Cura %s (%s): installed %s - %s" % (ver, flav, installed_version(d) or "no", txt))
            continue
        probs = install(d)
        if probs:
            rc = 1
            print("Cura %s (%s): PROBLEM %s" % (ver, flav, "; ".join(probs)))
        else:
            print("Cura %s (%s): installed and read back OK -> %s" % (ver, flav, plugin_target(d)))
    if not args.uninstall and not args.check:
        print("Now start Cura, then run:  python3 install.py --cli --check  (or use the window)")
        print("In Cura: Extensions > Shark Support.")
    return rc


# ---------------------------------------------------------------- window
def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title(TITLE)
    root.geometry("860x480")
    root.minsize(720, 380)
    style = ttk.Style(root)
    style.configure("Treeview", rowheight=26)
    for tag in ("good", "bad", "wait"):
        pass

    top = ttk.Frame(root, padding=10)
    top.pack(fill="both", expand=True)
    ttk.Label(top, text="Shark Support for UltiMaker Cura", font=("TkDefaultFont", 14, "bold")).pack(anchor="w")
    ttk.Label(top, foreground="#b45309",
              text="WORK IN PROGRESS: MANY FEATURES MAY BE BROKEN.  Close Cura before installing.").pack(anchor="w", pady=(2, 8))

    cols = ("cura", "kind", "installed", "status")
    tree = ttk.Treeview(top, columns=cols, show="headings", height=6, selectmode="extended")
    for c, w, t in (("cura", 90, "Cura"), ("kind", 90, "Type"), ("installed", 110, "Shark Support"),
                    ("status", 520, "Status (from Cura's own log)")):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w", stretch=(c == "status"))
    tree.tag_configure("good", background="#dcfce7")
    tree.tag_configure("bad", background="#fee2e2")
    tree.tag_configure("wait", background="#fef9c3")
    tree.pack(fill="both", expand=True)

    status = tk.StringVar(value="")
    rows = {}

    def refresh():
        tree.delete(*tree.get_children())
        rows.clear()
        found = find_cura_data()
        for ver, d, flav in found:
            iv = installed_version(d)
            st, txt = log_status(d) if iv else ("none", "not installed")
            tag = {"loaded": "good", "error": "bad", "not yet": "wait"}.get(st, "")
            iid = tree.insert("", "end", values=(ver, flav, iv or "-", txt), tags=(tag,))
            rows[iid] = d
        if not found:
            status.set("No Cura 5 found. Start Cura once, close it, then press Check.  Looked in: " + ", ".join(data_roots()))
        else:
            status.set("Found %d Cura data folder(s). Press Install (or click rows to pick some), then Start Cura. Green = Cura loaded it." % len(found))

    def chosen():
        sel = tree.selection() or tree.get_children()
        return [rows[i] for i in sel]

    def do_install():
        msgs = []
        for d in chosen():
            probs = install(d)
            msgs.append("%s: %s" % (os.path.basename(d), "OK, read back" if not probs else "; ".join(probs)))
        refresh()
        status.set("Installed - " + " | ".join(msgs) + ". Now press Start Cura (or start it yourself).")

    def do_uninstall():
        if not messagebox.askyesno("Uninstall", "Remove Shark Support from the selected Cura(s)?"):
            return
        for d in chosen():
            uninstall(d)
        refresh()
        status.set("Removed. Restart Cura to drop it from memory.")

    progs = find_cura_programs()

    def poll(n=0):
        refresh()
        states = [log_status(d)[0] for d in chosen() if installed_version(d)]
        if states and all(s == "loaded" for s in states):
            status.set("Cura loaded Shark Support. In Cura: Extensions > Shark Support.")
            return
        if n < 60:
            root.after(3000, lambda: poll(n + 1))
        else:
            status.set("Cura did not report loading the plugin within 3 minutes. Press Check after Cura is open.")

    def do_start():
        if not progs:
            messagebox.showinfo("Start Cura", "I could not find Cura's program. Start Cura yourself, then press Check.")
            return
        label, argv = progs[0]
        try:
            subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as ex:
            messagebox.showerror("Start Cura", "Could not start %s: %s" % (label, ex))
            return
        status.set("Started %s - waiting for its log to show the plugin loaded..." % label)
        root.after(5000, poll)

    btns = ttk.Frame(top)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text="Install", command=do_install).pack(side="left")
    ttk.Button(btns, text="Start Cura", command=do_start).pack(side="left", padx=6)
    ttk.Button(btns, text="Check", command=refresh).pack(side="left")
    ttk.Button(btns, text="Uninstall", command=do_uninstall).pack(side="left", padx=6)
    ttk.Button(btns, text="Close", command=root.destroy).pack(side="right")
    ttk.Label(top, textvariable=status, wraplength=820, justify="left").pack(anchor="w", pady=(8, 0))
    bar = ttk.Frame(root, padding=(10, 2))
    bar.pack(fill="x", side="bottom")
    ttk.Label(bar, text="v%s - %s   |   Copyright Matthew Armstrong - PolyForm Noncommercial 1.0.0 - no warranty"
              % (VERSION, BUILD_DATE), foreground="#666").pack(anchor="w")
    refresh()
    root.mainloop()
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--cli", action="store_true", help="text mode, no window")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--check", action="store_true", help="text mode: show what Cura's log says")
    ap.add_argument("--version", action="version", version=TITLE)
    a = ap.parse_args(argv)
    if a.cli or a.check or a.uninstall:
        return cli(a)
    try:
        import tkinter  # noqa: F401
    except ImportError:
        print("The installer window needs tkinter, which this Python does not have.")
        if SYSTEM == "Linux":
            print("Fix:  sudo apt install python3-tk     (then run the launcher again)")
        print("Falling back to text mode.\n")
        return cli(a)
    try:
        return gui()
    except Exception as ex:  # noqa: BLE001 - e.g. no display
        print("Could not open the window (%s). Falling back to text mode.\n" % ex)
        return cli(a)


if __name__ == "__main__":
    sys.exit(main())

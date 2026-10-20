#!/bin/sh
# TEST ONLY. Start Cura from source under Xvfb with the stand-ins and the harness, act on the
# harness's requests (screenshots, real mouse clicks with xdotool), print the results.
# usage: CURA_SRC=... URANIUM_SRC=... VENV_PY=... HOME=<throwaway home> STL=<file> run_cura_from_source.sh <seconds> <shot-prefix>
# HOME must be a throwaway folder: Cura writes its settings there. Needs Xvfb, ImageMagick (import), xdotool.
HERE=$(cd "$(dirname "$0")" && pwd)
STUBS=$(mktemp -d); cp "$HERE/stubs_sitecustomize.py" "$STUBS/sitecustomize.py"
OUT=$(mktemp)
DISP=:91
Xvfb $DISP -screen 0 1600x1000x24 +extension GLX >/dev/null 2>&1 &
XP=$!; sleep 2
DISPLAY=$DISP PYTHONPATH="$STUBS:$URANIUM_SRC:$CURA_SRC" SHARK_HARNESS_STL="$STL" timeout "$1" "$VENV_PY" "$CURA_SRC/cura_app.py" > "$OUT" 2>&1 &
CP=$!; i=0; done_lines=0; LASTX=""; LASTY=""
while [ $i -lt "$1" ]; do
  sleep 1; i=$((i+1))
  total=$(grep -c "HARNESS:" "$OUT")
  if [ "$total" -gt "$done_lines" ]; then
    grep "HARNESS:" "$OUT" | sed -n "$((done_lines+1)),${total}p" | sed 's/^.*HARNESS: //' | while read -r cmd a b; do
      case "$cmd" in
        shot) sleep 2; DISPLAY=$DISP import -window root "$2-$a.png" ;;
        click) [ "$a" = "again" ] && { a=$(cat "$OUT.lastx"); b=$(cat "$OUT.lasty"); }
               echo "$a" > "$OUT.lastx"; echo "$b" > "$OUT.lasty"
               DISPLAY=$DISP xdotool mousemove "$a" "$b"; sleep 0.3; DISPLAY=$DISP xdotool click 1 ;;
      esac
    done
    done_lines=$total
  fi
  grep -q "HARNESS: DONE" "$OUT" && { sleep 4; DISPLAY=$DISP import -window root "$2-final.png"; break; }
done
kill $CP 2>/dev/null; sleep 1; kill $XP 2>/dev/null
grep "HARNESS\|Shark Support" "$OUT" | sed 's/^.*\] //'
cp "$OUT" "$2-cura.log" 2>/dev/null

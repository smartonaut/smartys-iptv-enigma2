#!/bin/bash
# Baut das Smartys-IPTV-IPK (Alpha) für Enigma2/OpenATV.
# Das Python-Plugin ist architektur-unabhängig (Architecture: all).
set -e
cd "$(dirname "$0")"

VERSION=$(awk '/^Version:/ {print $2}' CONTROL/control)
PKG="enigma2-plugin-extensions-smartysiptv_${VERSION}_all.ipk"
BUILD="$(mktemp -d)"
PLUGIN_DIR="$BUILD/usr/lib/enigma2/python/Plugins/Extensions/SmartysIPTV"

echo "== Baue $PKG =="

# --- data.tar.gz: Plugin-Dateien -------------------------------------------
mkdir -p "$PLUGIN_DIR"
cp -r plugin/. "$PLUGIN_DIR/"
# Root-Cause-Artefakte ausschließen (funktionierender Box-Zustand)
rm -f "$PLUGIN_DIR/__init__.py"
find "$PLUGIN_DIR" -name '*.pyc' -delete
find "$PLUGIN_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

(cd "$BUILD" && tar czf data.tar.gz usr)

# --- control.tar.gz ---------------------------------------------------------
mkdir -p "$BUILD/ctrl"
cp CONTROL/control "$BUILD/ctrl/control"
# postinst: nach Installation Enigma2 zum Neuladen auffordern
cat > "$BUILD/ctrl/postinst" << 'EOF'
#!/bin/sh
echo "Smartys IPTV installiert. Bitte Enigma2 neu starten (GUI-Neustart)."
exit 0
EOF
chmod 755 "$BUILD/ctrl/postinst"
(cd "$BUILD/ctrl" && tar czf "$BUILD/control.tar.gz" .)

# --- debian-binary ----------------------------------------------------------
printf '2.0\n' > "$BUILD/debian-binary"

# --- IPK (ar-Archiv) --------------------------------------------------------
rm -f "$PKG"
(cd "$BUILD" && ar r "$OLDPWD/$PKG" debian-binary control.tar.gz data.tar.gz)

rm -rf "$BUILD"
echo "== Fertig: $PKG =="
ls -la "$PKG"

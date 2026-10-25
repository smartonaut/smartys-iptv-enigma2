#!/bin/bash
# Veroeffentlichung in einem Durchgang: pruefen, bauen, committen, taggen,
# pushen, Release anlegen, auf den Server legen, Website und Forum aktualisieren.
#
# Aufruf:  ./release.sh 0.5.0 "Kurzbeschreibung"
#
# Abbruch bei JEDEM Fehler (set -e) — ein halb veroeffentlichter Stand ist
# schlimmer als gar keiner, weil Download und Ankuendigung auseinanderlaufen.
set -euo pipefail
cd "$(dirname "$0")"

NUR_PRUEFEN=0
if [ "${1:-}" = "--pruefen" ]; then
    NUR_PRUEFEN=1
    shift
fi

VERSION="${1:-}"
NOTIZ="${2:-}"
if [ -z "$VERSION" ] && [ "$NUR_PRUEFEN" = "0" ]; then
    echo "Aufruf: ./release.sh <version> [kurzbeschreibung]"
    echo "Beispiel: ./release.sh 0.5.0 \"Aufnahmen aus der EPG-Uebersicht\""
    exit 2
fi

ROT=$'\033[31m'; GRUEN=$'\033[32m'; GELB=$'\033[33m'; AUS=$'\033[0m'
ok()   { echo "${GRUEN}  ok${AUS}  $*"; }
warn() { echo "${GELB}warn${AUS}  $*"; }
tot()  { echo "${ROT}FEHL${AUS}  $*"; exit 1; }

echo "== 1) Datenkontrolle vor der Veroeffentlichung =="

# Alles, was ins Repo oder auf eine oeffentliche Seite geht.
QUELLEN=(plugin/ CHANGELOG.md README.md build.sh CONTROL/)
TREFFER=0

pruefe() {
    local muster="$1" erklaerung="$2" dateien="$3"
    local fund
    fund=$(grep -rnE "$muster" $dateien 2>/dev/null \
           | grep -vE "192\.168\.1\.50|benutzer@192\.168\.1\.50|10\.0\.0\.1|127\.0\.0\.1" \
           | head -5) || true
    if [ -n "$fund" ]; then
        echo "${ROT}  GEFUNDEN${AUS}  $erklaerung"
        echo "$fund" | sed 's/^/           /'
        TREFFER=$((TREFFER + 1))
    else
        ok "$erklaerung: keine Treffer"
    fi
}

# Private Netze — die Beispieladresse 192.168.1.50 ist erlaubt und wird oben
# herausgefiltert. Jede andere interne Adresse gehoert nicht ins Repo.
pruefe '192\.168\.[0-9]+\.[0-9]+' "interne IP (192.168.x.x)" "${QUELLEN[*]}"
pruefe '\b10\.[0-9]+\.[0-9]+\.[0-9]+\b' "interne IP (10.x.x.x)" "${QUELLEN[*]}"

# Zugangsdaten
pruefe '(@gmail\.com|@web\.de|@gmx\.|@t-online\.|@telekom\.)' "echte Mailadresse" "${QUELLEN[*]}"
# Nur echte Werte: ein Passwort in Anfuehrungszeichen oder eine lange
# Zeichenkette. "self.password = password" ist Code und kein Fund.
pruefe "(passwor[dt]|kennwort)[A-Za-z_]*\s*[=:]\s*['\"][^'\"]{6,}['\"]" "Passwort als Wert" "${QUELLEN[*]}"
pruefe "(api[_-]?key|secret|token)[A-Za-z_]*\s*[=:]\s*['\"][A-Za-z0-9_\-]{20,}['\"]" "Schluessel/Token als Wert" "${QUELLEN[*]}"
pruefe 'BEGIN (RSA|OPENSSH|PRIVATE) ' "privater Schluessel" "${QUELLEN[*]}"
pruefe '(line\.smartytv\.xyz|[a-z0-9-]+\.smartytv\.xyz)' "Anbieter-Hostname" "${QUELLEN[*]}"

# Persoenliche Dateien, die nie mitkommen duerfen
for datei in config.toml signaturen.json .bruce_gmail_pw .telekom_pw; do
    if find plugin CONTROL debian assets packaging .             -maxdepth 3 -name "$datei" -not -path "./.git/*" 2>/dev/null | grep -q .; then
        tot "$datei liegt im Arbeitsverzeichnis — vor dem Release entfernen"
    fi
done
ok "keine persoenlichen Konfigurationsdateien"

if [ "$TREFFER" -gt 0 ]; then
    echo
    echo "${ROT}Abbruch: $TREFFER Datenfund(e).${AUS}"
    echo "Diese Stellen bereinigen, dann erneut starten."
    exit 1
fi

if [ "$NUR_PRUEFEN" = "1" ]; then
    echo
    echo "Nur geprueft — nichts veroeffentlicht."
    exit 0
fi

echo
echo "== 2) Version =="
IST=$(sed -n 's/^Version: //p' CONTROL/control)
if [ "$IST" != "$VERSION" ]; then
    warn "CONTROL sagt $IST, gewuenscht ist $VERSION"
    sed -i "s|^Version: .*|Version: $VERSION|" CONTROL/control
    ok "CONTROL auf $VERSION gesetzt"
else
    ok "CONTROL steht auf $VERSION"
fi

if ! grep -q "^## \[$VERSION\]" CHANGELOG.md; then
    tot "CHANGELOG.md hat keinen Abschnitt [${VERSION}] — erst schreiben"
fi
ok "CHANGELOG-Abschnitt vorhanden"

echo
echo "== 3) Paket bauen =="
./build.sh >/dev/null 2>&1 || tot "build.sh fehlgeschlagen"
IPK="enigma2-plugin-extensions-smartysiptv_${VERSION}_all.ipk"
[ -f "$IPK" ] || tot "$IPK wurde nicht erzeugt"
ok "$IPK ($(stat -c%s "$IPK") Bytes)"

# Gegenprobe: steht die Version wirklich im Paket?
AUS_PAKET=$(ar p "$IPK" control.tar.gz 2>/dev/null | tar xzO ./control 2>/dev/null \
            | sed -n 's/^Version: //p')
[ "$AUS_PAKET" = "$VERSION" ] || tot "Paket meldet Version '$AUS_PAKET', erwartet '$VERSION'"
ok "Version im Paket geprueft: $AUS_PAKET"

echo
echo "== 4) Git =="
git add -A
if git diff --cached --quiet; then
    warn "keine Aenderungen zu committen"
else
    git -c user.name="Smartys" -c user.email="smartonaut@users.noreply.github.com" \
        commit -q -m "Release $VERSION${NOTIZ:+: $NOTIZ}"
    ok "committet"
fi
git tag -f "v$VERSION"
ok "Tag v$VERSION gesetzt"
git push github master >/dev/null 2>&1 || tot "Push nach github fehlgeschlagen"
git push github "v$VERSION" -f >/dev/null 2>&1 || tot "Tag-Push fehlgeschlagen"
git push origin master >/dev/null 2>&1 || warn "Push zum Hostinger-Remote fehlgeschlagen"
ok "gepusht"

echo
echo "== 5) GitHub-Release =="
if gh release view "v$VERSION" >/dev/null 2>&1; then
    gh release upload "v$VERSION" "$IPK" --clobber >/dev/null 2>&1 \
        && ok "Asset ersetzt"
else
    gh release create "v$VERSION" "$IPK" --title "v$VERSION${NOTIZ:+ — $NOTIZ}" \
        --notes-file <(sed -n "/^## \[$VERSION\]/,/^## \[/p" CHANGELOG.md | head -n -1) \
        >/dev/null 2>&1 || tot "Release anlegen fehlgeschlagen"
    ok "Release angelegt"
fi
# Verifizieren, nicht annehmen
gh release view "v$VERSION" --json assets --jq '.assets[].name' 2>/dev/null \
    | grep -q "$IPK" || tot "Asset fehlt am Release"
ok "Asset am Release nachgeprueft"

echo
echo "== 6) Download-Server =="
scp -q -o ConnectTimeout=8 "$IPK" hostinger:/home/smarty/docker-host/camviewer-dl/data/ \
    || tot "Upload fehlgeschlagen"
ssh -o ConnectTimeout=8 hostinger "cd /home/smarty/docker-host/camviewer-dl/data \
    && cp apps.json apps.json.bak.\$(date +%Y%m%d-%H%M%S) \
    && sed -i 's|enigma2-plugin-extensions-smartysiptv_[0-9.]*_all\.ipk|$IPK|g' apps.json" \
    || tot "apps.json aktualisieren fehlgeschlagen"
LIVE=$(curl -sL --max-time 60 "https://player.smartys.tech/download/enigma2" -o /tmp/_dl.ipk \
       -w "%{http_code}")
[ "$LIVE" = "200" ] || tot "Download antwortet mit HTTP $LIVE"
LIVE_VERSION=$(ar p /tmp/_dl.ipk control.tar.gz 2>/dev/null | tar xzO ./control 2>/dev/null \
               | sed -n 's/^Version: //p')
[ "$LIVE_VERSION" = "$VERSION" ] || tot "Live-Download liefert $LIVE_VERSION statt $VERSION"
ok "Download liefert $LIVE_VERSION"
rm -f /tmp/_dl.ipk

echo
echo "== 7) Website =="
ssh -o ConnectTimeout=8 hostinger "sed -i 's|v[0-9]\+\.[0-9]\+\.[0-9]\+|v$VERSION|g' \
    /home/smarty/docker-host/iptv-backend/site-player/index.html" \
    || tot "Website-Badge fehlgeschlagen"
ssh -o ConnectTimeout=8 hostinger "cd /home/smarty/docker-host/iptv-backend \
    && docker compose up -d --build player-site >/dev/null 2>&1" \
    || tot "Website-Neubau fehlgeschlagen"
sleep 5
curl -s --max-time 15 https://player.smartys.tech/ | grep -q "v$VERSION" \
    || tot "Website zeigt v$VERSION nicht"
ok "Website zeigt v$VERSION"

echo
echo "== 8) Forum =="
if scp -q -o ConnectTimeout=8 ~/.hermes/cache/scratch/forum_release.py \
        hostinger:/tmp/ 2>/dev/null; then
    ssh -o ConnectTimeout=8 hostinger "cd /tmp && VERSION=$VERSION python3 forum_release.py 2>&1 | tail -3" \
        || warn "Forum-Beitrag fehlgeschlagen — bitte manuell nachtragen"
else
    warn "forum_release.py nicht gefunden — Forum-Schritt uebersprungen"
fi

echo
echo "${GRUEN}== Fertig: $VERSION ist ueberall veroeffentlicht ==${AUS}"
echo "  Download: https://player.smartys.tech/download/enigma2"
echo "  Release:  https://github.com/smartonaut/smartys-iptv-enigma2/releases/tag/v$VERSION"
echo "  Forum:    https://forum.smartys.tech/d/13"

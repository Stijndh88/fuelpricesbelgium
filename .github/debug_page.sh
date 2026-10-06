set -x
B=https://petrolprices.economie.fgov.be
curl -sSL -A fuelpricesbelgium "$B/petrolprices?locale=fr" -o app.html; wc -c app.html
head -c 4000 app.html; echo
grep -oiE '(src|href)="[^"]+"' app.html | head -50
for js in $(grep -oiE 'src="[^"]+\.js[^"]*"' app.html | sed -E 's/src="([^"]+)"/\1/' | head -10); do
  case "$js" in http*) u="$js";; /*) u="$B$js";; *) u="$B/petrolprices/$js";; esac
  echo "== JS $u"; curl -sSL "$u" -o s.js; wc -c s.js
  grep -oE '"(/|https?://)[^"]{2,120}"' s.js | grep -iE 'api|price|prix|json|rest|tarif|product' | sort -u | head -40
  grep -oE "'(/|https?://)[^']{2,120}'" s.js | grep -iE 'api|price|prix|json|rest|tarif|product' | sort -u | head -40
done
curl -sSL -A fuelpricesbelgium https://economie.fgov.be/sites/default/files/Files/Energy/prices/Tarifs-officiels-produits-petroliers.pdf -o tarif.pdf; file tarif.pdf
which pdftotext && pdftotext -layout tarif.pdf - | head -150

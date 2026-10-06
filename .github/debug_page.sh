for loc in fr nl; do
curl -sSL -A fuelpricesbelgium "https://petrolprices.economie.fgov.be/petrolprices?locale=$loc" -o app_$loc.html
python - app_$loc.html <<'PY'
import sys
from fuelprices.sources.fod import _TableRows
p=_TableRows(); p.feed(open(sys.argv[1],encoding="utf-8").read())
for r in p.rows: print(r)
PY
done
sed -n 's/.*\(<tbody.*\)/\1/p' app_nl.html | head -c 1500

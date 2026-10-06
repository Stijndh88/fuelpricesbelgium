import re, sys
from html.parser import HTMLParser
html = open(sys.argv[1], encoding="utf-8", errors="replace").read()
print("bytes", len(html), "tables", html.lower().count("<table"), "iframes", html.lower().count("<iframe"))
for m in re.finditer(r'(href|src)="([^"]+\.(xlsx|csv|pdf|json)[^"]*)"', html, re.I):
    print("LINK", m.group(2))
for m in re.finditer(r'<(iframe|script)[^>]*src="([^"]+)"', html, re.I):
    print("SRC", m.group(2))
class T(HTMLParser):
    def __init__(s): super().__init__(); s.t=[]; s.skip=0
    def handle_starttag(s,tag,a):
        if tag in("script","style"): s.skip+=1
    def handle_endtag(s,tag):
        if tag in("script","style"): s.skip-=1
    def handle_data(s,d):
        if not s.skip and d.strip(): s.t.append(d.strip())
p=T(); p.feed(html)
text="\n".join(p.t)
i=max(text.lower().find("e10"),0)
print("----TEXT around E10----"); print(text[max(i-1500,0):i+2500])
for kw in ("diesel","€/l","prix maximum"):
    j=html.lower().find(kw); print("----HTML around",kw,j); print(html[max(j-600,0):j+900] if j>=0 else "")

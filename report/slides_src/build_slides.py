"""Build report/slides.html from slides.template.html with every screenshot and the
architecture diagram embedded, so the single file still works when emailed.
Run from the project root:  python3 report/slides_src/build_slides.py
"""
import base64
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent


def img(m):
    data = (REPORT / "img" / m.group(1)).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def svg(_m):
    html = (REPORT / "report.html").read_text()
    return re.search(r"<svg.*?</svg>", html, re.S).group(0)  # same diagram as the report


out = (HERE / "slides.template.html").read_text()
out = re.sub(r"\{\{img:([\w.-]+)\}\}", img, out)
out = re.sub(r"\{\{svg:arch\}\}", svg, out)
(REPORT / "slides.html").write_text(out)
print(f"wrote {REPORT / 'slides.html'} ({len(out) / 1024:.0f} KB)")

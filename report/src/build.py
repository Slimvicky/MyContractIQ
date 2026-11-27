"""Build the shareable, single-file report.html and slides.html.

Every screenshot (and, for the slides, the architecture diagram) is embedded in the
output, so each file works on its own when emailed. Edit the templates in this folder,
then run from the project root:  python3 report/src/build.py
"""
import base64
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent
REPORT = SRC.parent


def _img(m: re.Match) -> str:
    data = (REPORT / "img" / m.group(1)).read_bytes()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def build(template: str, out_name: str, svg: str) -> None:
    html = (SRC / template).read_text()
    html = re.sub(r"\{\{img:([\w.-]+)\}\}", _img, html)                    # slides placeholders
    html = re.sub(r'src="img/([\w.-]+)"', lambda m: f'src="{_img(m)}"', html)  # report <img> tags
    html = html.replace("{{svg:arch}}", svg)
    assert 'src="img/' not in html and "{{" not in html, f"unresolved asset in {out_name}"
    (REPORT / out_name).write_text(html)
    print(f"wrote report/{out_name} ({len(html) / 1024:.0f} KB)")


if __name__ == "__main__":
    report_src = (SRC / "report.template.html").read_text()
    arch_svg = re.search(r"<svg.*?</svg>", report_src, re.S).group(0)  # same diagram in both
    build("report.template.html", "report.html", arch_svg)
    build("slides.template.html", "slides.html", arch_svg)

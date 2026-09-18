#!/usr/bin/env python3
"""Build a standalone, accessible HTML edition of the Marketteo CRM manual."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import unicodedata
from pathlib import Path


H2_PATTERN = re.compile(r"^## (.+)$")
H3_PATTERN = re.compile(r"^### (.+)$")
IMAGE_PATTERN = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
CAPTION_PATTERN = re.compile(r"^\*(Figure\s+\d+\s+—.+)\*$")
NUMBERED_PATTERN = re.compile(r"^\d+\. (.+)$")


CSS = """
:root { --ink:#17251f; --green:#173f35; --green-2:#1f5a49; --mint:#d9eee3; --cream:#f8f2e7; --gold:#e3a829; --paper:#fffdf9; --line:#d6e1dc; --muted:#63716a; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; background:#eff5f1; color:var(--ink); font:16px/1.58 Inter, Aptos, Calibri, Arial, sans-serif; }
a { color:var(--green-2); }
.skip-link { position:absolute; left:-999px; top:auto; width:1px; height:1px; overflow:hidden; }
.skip-link:focus { left:1rem; top:1rem; width:auto; height:auto; z-index:20; padding:.65rem .85rem; background:#fff; border:2px solid var(--green); border-radius:.4rem; }
.site-header { background:linear-gradient(125deg, var(--green), #245f4d); color:#fff; padding:2.5rem max(1.25rem, calc((100vw - 1180px) / 2)); }
.brand { display:flex; gap:.75rem; align-items:center; font-size:.82rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; }
.brand-mark { display:grid; place-items:center; width:2.15rem; height:2.15rem; border-radius:.55rem; background:var(--gold); color:var(--green); font-size:1.1rem; }
.site-header h1 { max-width:760px; margin:1.25rem 0 .4rem; font-size:clamp(2rem, 4vw, 3.45rem); line-height:1.08; }
.site-header p { max-width:760px; margin:0; color:#dceee5; }
.meta { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.35rem; }
.meta span { padding:.28rem .62rem; border:1px solid rgba(255,255,255,.34); border-radius:999px; color:#fff; font-size:.88rem; }
.layout { display:grid; grid-template-columns:250px minmax(0, 860px); gap:2rem; max-width:1180px; margin:0 auto; padding:2rem 1.25rem 4rem; }
.sidebar { align-self:start; position:sticky; top:1rem; padding:1.1rem; background:#fff; border:1px solid var(--line); border-radius:.85rem; box-shadow:0 .4rem 1.4rem rgba(23,63,53,.06); }
.sidebar strong { display:block; margin-bottom:.6rem; color:var(--green); font-size:.82rem; letter-spacing:.08em; text-transform:uppercase; }
.sidebar ol { margin:0; padding-left:1.2rem; }
.sidebar li { margin:.35rem 0; }
.sidebar a { text-decoration:none; font-size:.91rem; }
.manual { min-width:0; padding:clamp(1.25rem, 4vw, 3.25rem); background:var(--paper); border:1px solid var(--line); border-radius:1rem; box-shadow:0 .5rem 1.8rem rgba(23,63,53,.08); }
.manual h2 { scroll-margin-top:1rem; margin:2.6rem 0 .65rem; color:var(--green-2); font-size:1.7rem; line-height:1.2; }
.manual h2:first-child { margin-top:0; }
.manual h3 { scroll-margin-top:1rem; margin:1.75rem 0 .5rem; color:var(--green); font-size:1.2rem; line-height:1.3; }
.manual p { margin:.65rem 0; }
.manual ol, .manual ul { margin:.75rem 0 1rem; padding-left:1.45rem; }
.manual li { margin:.35rem 0; }
.manual code { padding:.08rem .3rem; border-radius:.25rem; background:var(--cream); color:var(--green); font: .88em ui-monospace, Consolas, monospace; }
.manual strong { color:#132f27; }
.note { margin:1.1rem 0; padding:.9rem 1rem; border-left:4px solid var(--gold); background:var(--cream); border-radius:0 .45rem .45rem 0; }
figure { margin:1.5rem auto; text-align:center; }
figure img { display:block; max-width:100%; height:auto; margin:auto; border:1px solid var(--line); border-radius:.65rem; box-shadow:0 .35rem 1rem rgba(23,63,53,.1); }
figcaption { margin-top:.45rem; color:var(--muted); font-size:.9rem; font-style:italic; }
.table-wrap { overflow-x:auto; margin:1rem 0 1.4rem; }
table { width:100%; border-collapse:collapse; font-size:.93rem; }
th, td { padding:.62rem .7rem; border:1px solid var(--line); vertical-align:top; text-align:left; }
th { background:var(--mint); color:#102c23; font-weight:750; }
tr:nth-child(even) td { background:#fbfdfb; }
.site-footer { max-width:1180px; margin:0 auto; padding:0 1.25rem 2.5rem; color:var(--muted); font-size:.9rem; }
@media (max-width: 850px) { .layout { grid-template-columns:1fr; padding-top:1rem; } .sidebar { position:static; } .sidebar ol { columns:2; } }
@media (max-width: 540px) { .site-header { padding:1.75rem 1.25rem; } .manual { padding:1.25rem; } .sidebar ol { columns:1; } th, td { min-width:8rem; } }
@media print { body { background:#fff; font-size:11pt; } .site-header { padding:0 0 1rem; background:#fff; color:#000; } .site-header p, .brand, .meta { color:#000; } .brand-mark { display:none; } .layout { display:block; max-width:none; margin:0; padding:0; } .sidebar { display:none; } .manual { border:0; box-shadow:none; padding:0; } .site-footer { display:none; } a { color:#000; text-decoration:none; } }
"""


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", normalized)) or "section"


def inline(value: str) -> str:
    escaped = html.escape(value, quote=False)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def parse_metadata(markdown: str) -> dict[str, str]:
    result = {}
    for label in ("Version", "État", "Date de référence", "Public"):
        match = re.search(rf"\*\*{re.escape(label)}\s*:\*\*\s*(.+)", markdown)
        if match:
            result[label] = match.group(1).strip()
    return result


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        rows.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
        index += 1
    if len(rows) > 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1]):
        rows.pop(1)
    return rows, index


def render_table(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    head = "".join(f"<th scope=\"col\">{inline(cell)}</th>" for cell in rows[0])
    body = "".join(
        "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>"
        for row in rows[1:]
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_body(markdown: str) -> str:
    lines = markdown.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith("## 1.")), 0)
    parts: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        h2 = H2_PATTERN.match(line)
        h3 = H3_PATTERN.match(line)
        image = IMAGE_PATTERN.match(line)
        if h2:
            title = h2.group(1)
            parts.append(f'<h2 id="{slugify(title)}">{inline(title)}</h2>')
            index += 1
            continue
        if h3:
            title = h3.group(1)
            parts.append(f'<h3 id="{slugify(title)}">{inline(title)}</h3>')
            index += 1
            continue
        if image:
            alt, source = image.groups()
            caption = ""
            if index + 1 < len(lines):
                caption_match = CAPTION_PATTERN.match(lines[index + 1].strip())
                if caption_match:
                    caption = caption_match.group(1)
                    index += 1
            parts.append(
                f'<figure><img src="{html.escape(source, quote=True)}" alt="{html.escape(alt, quote=True)}" loading="lazy">'
                + (f"<figcaption>{inline(caption)}</figcaption>" if caption else "")
                + "</figure>"
            )
            index += 1
            continue
        if line.startswith("|"):
            rows, index = parse_table(lines, index)
            parts.append(render_table(rows))
            continue
        if line.startswith("> "):
            parts.append(f'<aside class="note">{inline(line[2:])}</aside>')
            index += 1
            continue
        ordered = NUMBERED_PATTERN.match(line)
        if ordered:
            items = []
            while index < len(lines):
                match = NUMBERED_PATTERN.match(lines[index].strip())
                if not match:
                    break
                items.append(f"<li>{inline(match.group(1))}</li>")
                index += 1
            parts.append("<ol>" + "".join(items) + "</ol>")
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(f"<li>{inline(lines[index].strip()[2:])}</li>")
                index += 1
            parts.append("<ul>" + "".join(items) + "</ul>")
            continue
        paragraph = [line]
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate or H2_PATTERN.match(candidate) or H3_PATTERN.match(candidate) or IMAGE_PATTERN.match(candidate):
                break
            if candidate.startswith(("|", "> ", "- ")) or NUMBERED_PATTERN.match(candidate):
                break
            paragraph.append(candidate)
            index += 1
        parts.append(f"<p>{inline(' '.join(paragraph))}</p>")
    return "\n".join(parts)


def build(source: Path, output: Path) -> None:
    markdown = source.read_text(encoding="utf-8")
    metadata = parse_metadata(markdown)
    title = markdown.splitlines()[0].lstrip("# ").strip()
    headings = [match.group(1) for line in markdown.splitlines() if (match := H2_PATTERN.match(line))]
    navigation = "".join(f'<li><a href="#{slugify(heading)}">{inline(heading)}</a></li>' for heading in headings)
    meta = "".join(f"<span>{html.escape(key)} : {inline(value)}</span>" for key, value in metadata.items() if key != "Public")
    public = html.escape(metadata.get("Public", "Utilisateurs de Marketteo CRM"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        f"""<!doctype html>
<html lang=\"fr-CA\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta name=\"description\" content=\"Manuel utilisateur de Marketteo CRM\">
  <title>{html.escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  <a class=\"skip-link\" href=\"#contenu\">Aller au contenu</a>
  <header class=\"site-header\">
    <div class=\"brand\"><span class=\"brand-mark\" aria-hidden=\"true\">M</span> Marketteo CRM</div>
    <h1>{html.escape(title)}</h1>
    <p>Guide pratique destiné à {public}.</p>
    <div class=\"meta\">{meta}</div>
  </header>
  <div class=\"layout\">
    <nav class=\"sidebar\" aria-label=\"Sommaire\"><strong>Sommaire</strong><ol>{navigation}</ol></nav>
    <main class=\"manual\" id=\"contenu\">{render_body(markdown)}</main>
  </div>
  <footer class=\"site-footer\">Marketteo CRM · {html.escape(metadata.get('Version', 'Manuel utilisateur'))} · Version HTML autonome.</footer>
</body>
</html>
""",
        encoding="utf-8",
    )


def copy_images(source: Path, output: Path) -> None:
    source_images = source.parent / "images"
    destination_images = output.parent / "images"
    if not source_images.exists():
        return
    if source_images.resolve() == destination_images.resolve():
        return
    shutil.copytree(source_images, destination_images, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--copy-images",
        action="store_true",
        help="Publie les captures du manuel à côté de l'édition HTML.",
    )
    args = parser.parse_args()
    build(args.source, args.output)
    if args.copy_images:
        copy_images(args.source, args.output)


if __name__ == "__main__":
    main()

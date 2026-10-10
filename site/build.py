#!/usr/bin/env python3
"""Build the System Design Primer learning site without a server."""
from __future__ import annotations

import html
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
OUT = ROOT / "_site"
GITHUB = "https://github.com/RobinHoodO/system-design-primer/blob/master/"
UPSTREAM = "https://github.com/donnemartin/system-design-primer"
UNRESOLVED_ANCHORS = set()


def esc(value):
    return html.escape(str(value), quote=True)


def github_anchor(text, used):
    """GitHub's visible heading text becomes a stable fragment identifier."""
    cleaned = "".join(c for c in text.lower() if c.isalnum() or c in " -_")
    slug = re.sub(r" +", "-", cleaned).strip("-")
    count = used[slug]
    used[slug] += 1
    return slug if count == 0 else f"{slug}-{count}"


def plain_heading(markdown):
    markdown = re.sub(r"!?(?:\[([^]]*)\]\([^)]*\))", r"\1", markdown)
    markdown = re.sub(r"`([^`]*)`", r"\1", markdown)
    markdown = re.sub(r"[*_~]", "", markdown)
    return html.unescape(markdown).strip()


def heading_data(source):
    used, rows = defaultdict(int), []
    for line_no, line in enumerate(source.splitlines()):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if match:
            text = plain_heading(match.group(2))
            rows.append({"line": line_no, "level": len(match.group(1)), "text": text,
                         "id": github_anchor(text, used)})
    return rows


def markdown_renderer(source, headings, line_offset=0):
    md = MarkdownIt("commonmark", {"html": True}).enable("table").enable("strikethrough")
    ids = {row["line"] - line_offset: row["id"] for row in headings}
    original = md.renderer.rules.get("heading_open")

    def heading_open(tokens, idx, options, env):
        token = tokens[idx]
        if token.map and token.map[0] in ids:
            token.attrSet("id", ids[token.map[0]])
        return original(tokens, idx, options, env) if original else md.renderer.renderToken(tokens, idx, options, env)

    md.renderer.rules["heading_open"] = heading_open
    return md.render(source)


def relative(target, depth):
    if target.startswith(("http://", "https://", "mailto:", "data:")) or target.startswith("#"):
        return target
    return "../" * depth + target


def solution_slug(value):
    value = value.strip("/")
    bits = value.split("/")
    if "solutions" in bits:
        pos = bits.index("solutions")
        if len(bits) > pos + 2:
            return bits[pos + 2].replace("_", "-")
    return None


def target_for_anchor(anchor, anchor_topics, depth):
    if anchor in {"system-design-interview-questions-with-solutions", "object-oriented-design-interview-questions-with-solutions"}:
        return f"{relative('index.html', depth)}#solutions"
    if anchor == "appendix" and "__appendix__" in anchor_topics:
        return relative(f"topics/{anchor_topics['__appendix__'][0]}.html", depth)
    item = anchor_topics.get(anchor)
    if not item:
        UNRESOLVED_ANCHORS.add(anchor)
        return f"{UPSTREAM}#{anchor}"
    slug, topic_anchor = item
    page = relative(f"topics/{slug}.html", depth)
    return page if anchor == topic_anchor else f"{page}#{anchor}"


def rewrite_url(url, depth, anchor_topics, solution_slugs, current_solution=None, is_image=False):
    """Rewrite primer links once, after markdown rendering. ponytail: regex HTML attrs are enough here."""
    url = html.unescape(url)
    if url.startswith(("data:", "mailto:")):
        return url
    parts = urlsplit(url)
    frag = unquote(parts.fragment)
    path = unquote(parts.path)
    is_upstream = parts.netloc == "github.com" and path.startswith("/donnemartin/system-design-primer")
    if not parts.scheme and (not path or path == "README.md" or path.endswith("/README.md")) and frag:
        return target_for_anchor(frag, anchor_topics, depth)
    if is_upstream and frag and ("README.md" in path or "/blob/" in path or path.rstrip("/").endswith("system-design-primer")):
        return target_for_anchor(frag, anchor_topics, depth)
    repo_path = ""
    if is_upstream:
        repo_path = re.sub(r"^/donnemartin/system-design-primer/(?:blob|tree)/[^/]+/?", "", path).lstrip("/")
    elif not parts.scheme:
        repo_path = path.lstrip("./")
    sol = solution_slug(repo_path)
    if sol and sol in solution_slugs:
        return relative(f"solutions/{sol}.html", depth) + (f"#{frag}" if frag else "")
    if is_image and not parts.scheme:
        if repo_path.startswith("images/"):
            return relative(repo_path, depth)
        if current_solution and repo_path.endswith(".png") and "/" not in repo_path:
            return relative(f"images/solutions/{current_solution}/{repo_path}", depth)
    if parts.scheme:
        return url
    if not path and frag:
        return target_for_anchor(frag, anchor_topics, depth)
    if repo_path:
        return GITHUB + repo_path + (f"#{frag}" if frag else "")
    return url


def rewrite_html(markup, depth, anchor_topics, solution_slugs, current_solution=None):
    def attr(match):
        key, quote, value = match.groups()
        return f"{key}={quote}{esc(rewrite_url(value, depth, anchor_topics, solution_slugs, current_solution, key == 'src'))}{quote}"
    markup = re.sub(r"\b(href|src)=(['\"])(.*?)\2", attr, markup, flags=re.I)
    markup = re.sub(r"<a\b([^>]*\bhref=['\"]https?://[^>]+)", r"<a\1 rel=\"noopener\"", markup, flags=re.I)
    return markup


def page(title, body, depth=0, landing=False, counts=None):
    prefix = "../" * depth
    tabs = [("overview", "Overview"), ("topics", f"Topics {counts['topics']}"),
            ("solutions", f"Solutions {counts['solutions']}"), ("diagrams", f"Diagrams {counts['diagrams']}")]
    if landing:
        nav = "".join(f'<button class="tab" role="tab" id="tab-{key}" aria-controls="{key}" data-tab="{key}">{esc(label)}</button>' for key, label in tabs)
    else:
        nav = "".join(f'<a class="tab" href="{prefix}index.html#{key}">{esc(label)}</a>' for key, label in tabs)
    footer = ('<footer class="footer shell"><p>Text and images from the <a href="https://github.com/donnemartin/system-design-primer" rel="noopener">System Design Primer by Donne Martin</a>, licensed <a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>. This site splits it into linked pages and adds plain-English summaries.</p><a class="top-link" href="#top">Top ↑</a></footer>')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="darkreader-lock"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="light dark"><meta name="description" content="A learning path through System Design Primer."><title>{esc(title)} · Thrivbe Lab</title><link rel="stylesheet" href="{prefix}assets/site.css"></head>
<body><a class="skip-link" href="#main">Skip to content</a><header class="masthead" id="top"><div class="shell"><a class="brand" href="{prefix}index.html#overview"><span class="brand-mark">THRIVBE / LAB</span><span class="brand-name">System Design Primer</span></a><nav class="tabs" role="tablist" aria-label="Sections">{nav}</nav><button class="theme-btn" id="themeBtn" type="button" aria-label="Switch colour theme">◐ Auto</button></div></header><main id="main">{body}</main>{footer}<script src="{prefix}assets/site.js"></script></body></html>'''


def diagram_info(path):
    source = path.read_text()
    title = re.search(r"<title>(.*?)</title>", source, re.S)
    boxes, cards = [], []
    for card in re.finditer(r'<article\b[^>]*\bid="(box-[^"]+)"[^>]*>(.*?)</article>', source, re.S):
        name = re.search(r"<h2[^>]*>(.*?)</h2>", card.group(2), re.S)
        label = re.sub(r"<[^>]+>", "", name.group(1)).strip() if name else card.group(1)
        boxes.append((card.group(1), label))
        cards.append({"id": card.group(1), "name": label, "links": links_from_html(card.group(2))})
    return {"title": re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else path.stem.replace("-", " ").title(), "boxes": boxes, "cards": cards, "source": source}


def topic_sections(readme, headings, topics):
    by_title = {t["heading"]: t for t in topics}
    rows = []
    for index, head in enumerate(headings):
        topic = by_title.get(head["text"])
        if not topic:
            continue
        end_line = len(readme.splitlines())
        for later in headings[index + 1:]:
            if later["level"] <= head["level"]:
                end_line = later["line"]
                break
        rows.append((topic["slug"], head, end_line))
    return {slug: (head, end) for slug, head, end in rows}


def solution_inventory():
    result = []
    for kind, folder in (("System design", ROOT / "solutions/system_design"), ("Object-oriented design", ROOT / "solutions/object_oriented_design")):
        for path in sorted(folder.iterdir()):
            if not path.is_dir() or path.name == "template":
                continue
            slug = path.name.replace("_", "-")
            readme = path / "README.md"
            note = next(path.glob("*.ipynb"), None)
            source = readme.read_text() if readme.exists() else ""
            if source:
                title = next((plain_heading(x[2:]) for x in source.splitlines() if x.startswith("# ")), path.name.replace("_", " ").title())
            else:
                notebook = json.loads(note.read_text())
                title = next(("".join(c.get("source", [])).lstrip("# ").strip() for c in notebook["cells"] if c["cell_type"] == "markdown" and "".join(c.get("source", [])).lstrip().startswith("#")), path.name.replace("_", " ").title())
            result.append({"slug": slug, "kind": kind, "path": path, "readme": readme if readme.exists() else None, "notebook": note, "title": title})
    return result


def notebook_html(path, anchor_topics, solution_slugs):
    parts = []
    for cell in json.loads(path.read_text())["cells"]:
        text = "".join(cell.get("source", []))
        if cell["cell_type"] == "markdown":
            parts.append(rewrite_html(markdown_renderer(text, heading_data(text)), 1, anchor_topics, solution_slugs))
        elif cell["cell_type"] == "code":
            parts.append(f'<pre><code class="language-python">{esc(text)}</code></pre>')
    return "\n".join(parts)


def links_from_html(markup, current_file=""):
    return re.findall(r"\bhref=['\"]([^'\"]+)", markup, re.I)


def unique_rows(rows):
    """Keep relationship evidence in source order without repeated destinations."""
    seen, result = set(), []
    for row in rows:
        if row not in seen:
            seen.add(row)
            result.append(row)
    return result


def readme_images(readme, headings, anchor_topics, topic_by_slug, solution_slugs):
    """Collect markdown and HTML images in README order, deduping by source."""
    occurrences = []
    markdown = re.compile(r"!\[([^]]*)\]\(([^ )]+)(?:\s+[^)]*)?\)")
    html_image = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>', re.I)
    lines = readme.splitlines()
    current = None
    recent_solution = (None, -10)
    heads_by_line = {head["line"]: head for head in headings}
    for line_no, line in enumerate(lines):
        current = heads_by_line.get(line_no, current)
        solution_links = [solution_slug(path) for path in re.findall(r"\]\(([^ )#]+)(?:#[^)]+)?\)", line)]
        linked = next((slug for slug in solution_links if slug in solution_slugs), None)
        if linked:
            recent_solution = (linked, line_no)
        nearby_solution = recent_solution[0] if line_no - recent_solution[1] <= 3 else None
        for match in markdown.finditer(line):
            occurrences.append((match.start() + line_no * 1_000_000, match.group(2), match.group(1), current, nearby_solution))
        for match in html_image.finditer(line):
            alt = re.search(r'\balt=["\']([^"\']*)["\']', match.group(0), re.I)
            occurrences.append((match.start() + line_no * 1_000_000, match.group(1), alt.group(1) if alt else "", current, nearby_solution))

    images, by_source = [], {}
    for _, src, alt, heading, linked_solution in sorted(occurrences):
        if src not in by_source:
            owner = anchor_topics.get(heading["id"]) if heading else None
            by_source[src] = {"src": src, "alt": alt, "heading": heading, "owner": owner, "solution": linked_solution}
            images.append(by_source[src])
        elif linked_solution:
            # The same preview can appear earlier in the README before its solution card.
            by_source[src]["solution"] = linked_solution
    return images


def build():
    UNRESOLVED_ANCHORS.clear()
    config = json.loads((SITE / "links.json").read_text())
    topics = config["topics"]
    solutions = solution_inventory()
    solution_slugs = {item["slug"] for item in solutions}
    readme = (ROOT / "README.md").read_text()
    readme_heads = heading_data(readme)
    sections = topic_sections(readme, readme_heads, topics)
    topic_by_slug = {t["slug"]: t for t in topics}
    anchor_topics = {}
    for slug, (head, end) in sections.items():
        for item in readme_heads:
            if head["line"] <= item["line"] < end:
                anchor_topics[item["id"]] = (slug, head["id"])
    appendix_heading = next((head for head in readme_heads if head["id"] == "appendix"), None)
    if appendix_heading:
        first_appendix_topic = next((slug for slug, (head, _) in sections.items() if head["line"] > appendix_heading["line"]), None)
        if first_appendix_topic:
            anchor_topics["__appendix__"] = (first_appendix_topic, "")
    diagrams = {p.stem: diagram_info(p) for p in sorted((SITE / "diagrams").glob("*.html"))}
    solution_by_slug = {item["slug"]: item for item in solutions}
    counts = {"topics": len(topics), "solutions": len(solutions), "diagrams": len(diagrams)}

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "topics").mkdir(parents=True)
    (OUT / "solutions").mkdir()
    (OUT / "diagrams").mkdir()
    shutil.copytree(ROOT / "images", OUT / "images")
    shutil.copytree(SITE / "assets", OUT / "assets")
    for info in solutions:
        target = OUT / "images/solutions" / info["slug"]
        target.mkdir(parents=True, exist_ok=True)
        for png in info["path"].glob("*.png"):
            shutil.copy2(png, target / png.name)
    for path in (SITE / "diagrams").glob("*.html"):
        shutil.copy2(path, OUT / "diagrams" / path.name)

    # Collect diagram and solution relationship evidence from actual link targets.
    diagrams_for_topic = defaultdict(list)
    for key, info in diagrams.items():
        for card in info["cards"]:
            for href in card["links"]:
                match = re.search(r"topics/([\w-]+)\.html", href)
                if match:
                    diagrams_for_topic[match.group(1)].append((key, card["id"], card["name"]))
    solution_topic_links = defaultdict(lambda: defaultdict(list))
    solution_rendered = {}
    for sol in solutions:
        if sol["readme"]:
            raw = sol["readme"].read_text()
            rendered = markdown_renderer(raw, heading_data(raw))
            rendered = rewrite_html(rendered, 1, anchor_topics, solution_slugs, sol["slug"])
        else:
            rendered = notebook_html(sol["notebook"], anchor_topics, solution_slugs)
        solution_rendered[sol["slug"]] = rendered
        for href in links_from_html(rendered):
            match = re.search(r"topics/([\w-]+)\.html(?:#([^\"']+))?", href)
            if match and match.group(1) in topic_by_slug:
                anchor = match.group(2) or ""
                rows = solution_topic_links[match.group(1)][sol["slug"]]
                if anchor not in rows:
                    rows.append(anchor)

    topic_html = {}
    original_by_topic = {}
    for slug, (head, end) in sections.items():
        original_by_topic[slug] = rewrite_html(
            markdown_renderer("\n".join(readme.splitlines()[head["line"]:end]), readme_heads, head["line"]),
            1, anchor_topics, solution_slugs)
    for position, topic in enumerate(topics):
        slug = topic["slug"]
        head, end = sections[slug]
        lines = readme.splitlines()
        original = "\n".join(lines[head["line"]:end])
        original_html = original_by_topic[slug]
        sub = [row for row in readme_heads if head["line"] < row["line"] < end and row["level"] in (head["level"] + 1, head["level"] + 2)]
        hero_rows = []
        for box, dest in config.get("hero_boxes", {}).items():
            dest_slug = dest.removeprefix("solution:").split("#")[0]
            if dest_slug == slug:
                label = next((name for ident, name in diagrams["hero"]["boxes"] if ident == box), box)
                hero_rows.append((f"../diagrams/hero.html#{box}", f"Hero diagram › {label}"))
        diagram_rows, seen_diagrams = [], {"hero"} if hero_rows else set()
        for key, box_id, box_name in diagrams_for_topic[slug]:
            if key in seen_diagrams:
                continue
            seen_diagrams.add(key)
            short_title = "Hero diagram" if key == "hero" else solution_by_slug.get(key, {}).get("title", diagrams[key]["title"])
            diagram_rows.append((f"../diagrams/{key}.html#{box_id}", f"{short_title} › {box_name}"))
        diagram_rows = unique_rows(diagram_rows)
        solution_rows = []
        for sol in solutions:
            anchors = solution_topic_links[slug].get(sol["slug"])
            if anchors is None:
                continue
            section_links = []
            for anchor in dict.fromkeys(anchor for anchor in anchors if anchor):
                text = next((head["text"] for head in readme_heads if head["id"] == anchor), anchor)
                section_links.append((f"#{anchor}", text))
            solution_rows.append((f"../solutions/{sol['slug']}.html", sol["title"], section_links))
        related = []
        for other_slug, markup in original_by_topic.items():
            if re.search(rf'href="(?:\.\./)?topics/{re.escape(slug)}\.html(?:#.*?)?"', markup):
                related.append((f"{other_slug}.html", topic_by_slug[other_slug]["title"]))
        def backlink(label, entries):
            entries = unique_rows(entries)
            return "" if not entries else f'<section class="backlinks"><h2>{label}</h2><div class="chips">' + "".join(f'<a class="chip" href="{href}">{esc(text)}</a>' for href, text in entries) + "</div></section>"

        def solution_backlink(entries):
            if not entries:
                return ""
            rows = []
            for href, title, sections in entries:
                detail = ""
                if sections:
                    links = "".join(f'<li><a href="{section_href}">{esc(section_title)}</a></li>' for section_href, section_title in sections)
                    detail = f'<details class="backlink-sections"><summary>Uses {len(sections)} sections</summary><ul>{links}</ul></details>'
                rows.append(f'<div class="backlink-row"><a class="chip" href="{href}">{esc(title)}</a>{detail}</div>')
            return '<section class="backlinks"><h2>Used in solutions</h2><div class="backlink-rows">' + "".join(rows) + "</div></section>"
        nav = "<nav class=\"page-nav\">" + (f'<a href="{topics[position-1]["slug"]}.html">← {esc(topics[position-1]["title"])}</a>' if position else "") + (f'<a href="{topics[position+1]["slug"]}.html">{esc(topics[position+1]["title"])} →</a>' if position + 1 < len(topics) else "") + "</nav>"
        body = f'''<section class="page-hero shell"><p class="breadcrumb"><a href="../index.html#topics">Topics</a> › {esc(topic['group'])} › {esc(topic['title'])}</p><h1>{esc(topic['title'])}</h1><aside class="summary-card"><div><strong>What it is</strong><p>{esc(topic['summary']['what'])}</p></div><div><strong>Its job</strong><p>{esc(topic['summary']['job'])}</p></div><div><strong>The trade-off</strong><p>{esc(topic['summary']['tradeoff'])}</p></div></aside></section><section class="content shell">{'<nav class="on-page"><h2>On this page</h2><ul>' + ''.join(f'<li><a href="#{row["id"]}">{esc(row["text"])}</a></li>' for row in sub) + '</ul></nav>' if sub else ''}{backlink('In the diagrams', hero_rows + diagram_rows)}{solution_backlink(solution_rows)}{backlink('Linked from other topics', related)}<section class="original"><h2>Original text</h2>{original_html}</section>{nav}</section>'''
        topic_html[slug] = page(topic["title"], body, 1, counts=counts)

    # A second pass makes topic-to-topic evidence complete, including forward links.
    for slug, markup in topic_html.items():
        (OUT / "topics" / f"{slug}.html").write_text(markup)

    for sol in solutions:
        markup = solution_rendered[sol["slug"]]
        used = []
        for href in links_from_html(markup):
            match = re.search(r"topics/([\w-]+)\.html(#[^\"']+)?", href)
            if match and match.group(1) in topic_by_slug:
                key = match.group(1) + (match.group(2) or "")
                if key not in {x[0] for x in used}:
                    label = topic_by_slug[match.group(1)]["title"]
                    if match.group(2):
                        anchor = match.group(2)[1:]
                        label += " › " + next((h["text"] for h in readme_heads if h["id"] == anchor), anchor)
                    used.append((key, label))
        used_by_topic = defaultdict(list)
        for key, label in used:
            topic_slug, _, anchor = key.partition("#")
            used_by_topic[topic_slug]
            if anchor:
                subtopic = next((head["text"] for head in readme_heads if head["id"] == anchor), anchor)
                if (anchor, subtopic) not in used_by_topic[topic_slug]:
                    used_by_topic[topic_slug].append((anchor, subtopic))
        topic_order = {topic["slug"]: index for index, topic in enumerate(topics)}
        topic_groups = []
        for topic_slug in sorted(used_by_topic, key=lambda item: topic_order[item]):
            subtopic_chips = "".join(f'<a class="chip" href="../topics/{topic_slug}.html#{anchor}">{esc(label)}</a>' for anchor, label in used_by_topic[topic_slug])
            topic_groups.append(f'<div class="topic-use"><a class="topic-use-name" href="../topics/{topic_slug}.html">{esc(topic_by_slug[topic_slug]["title"])}</a><div class="chips">{subtopic_chips}</div></div>')
        chips = "".join(topic_groups)
        diagram = diagrams.get(sol["slug"])
        if diagram:
            visual = f'<iframe class="diagram-frame" src="../diagrams/{sol["slug"]}.html" title="{esc(diagram["title"])}"></iframe>'
        else:
            main_image = sol["path"] / f'{sol["path"].name}.png'
            visual = f'<img class="solution-image" src="../images/solutions/{sol["slug"]}/{main_image.name}" alt="Diagram for {esc(sol["title"])}">' if main_image.exists() else ""
        body = f'<section class="page-hero shell"><p class="breadcrumb"><a href="../index.html#solutions">Solutions</a> › {esc(sol["kind"])}</p><h1>{esc(sol["title"])}</h1>{"<section class=\"topics-used\"><h2>Topics used</h2><div class=\"chips\">" + chips + "</div></section>" if chips else ""}</section><section class="content shell">{visual}<section class="original"><h2>Original text</h2>{markup}</section></section>'
        (OUT / "solutions" / f'{sol["slug"]}.html').write_text(page(sol["title"], body, 1, counts=counts))

    # Landing page: steps come from hero's real SVG links, not a separate hand list.
    step_rows = defaultdict(list)
    hero_source = diagrams["hero"]["source"]
    for group in re.finditer(r'<g\b[^>]*data-motion-item[^>]*data-step="(\d+)"[^>]*>(.*?)</g>', hero_source, re.S):
        for box in re.findall(r'href="#(box-[^"]+)"', group.group(2)):
            dest = config.get("hero_boxes", {}).get(box, "")
            if dest and not dest.startswith("solution:"):
                slug, _, anchor = dest.partition("#")
                title = next((h["text"] for h in readme_heads if h["id"] == anchor), topic_by_slug[slug]["title"]) if anchor else topic_by_slug[slug]["title"]
                item = (f'topics/{slug}.html' + (f'#{anchor}' if anchor else ""), title)
                if item not in step_rows[group.group(1)]: step_rows[group.group(1)].append(item)
    steps = []
    for number in sorted(step_rows, key=int):
        pop = re.search(rf'<article[^>]*id="pop-{number}"[^>]*>.*?<h2>(.*?)</h2>', hero_source, re.S)
        name = html.unescape(re.sub(r"<[^>]+>", "", pop.group(1))).strip() if pop else f"Step {number}"
        name = re.sub(r"^\s*\d+\s*·\s*", "", name)
        chips = "".join(f'<a class="chip" href="{href}">{esc(label)}</a>' for href, label in step_rows[number])
        steps.append(f'<article class="step"><h3><span>{number}</span>{esc(name)}</h3><div class="chips">{chips}</div></article>')
    groups = []
    for group in dict.fromkeys(t["group"] for t in topics):
        cards = []
        for topic in [t for t in topics if t["group"] == group]:
            chips, seen_diagrams = [], set()
            for key, box_id, box_name in diagrams_for_topic[topic["slug"]]:
                if key in seen_diagrams:
                    continue
                seen_diagrams.add(key)
                short_title = "Hero diagram" if key == "hero" else solution_by_slug.get(key, {}).get("title", diagrams[key]["title"])
                chips.append((f"diagrams/{key}.html#{box_id}", f"In the diagram: {short_title} › {box_name}"))
            chips = "".join(f'<a class="chip" href="{href}">{esc(label)}</a>' for href, label in unique_rows(chips))
            cards.append(f'<article class="guide-card"><div class="card-body"><div class="card-meta"><span>{esc(group)}</span></div><h3>{esc(topic["title"])}</h3><p>{esc(topic["one_line"])}</p><div class="chips">{chips}</div><div class="card-footer"><a href="topics/{topic["slug"]}.html">Open topic →</a></div></div></article>')
        groups.append(f'<section class="topic-group"><h2>{esc(group)}</h2><div class="card-grid">{"".join(cards)}</div></section>')
    sol_groups = []
    for kind in ("System design", "Object-oriented design"):
        cards = []
        for sol in [x for x in solutions if x["kind"] == kind]:
            configured = next((x.get("one_line") for x in config.get("solutions", []) if x.get("slug") == sol["slug"]), sol["title"])
            badge = '<span class="type-tag live">▶ Interactive diagram</span>' if sol["slug"] in diagrams else ""
            cards.append(f'<article class="guide-card"><div class="card-body"><div class="card-meta"><span>{esc(kind)}</span>{badge}</div><h3>{esc(sol["title"])}</h3><p>{esc(configured)}</p><div class="card-footer"><a href="solutions/{sol["slug"]}.html">Open solution →</a></div></div></article>')
        sol_groups.append(f'<section class="topic-group"><h2>{kind}</h2><div class="card-grid">{"".join(cards)}</div></section>')
    image_records = readme_images(readme, readme_heads, anchor_topics, topic_by_slug, solution_slugs)
    images, dropped_images = [], []
    for item in image_records:
        src, alt, heading = item["src"], item["alt"], item["heading"]
        if urlsplit(src).scheme:
            # The one remote README visual is a stale camo redirect. Keep it in its topic text, not the offline gallery.
            dropped_images.append(src)
            continue
        if item["solution"]:
            solution = solution_by_slug[item["solution"]]
            link = f'solutions/{solution["slug"]}.html'
            shown = f'Shown in: {solution["title"]}'
        elif item["owner"] and heading:
            slug, _ = item["owner"]
            link = f'topics/{slug}.html#{heading["id"]}'
            shown = f'Shown in: {topic_by_slug[slug]["title"]} › {heading["text"]}'
        else:
            link, shown = UPSTREAM, "Shown in: the original README"
        caption = alt or (heading["text"] if heading else "Primer image")
        img = rewrite_url(src, 0, anchor_topics, solution_slugs, is_image=True)
        images.append(f'<article class="gallery-card"><a href="{link}"><img loading="lazy" src="{img}" alt="{esc(caption)}"></a><p>{esc(caption)}<br><a href="{link}">{esc(shown)}</a></p></article>')
    diagram_cards = [f'<article class="guide-card"><div class="card-body"><h3>How a web system scales</h3><p>Walk through the main parts of a web system.</p><div class="card-footer"><a href="diagrams/hero.html">Open diagram →</a></div></div></article>']
    for key, info in diagrams.items():
        if key != "hero":
            title = next((x["title"] for x in solutions if x["slug"] == key), info["title"])
            source = solution_by_slug.get(key, {}).get("path")
            thumbnail = source / f'{source.name}.png' if source else None
            preview = f'<img class="diagram-thumbnail" src="images/solutions/{key}/{thumbnail.name}" alt="">' if thumbnail and thumbnail.exists() else ""
            diagram_cards.append(f'<article class="guide-card">{preview}<div class="card-body"><h3>{esc(title)}</h3><div class="card-footer"><a href="diagrams/{key}.html">Open diagram →</a></div></div></article>')
    landing = f'''<div role="tabpanel" id="overview" aria-labelledby="tab-overview"><section class="hero"><div class="shell"><p class="eyebrow">Read the primer</p><h1>Learn one system idea at a time.</h1><p class="hero-copy">Start with the basics. Use the diagram links to see where each idea fits.</p><div class="stamps"><div class="library-stamp"><strong>{counts['topics']}</strong><span>Topics</span></div><div class="library-stamp"><strong>{counts['solutions']}</strong><span>Solutions</span></div><div class="library-stamp"><strong>{counts['diagrams']}</strong><span>Diagrams</span></div></div></div></section><section class="section"><div class="shell"><p class="section-label">Overview</p><h2>Follow a request through the system.</h2><div class="split-layout"><iframe class="diagram-frame" src="diagrams/hero.html" title="How a web system scales"></iframe><div class="step-list">{"".join(steps)}</div></div></div></section></div><div role="tabpanel" id="topics" aria-labelledby="tab-topics" hidden><section class="section"><div class="shell"><p class="section-label">Topics</p><h1>Learn one system idea at a time.</h1>{"".join(groups)}</div></section></div><div role="tabpanel" id="solutions" aria-labelledby="tab-solutions" hidden><section class="section"><div class="shell"><p class="section-label">Solutions</p><h1>See the ideas in use.</h1>{"".join(sol_groups)}</div></section></div><div role="tabpanel" id="diagrams" aria-labelledby="tab-diagrams" hidden><section class="section"><div class="shell"><p class="section-label">Diagrams</p><h1>Explore the visual guides.</h1><div class="card-grid">{"".join(diagram_cards)}</div><h2 class="gallery-heading">Images from the primer</h2><div class="gallery">{"".join(images)}</div></div></section></div>'''
    (OUT / "index.html").write_text(page("System Design Primer", landing, landing=True, counts=counts))
    print(f"gallery images: {len(images)} (unique README srcs: {len(image_records)}, dropped remote: {len(dropped_images)})")
    print(f"unresolved README anchors: {len(UNRESOLVED_ANCHORS)}" + (f" — {', '.join(sorted(UNRESOLVED_ANCHORS)[:10])}" if UNRESOLVED_ANCHORS else ""))
    return link_check(config, topic_by_slug, counts)


def link_check(config, topics, counts):
    failures, checked = [], 0
    pages = list(OUT.rglob("*.html"))
    for file in pages:
        text = file.read_text()
        ids = set(re.findall(r'\bid=["\']([^"\']+)', text))
        for value in re.findall(r'\b(?:href|src)=["\']([^"\']+)', text):
            if value.startswith(("http:", "https:", "mailto:", "data:")): continue
            checked += 1
            path, sep, frag = value.partition("#")
            if not path:
                if frag and file.parent.name != "diagrams" and frag not in ids: failures.append(f"{file.relative_to(OUT)}: missing #{frag}")
                continue
            target = (file.parent / path).resolve()
            if not target.exists():
                failures.append(f"{file.relative_to(OUT)}: missing {value}")
            elif frag and target.suffix == ".html" and frag not in set(re.findall(r'\bid=["\']([^"\']+)', target.read_text())):
                failures.append(f"{file.relative_to(OUT)}: missing {value}")
    index = (OUT / "index.html").read_text()
    for box, dest in config.get("hero_boxes", {}).items():
        if dest.startswith("solution:"): continue
        slug = dest.split("#")[0]
        if f"hero.html#{box}" not in (OUT / "topics" / f"{slug}.html").read_text(): failures.append(f"two-way: {box} missing from {slug}")
    for slug in topics:
        if f'topics/{slug}.html' not in index: failures.append(f"index missing topic {slug}")
    for file in (OUT / "solutions").glob("*.html"):
        if f'solutions/{file.name}' not in index: failures.append(f"index missing solution {file.name}")
    print(f"pages: {len(pages)}, links checked: {checked}, failures: {len(failures)}")
    for failure in failures[:50]: print("FAIL", failure)
    return not failures


if __name__ == "__main__":
    sys.exit(0 if build() else 1)

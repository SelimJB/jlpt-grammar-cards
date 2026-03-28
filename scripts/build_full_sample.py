#!/usr/bin/env python3

import csv
import html
import json
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path


FIELDS = [
    "grammar_point",
    "meaning",
    "level",
    "lesson_number",
    "lesson_title",
    "bunpro_url",
    "structure",
    "part_of_speech",
    "word_type",
    "register",
    "about",
    "cautions",
    "example_jp_1",
    "example_en_1",
    "synonyms",
    "antonyms",
    "related",
]

USER_AGENT = "Mozilla/5.0 (compatible; Codex/1.0; +https://openai.com/)"

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
)
TAG_RE = re.compile(r"<[^>]+>")
CAUTION_SECTION_RE = re.compile(r"<section class='caution'>.*?</section>", re.S)
PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.S)
STUDY_QUESTION_REF_RE = re.compile(r'data-study-question="(\d+)"')


def clean_text(value: str) -> str:
    if not value:
        return ""
    value = value.replace("<br>", " | ").replace("<br/>", " | ").replace("<br />", " | ")
    value = re.sub(r"</p>\s*<p>", "\n\n", value)
    value = re.sub(r"</li>\s*<li[^>]*>", " | ", value)
    value = TAG_RE.sub("", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s*\|\s*", " | ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return value.strip()


def single_line(value: str) -> str:
    value = clean_text(value)
    value = value.replace("\n\n", " | ").replace("\n", " ")
    value = re.sub(r"\s*\|\s*", " | ", value)
    return value.strip(" |")


def safe_cell(value: str) -> str:
    return (value or "").replace(";", ",")


def normalize_example_content(value: str) -> str:
    value = value or ""
    value = html.unescape(value)
    value = re.sub(
        r"<span class=['\"]study-area-input['\"]>.*?</span>",
        "",
        value,
    )
    value = TAG_RE.sub("", value)
    value = re.sub(r"\[\[\s*\|\s*", "<br>", value)
    value = re.sub(r"\s*\|\s*", "<br>", value)
    value = value.replace("]]", "")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"\n\s*\n+", "<br><br>", value)
    value = re.sub(r"\n+", "<br>", value)
    value = re.sub(r"(?:<br>\s*){3,}", "<br><br>", value)
    value = re.sub(r"\s*<br>\s*", "<br>", value)
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip(" <br>")


def fetch_page_props(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode("utf-8")
    match = NEXT_DATA_RE.search(raw)
    if not match:
        raise RuntimeError(f"Missing __NEXT_DATA__ for {url}")
    return json.loads(match.group(1))["props"]["pageProps"]


def build_structure(reviewable: dict) -> str:
    casual = single_line(reviewable.get("casual_structure", ""))
    polite = single_line(reviewable.get("polite_structure", ""))
    parts = []
    if casual and polite:
        if casual != polite:
            parts.extend([casual, polite])
        else:
            parts.append(casual)
    elif casual:
        parts.append(casual)
    elif polite:
        parts.append(polite)
    return " | ".join(dict.fromkeys(parts))


def extract_about(writeup_html: str, fallback: str) -> str:
    if writeup_html:
        without_cautions = CAUTION_SECTION_RE.sub("", writeup_html)
        paragraphs = [single_line(p) for p in PARAGRAPH_RE.findall(without_cautions)]
        paragraphs = [p for p in paragraphs if p]
        if paragraphs:
            return paragraphs[0]
    return single_line(fallback)


def extract_cautions(reviewable: dict, writeup_html: str) -> str:
    cautions = []
    base_caution = single_line(reviewable.get("caution", ""))
    if base_caution:
        cautions.append(base_caution)
    if writeup_html:
        for section in CAUTION_SECTION_RE.findall(writeup_html):
            for paragraph in PARAGRAPH_RE.findall(section):
                cleaned = single_line(paragraph)
                if cleaned:
                    cautions.append(cleaned)

    deduped = []
    seen = set()
    for caution in cautions:
        key = caution.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(caution)
    return " | ".join(deduped)


def extract_example(study_questions: list, writeup_html: str) -> tuple[str, str]:
    lookup = {str(question.get("id")): question for question in study_questions}
    ordered_ids = STUDY_QUESTION_REF_RE.findall(writeup_html or "")
    ordered_questions = [lookup[qid] for qid in ordered_ids if qid in lookup]
    candidates = ordered_questions if ordered_questions else study_questions

    for question in candidates:
        content = question.get("content") or ""
        answer = question.get("kanji_answer") or question.get("answer") or ""
        if answer:
            content = re.sub(
                r"<span class=['\"]study-area-input['\"]>.*?</span>", answer, content
            )
        jp = normalize_example_content(content)
        en = single_line(question.get("translation", ""))
        if jp:
            return jp, en
    return "", ""


def extract_relationships(related_contents: list, current_title: str) -> dict:
    grouped = {"synonym": [], "antonym": [], "related": []}
    for item in related_contents or []:
        relationship_type = item.get("relationship_type") or "related"
        grouped.setdefault(relationship_type, [])
        first = item.get("first_relatable") or {}
        second = item.get("second_relatable") or {}
        other = second if first.get("title") == current_title else first
        title = other.get("title") or ""
        if title and title != current_title:
            grouped[relationship_type].append(title)

    result = {}
    for key in ("synonym", "antonym", "related"):
        unique = []
        seen = set()
        for title in grouped.get(key, []):
            if title not in seen:
                seen.add(title)
                unique.append(title)
        result[key] = " | ".join(unique)
    return result


def enrich_row(source_row: dict) -> dict:
    props = fetch_page_props(source_row["bunpro_url"])
    reviewable = props["reviewable"]
    included = props["included"]

    writeups = included.get("writeups") or []
    writeup_html = writeups[0].get("body", "") if writeups else ""
    study_questions = included.get("studyQuestions") or []
    related_contents = included.get("relatedContents") or []

    example_jp, example_en = extract_example(study_questions, writeup_html)
    relationships = extract_relationships(
        related_contents, reviewable.get("title", source_row["grammar_point"])
    )

    row = {
        "grammar_point": source_row["grammar_point"],
        "meaning": source_row["meaning"],
        "level": source_row["level"],
        "lesson_number": source_row["lesson_number"],
        "lesson_title": source_row["lesson_title"],
        "bunpro_url": source_row["bunpro_url"],
        "structure": build_structure(reviewable),
        "part_of_speech": single_line(
            reviewable.get("part_of_speech_translation")
            or reviewable.get("part_of_speech")
            or ""
        ),
        "word_type": single_line(
            reviewable.get("word_type_translation") or reviewable.get("word_type") or ""
        ),
        "register": single_line(
            reviewable.get("register_translation") or reviewable.get("register") or ""
        ),
        "about": extract_about(
            writeup_html,
            reviewable.get("nuance_translation") or reviewable.get("nuance") or "",
        ),
        "cautions": extract_cautions(reviewable, writeup_html),
        "example_jp_1": example_jp,
        "example_en_1": example_en,
        "synonyms": relationships["synonym"],
        "antonyms": relationships["antonym"],
        "related": relationships["related"],
    }
    return {field: safe_cell(row[field]) for field in FIELDS}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="n5.txt",
        help="Input semicolon-delimited dataset file",
    )
    parser.add_argument(
        "--output",
        default="n5_full_sample.txt",
        help="Output semicolon-delimited enriched dataset file",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Delay between requests in seconds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    input_path = root / args.input
    output_path = root / args.output

    with input_path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        source_rows = list(reader)

    enriched_rows = []
    total = len(source_rows)
    for index, source_row in enumerate(source_rows, start=1):
        enriched_rows.append(enrich_row(source_row))
        if index % 20 == 0 or index == total:
            print(f"processed {index}/{total}", file=sys.stderr)
        time.sleep(args.sleep)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"wrote {len(enriched_rows)} rows to {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

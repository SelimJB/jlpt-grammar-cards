
Japanese grammar flashcard datasets and Anki templates built from public Bunpro pages.

## Contracts

### Simple

Methodology:
- fetched from the public Bunpro deck pages only

```txt
grammar_point;meaning;level;lesson_number;lesson_title;bunpro_url
```

Fields:
- `grammar_point`: Japanese grammar item
- `meaning`: short gloss
- `level`: JLPT level
- `lesson_number`: Bunpro lesson number
- `lesson_title`: Bunpro lesson title
- `bunpro_url`: public Bunpro page

Templates:
- `templates/jap_to_meaning`
- `templates/meaning_to_jap`

### Enriched

Methodology:
- fetched from each public Bunpro grammar page

```txt
grammar_point;meaning;level;lesson_number;lesson_title;bunpro_url;structure;structure_display;part_of_speech;word_type;register;about;cautions;example_jp_1;example_en_1;synonyms;antonyms;related;meaning_hint;jp_hint
```

Fields:
- `grammar_point`: Japanese grammar item
- `meaning`: short gloss
- `level`: JLPT level
- `lesson_number`: Bunpro lesson number
- `lesson_title`: Bunpro lesson title
- `bunpro_url`: public Bunpro page
- `structure`: usage pattern
- `structure_display`: structure formatted for card display
- `part_of_speech`: grammar class
- `word_type`: word category
- `register`: style level
- `about`: short explanation
- `cautions`: common traps
- `example_jp_1`: first Japanese example
- `example_en_1`: first English translation
- `synonyms`: close grammar points
- `antonyms`: opposite grammar points
- `related`: related grammar points
- `meaning_hint`: disambiguation for repeated meanings
- `jp_hint`: context hint for repeated Japanese forms

Generated fields:
- `meaning_hint`: generated only when the gloss is ambiguous
- `jp_hint`: generated only when the Japanese form is ambiguous
- `structure_display`: generated from `structure` for easier reading in templates

Templates:
- `templates/jap_to_meaning_full`
- `templates/meaning_to_jap_full`

# kn/lexical-plural-folding (KGForEdGlobalMCP)

Branch: [`kn/lexical-plural-folding`](https://github.com/nyashkn/KGForEdGlobalMCP/tree/kn/lexical-plural-folding) in the `KGForEdGlobalMCP` fork, at `a364d64`, one commit on IDinsight `KGForEdGlobalMCP` `main` at `45f07c4` (2.0.0). Type: feat, opt-in. **The measured gain is small.**

## What the change does

Lexical search in the MCP server does no plural folding, so "pictograph" misses "pictographs" and "equation" misses "equations". The branch adds a profile setting `languagePolicy.foldLexicalPlurals` (default `false`; an additive field, so the profile schema version stays 1.1, and no shipped profile sets it). When a package's profile sets it, that package's index and its queries are built with folded tokens.

Fold rules (hand-written, no dependency): `-ies` to `-y`; `-sses`, `-shes`, `-xes`, `-ches` drop `es`; other `-s` is dropped except after `-ss`, `-us`, `-is`. Never folded: times, news, series, species. Kept with their `e`: aches, caches, headaches, moustaches, niches. Irregular: axes to axis, halves to half, vertices to vertex, matrices to matrix, indices to index, children to child, feet to foot. Only lowercase ASCII words longer than 3 letters change. Known gaps: `-ie` singulars (cookies, movies) and `-o` plurals (zeroes) do not join; `-zes` (quizzes) is not folded.

Changed files: `profiles/models.py`, `search/normalizers.py`, `search/lexical.py`, `search/service.py` (reports the normalizer version in index metadata), `docs/guides/standards-search.md` and `docs/data/profiles.md`. Tests: `backend/tests/kgfegmcp/test_lexical_plural_fold.py`.

An earlier version folded plurals for everyone. That changed ranking, the index hash and cursors, and went against the docs' "no stemming" statement, so it was rewritten as an opt-in.

## Method

A probe against the MCP server over stdio: tool `search_standards`, text mode, tokens, operator any, limit 10. For each question, search within the question's grade and count whether the gold standard is in the top 5. Two query forms: `raw` (the question as written) and `kw` (stopwords and digits removed); two extra forms (`kwn`, `full`) that keep digits and symbols. "Off" runs the server with the setting at its default; "on" runs a launcher that sets the default to true, so the real profile path is used without editing profile files (their hashes are pinned).

## Inputs

52 Rwanda and 113 Nigeria exam-style questions, each linked to 1 to 3 standards in IDinsight's published packages. The links were made by a language model and checked by a second model only where two linkers disagreed; no person checked them. The Nigeria questions come from a third-party site, not official papers. The question text is third-party copyright, so neither the questions nor the links are in this repository, and **the probe cannot be re-run from this repository**.

## Result (top 5 within grade, setting off against on)

| Query | Set | n | Top-5 off (= `main`) | Top-5 on | Gained / lost |
|---|---|---|---|---|---|
| kw | Rwanda | 52 | 22 | 23 | +2 / -1 |
| kw | Nigeria | 113 | 30 | 34 | +4 / 0 |
| raw | Rwanda | 52 | 17 | 21 | +4 / 0 |
| raw | Nigeria | 113 | 22 | 24 | +2 / 0 |
| kwn | Rwanda | 52 | 20 | 21 | +3 / -2 |
| kwn | Nigeria | 113 | 26 | 28 | +3 / -1 |

The `full` query variant was also run; its rows are omitted here.

Pooled over both countries (n = 165): `kw` 52 to 57 questions in the top 5, `raw` 39 to 45. Top-1 moves both ways (Rwanda `kw` 12 to 9, Nigeria `kw` 13 to 18). Three cells lose a question.

Setting off against `main`: index metadata (index hash, normalizer version, unique token count) was identical for all 7 shipped packages, and the probe gave identical rows (rank, hit count, top-1, score) for 416 of 416 Rwanda rows and 904 of 904 Nigeria rows over all four query kinds and both scopes.

## Limits

- The gain is 1 to 4 questions per cell and there are no confidence intervals. Quote examples ("pictograph" now finds "pictographs"), not a recall figure.
- Most misses in this probe are vocabulary (command words, word problems, notation), not word endings, so folding cannot fix most of them.
- False folds were not measured on the five packages other than Rwanda and Nigeria with the setting on.
- The docs build in strict mode was not run.
- The gold is model-made and only partly reviewed (see Inputs).
- The probe script and question sets stay outside this repository, and the table and the setting-off check above are the figures recorded when the probe was run; they were not re-run for this repository. What we did re-check: the branch's own test file (`test_lexical_plural_fold.py`, 36 tests) passes, and the fold function gives pictographs to pictograph, equations to equation, halves to half and leaves times and series alone.

## Reproduce

The unit tests and the examples are reproducible. From a checkout of the branch, in the MCP backend virtualenv:

```
pytest backend/tests/kgfegmcp/test_lexical_plural_fold.py
```

To see the behaviour by hand, call `kgfegmcp.search.normalizers.normalize_lexical_text("Pictographs and equations", fold_plurals=True)`. It returns `('pictograph', 'and', 'equation')`; with the default it returns `('pictographs', 'and', 'equations')`.

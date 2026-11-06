---
name: vault-log
description: Exact formats for writing back to the Gen vault (Decisions log, Findings log, Open items, journal notes, frontmatter). Use when recording a decision, a result or negative result, an open item, or journal links at the end of a session.
---
# vault-log

The vault (`/Users/benk/Downloads/Obsidian/Gen`) is the project's map: summaries and links to repo files
at a commit, never copies. Write to the files directly; Obsidian is only the viewer.

## The procedure (vault first; the rules are in CLAUDE.md)
1. **Before the first edit:** read the area's MOC, the note that owns the component, and the Glossary
   for any term you're unsure of. Check the Decisions log before proposing a choice and the Findings
   log before re-running or re-deriving anything. Take the next task from Open items.
2. **Before a repo file:** read its note. When the note is wrong or stale, fix it in the same turn:
   summary, path, commit (the frontmatter `source` and `date` too).
3. **A new row, spec, run or adapter:** make its note first from `Templates/Note template.md` (what it
   is, what was built, results, hashes, deviations, status), placeholders included. Fill it as you go.
4. **As things happen, not at the end:** a decision means a Decisions line; a result means a Findings
   line with the record path; anything waiting on Ben or an agent means an Open item with owner and
   owning note. Close items when they're done.
5. **Blocked on Ben:** write the Open item, say so in one line, and stop.
6. **After each block of work:** one to three journal lines of why, linking the notes touched (no
   narration); the notes touched also go on the day's `Related:` line.
7. **Before stopping:** every note you touched still has a valid source commit; today's journal lines
   link something; `vault_check.py` passes (the Stop hook checks links and the logs).

## A note
- One note per concept, holding summaries and links only, under 60 lines.
- A one-off fact goes in the note that owns it, never in a new note.
- Frontmatter on every note (below). Each note links its MOC and at least two related notes, and the
  MOC links every note in its area.

## Where recorded: `path@commit`
Every log line points at the repo file that holds the evidence, at the commit that holds it:
`[plans/row5-spec.md#L580-L602](https://github.com/ben06kn-droid/<repo>/blob/<full sha>/plans/row5-spec.md#L580-L602)`.
The link text is `path` (with `#L` lines if useful); the URL carries the full SHA. Copy the SHA from
`git rev-parse HEAD` or `git log` output in the same turn. Never type one.

## Decisions log (`05 Cross-cutting/Decisions log.md`)
One table row in the section for its phase and row, oldest first:
`| YYYY-MM-DD | <decision, one line> | <path@commit link> | proposed / registered / superseded |`
- registered = decided by Ben, or settled in writing by the author before use (pre-committed rules count)
- superseding: add the new row and change the old row's status to `superseded (<what replaced it>)`

## Findings log (`05 Cross-cutting/Findings log.md`)
`| YYYY-MM-DD | <result with its key number; prefix **NEG** for a negative result> | <path@commit link to the record> |`
Numbers are copied from the record, never recalled.

## Open items (`05 Cross-cutting/Open items.md`)
Under `## Waiting on Ben` or `## Waiting on the agents`:
`| <item> | [[<owner note>]] | <path@commit link> |`
Closing: move the row to `## Closed` (create it at the end if missing) and prefix the item with
`YYYY-MM-DD done:`; add the commit or note that closed it.

## Journal (`06 Journal/YYYY-MM-DD.md`)
Git's post-commit hook (`.githooks/post-commit`, which calls `vault_ctx.py commit`) writes one line per
commit under `## <repo>`, whoever made it, once per hash:
`- HH:MM · <repo> · \`<short>\` · <subject> · <up to five paths>`
After each block of work, add one to three lines of why under the commit lines, linking the notes:
`- Why: <one line> · [[<note>]]`
At the end of a session, add the vault notes you touched to the day's `Related:` line as wikilinks.
A new day starts from `Templates/Journal template.md` and is added to the top of `06 Journal/MOC Journal.md`
(the hook does both). Obsidian's Daily notes also write to `06 Journal/` from that template. A day note
that already exists is the day's note: the hook adds missing frontmatter, fills `{{previous}}`, links it
from MOC Journal, and never makes a second file. Don't create a day note anywhere else.

## Frontmatter (every note)
```
---
type: <moc | home | plan-section | amendment | row | note | log | glossary | journal | template | stub>
status: <current | draft | proposed | registered | built | paused | superseded | placeholder | stub>
date: YYYY-MM-DD
source: "<repo> <path> @ <full sha>"
tags: [phase1 | phase2 | graph | sablier | decision | finding | open | registered | proposed]
---
```

## Never
- paste a plan, spec, log, result, prompt or record into the vault (a short quoted phrase is fine); link it at `path@commit`
- write credentials, organisation ids, account ids, host aliases, IPs or key paths
- rename or move a vault note outside Obsidian, or with "Automatically update internal links" off
- leave an unresolved `[[wikilink]]`: check with `python3 /Users/benk/Downloads/Obsidian/Gen/.scripts/vault_check.py`

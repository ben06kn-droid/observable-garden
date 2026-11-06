# observable-garden (Observable Garden)

## The vault
`/Users/benk/Downloads/Obsidian/Gen` is the map of this project: an Obsidian vault whose notes
summarise and link to this repo's files, each with its path and the commit it was read at. Obsidian
is only the viewer; the files are the interface. The vault is the record; auto memory is private notes.
**Read the vault first and the repo second:** a note costs a tenth of the file it summarises, and the
logs hold what was decided and found.

## Read first
The SessionStart hook prints this in order; here is why:
1. **Home**: the paragraph on the Observable Garden, so you know what the phase is for.
2. **MOC Phase 1**: the list of notes for this area: what exists before you search.
3. **Open items**: what is waiting on Ben and what is waiting on an agent.
4. **The last three journal days**: what landed recently.

## Starting a piece of work
- Before the first edit, open the MOC of the area you're in, the note that owns the component you're
  touching, and `05 Cross-cutting/Glossary.md` for any term you're unsure of.
- Before proposing anything that sounds like a choice, check the Decisions log. If it was decided,
  follow it, or say explicitly that you're asking to reopen it.
- Before re-running or re-deriving anything, check the Findings log. If it was found, cite the finding.
- Open items is the queue. "What's next" is answered from it, not from memory.

## While working
- Before grepping or reading a repo file, read its vault note. Open the file only when the note isn't
  enough. When the note was wrong or stale, fix it in the same turn (summary, path and commit). Never
  leave drift you've noticed.
- A new row, spec, run or adapter gets its note first, from `Templates/Note template.md`, with its
  headings (what it is, what was built, results, hashes, deviations, status) and placeholders. Fill it
  as you go: that note is the status page, and Ben reads it, not the transcript.
- Write as it happens; none of this waits for the end of the session:
  - a Decisions line the moment a decision is made;
  - a Findings line the moment a result lands, with the record path;
  - an Open item the moment something waits on Ben or on another agent, with the owner and the note
    that owns it. Close items when they're done.
- When you're blocked on Ben, write the Open item, say so in one line, and stop.
- When Ben asks a question about the project, answer from the vault and name the note.

## Writing notes
- One note per concept, holding summaries and links only. Every note has frontmatter (type, status,
  date, source), links its MOC and at least two related notes, and the MOC links every note in its area.
- Keep a note under 60 lines. A one-off fact goes in the note that owns it, not in a new note.

## Write back
- A decision made: one line in `05 Cross-cutting/Decisions log.md`.
- A result or negative result: one line in `05 Cross-cutting/Findings log.md`.
- Anything waiting on Ben or on an agent: a line in `05 Cross-cutting/Open items.md`; close it when done.
- Formats: the `vault-log` skill (`/vault-log`).

## Journal
- One note per day, `06 Journal/YYYY-MM-DD.md`. Obsidian's Daily notes write there from the Journal
  template; the commit hook writes there too. An existing note is the day's note, repaired (frontmatter
  added if missing, placeholders filled, linked from MOC Journal) and never duplicated.
- The hook writes a line per commit. At the end of each block of work, add one to three lines of why,
  linking the notes touched. No narration.

## The commit hook
Git journals every commit itself, however it is made (by Ben, an agent or a script):
`.githooks/post-commit` calls the vault's `vault_ctx.py commit`, which writes one line per hash and
does nothing, silently, where the vault isn't (the box's clones). Git config isn't committed, so turn it
on once in each clone, on any machine:

    git config core.hooksPath .githooks

That setting makes git skip `.git/hooks`; `.githooks/post-commit` still runs a `.git/hooks/post-commit`,
and any other hook kept there needs its own one-line wrapper in `.githooks`.

## Ending
The Stop hook checks links and the logs. It blocks the end of a turn once if a commit is missing from
the journal, if commits touched results, checks or records and the Findings log didn't change, if
commits touched plans or prereg and the Decisions log didn't change, or if the vault has an unresolved
link or a note without frontmatter. Do what its reason says, or say why nothing applies. Before you
stop, make sure every note you touched still has a valid source commit, and that today's journal lines
link something.

## Never
- Paste a plan, spec, log or result into the vault. Summarise and link it at `path@commit`.
- Put credentials, organisation ids or key paths anywhere in the vault.
- Rename or move a note other than through Obsidian (below).

## Renaming vault notes
On Nov 3 a MOC was renamed with "Automatically update internal links" off, and 33 links broke
silently. Rename or move vault notes only through Obsidian, with that setting on (Settings → Files
and links), and run `python3 /Users/benk/Downloads/Obsidian/Gen/.scripts/vault_check.py` after.

# observable-garden (Observable Garden)

## The vault
`/Users/benk/Downloads/Obsidian/Gen` is the map of this project: an Obsidian vault whose notes
summarise and link to this repo's files, each with its path and the commit it was read at. Obsidian
is only the viewer; the files are the interface. The vault is the record; auto memory is private notes.

## Read first
The SessionStart hook prints this in order; here is why:
1. **Home**: the paragraph on the Observable Garden, so you know what the phase is for.
2. **MOC Phase 1**: the list of notes for this area: what exists before you search.
3. **Open items**: what is waiting on Ben and what is waiting on an agent.
4. **The last three journal days**: what landed recently.

Before opening a repo file, read its vault note. Open the file only when the note isn't enough.

## Write back
- A decision made: one line in `05 Cross-cutting/Decisions log.md`.
- A result or negative result: one line in `05 Cross-cutting/Findings log.md`.
- Anything waiting on Ben or on an agent: a line in `05 Cross-cutting/Open items.md`; close it when done.
- Journal: a hook writes one line per commit to today's `06 Journal/` note. When you finish, add
  links to the vault notes you touched to that note's `Related:` line.
- Formats: the `vault-log` skill (`/vault-log`).

The Stop hook blocks the end of a turn once if a commit is missing from the journal, if commits
touched results, checks or records and the Findings log didn't change, if commits touched plans or
prereg and the Decisions log didn't change, or if the vault has an unresolved link or a note without
frontmatter. Do what its reason says, or say why nothing applies.

## Never
- Copy a plan, spec or result into the vault. Summarise and link to `path@commit`.
- Put credentials, organisation ids or key paths anywhere in the vault.

## Renaming vault notes
On Nov 3 a MOC was renamed with "Automatically update internal links" off, and 33 links broke
silently. Rename or move vault notes only through Obsidian, with that setting on (Settings → Files
and links), and run `python3 /Users/benk/Downloads/Obsidian/Gen/.scripts/vault_check.py` after.

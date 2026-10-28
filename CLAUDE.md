# Claude project rules

Read and follow [AGENTS.md](AGENTS.md) and [docs/PROTOCOL.md](docs/PROTOCOL.md).

This Git remote is **public**. Private Deposium research, application sources,
local configuration, results, documents, metadata, and the former private Git
history may be present locally under ignored paths. Keep them local and preserve
them. Their availability is not permission to publish them.

- Never force-add ignored files, weaken privacy ignore rules, or copy confidential
  information into public code, commits, PRs, issues, logs, screenshots, or reports.
- Never publish credentials, private document/user/tenant identifiers, real
  operational snapshots, personal paths, author emails, or development hostnames.
- Do not remove ignored material or run `git clean -x` / `git clean -X`.
- Use explicit staging paths, inspect the staged diff, and run
  `python3 scripts/check-public-content.py` before committing or pushing.
- Preserve reference versions and original private campaign archives. A public
  clone does not contain those local files or the former private Git history.

Do not repoint an old private clone and push its history here. Use the clean
public history and reviewed file changes; never mirror private refs or tags.

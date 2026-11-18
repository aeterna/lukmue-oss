# lukmue-oss — rules for agents

Org rules apply when working inside the AETERNA workspace: worktree per task, product code through `aeterna-delegate`, and owner-controlled merges.

- **Purpose:** public home for tools and mods that can be shared.
- **Layout:** `tools/<name>/` and `mods/<name>/`, each with a valid `project.toml`.
- **Never add:** online-game play helpers, secrets, account data, recordings, or files we may not redistribute.
- **No private dependency:** this repo must not import or reference private repositories.
- **Commits:** sign off every commit with `git commit -s` and record `Agent: <Tool> - <Model>`.
- **Before push:** `python3 -m unittest discover -s tools/project-check -p 'test_*.py'` and `python3 tools/project-check/check_projects.py --root . --visibility public --dir tools --dir mods`.

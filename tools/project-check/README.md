# project-check

Validates `project.toml` files with Python 3.11 or newer and no third-party packages.

```bash
python3 tools/project-check/check_projects.py --root . --visibility public --dir tools --dir mods
```

Each non-hidden folder under a `--dir` is one project. `name` must match its folder and `visibility` must match `--visibility`.

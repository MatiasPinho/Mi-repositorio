# Development workflow

GitHub is the source of truth for the University Study engine. Personal courses stay local and are ignored by Git.

- `main`: stable engine.
- `dev`: integration branch used for iteration and CI.
- CI runs the release suite on Windows and Linux with Python 3.11.
- `materias/*` remains local except `materias/_plantilla/**`.
- Paid/model evals are intentionally separate from deterministic CI.

After bootstrap, normal engine updates are `git pull`; no ZIP migration is required.

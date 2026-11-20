"""Live /docs module: pitch deck + technical documentation + live system view, with admin control.

- settings.py  visibility switch and publishing window (Bangladesh time, GMT+6)
- store.py     content: draft, published, version history (JSON files)
- auth.py      Admin / Super Admin sign-in (passwords from the environment, signed cookie)
- sanitize.py  allowlist HTML cleaner for the editor + HTML -> Markdown export
- images.py    team photos: crop, resize, strip metadata
- live.py      live data from the running app: features, endpoints, knowledge base, usage, benchmarks
- routes.py    /docs, /docs/admin, /docs/export.md, /api/docs/*
"""

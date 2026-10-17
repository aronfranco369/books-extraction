# Book JSON Viewer (hosted)

Static version of the local `D:\tetea\books2json` viewer. No server needed:
it lists `tie/output/<level>/<subject>/<form folder>/*.json` through the GitHub
API and loads the JSONs and figure crops (`assets/`) from raw.githubusercontent.com.

Live: https://aronfranco369.github.io/books-extraction/

- `?b=csee/physics/form%20four` opens a book, `&page=2` jumps to a page.
- `?f=csee/physics/form%20four/<file>.json` opens one file.
- `?repo=owner/name&branch=main` reads another repo.

New extractions show up after a push (raw GitHub caches ~5 minutes; press Refresh).
The local-only "Check structure" button was removed (it needs Python).

# books-extraction

Workspace for the `books_extraction` skill: textbook PDFs -> page-based JSON.

## Layout

    skills/books_extraction/   the skill (SKILL.md, references/, scripts/)
    tools/render_chemfig.py    Chemfig -> SVG renderer (uses Tectonic)
    tie/books/<level>/<subject>/    put source PDFs here (level = csee | acsee)
    tie/output/<level>/<subject>/   extracted page JSONs are written here
    assets/books/              figure crops (written by the skill)
    pages/books/               page renders (written by the skill)

Inside each output subject the skill makes `form one` ... `form six` folders for
finished pages and a `temp` folder for unfinished pages and session records.

## Agent session start

    source ./setup.sh

This sets TETEA_ROOT to the repo root, installs PyMuPDF/Pillow and the Linux
build of Tectonic. Then invoke, e.g.:

    $books_extraction csee biology form2 20-30

Commit and push tie/output, assets/books and pages/books at the end of each
session, or the work is lost when the agent workspace is reset.

## PDF notes

GitHub rejects files over 100 MB and warns over 50 MB. Most books here are
under 80 MB; for anything bigger use Git LFS.

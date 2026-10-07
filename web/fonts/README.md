# Faces

Newsreader and Archivo, both SIL Open Font License 1.1, subset to latin by
Fontsource and renamed to their plain family names. Fontsource ships the optical
size doubled into the family name (`Newsreader 16pt 16pt`), which fontconfig
will not match, so the name table is rewritten on the way in.

They are committed rather than fetched because `scripts/build_assets.py` draws
the share card with them. A card that silently falls back to DejaVu because a
build host has no network is worse than no card: it still ships, and it still
looks almost right.

The page itself does not use these files. It pulls the same two faces from
Google Fonts, with real fallback stacks.

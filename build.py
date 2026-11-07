#!/usr/bin/env python3
"""Builds the AutoLang add-on package.

Usage:
	python build.py

The package is written to dist/AutoLang-V<version>.nvda-addon.

Optional helpers (the build still works without them if the generated files are already in the repository):
	* markdown  - turns addon/doc/en/readme.md into readme.html (pip install markdown)
	* polib     - turns the translation .po files into .mo files (pip install polib)
"""

import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ADDON = ROOT / "addon"
DIST = ROOT / "dist"
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AutoLang</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
{body}
</body>
</html>
"""


def readManifestValue(key):
	text = (ADDON / "manifest.ini").read_text(encoding="utf-8")
	match = re.search(rf"^{key}\s*=\s*(.+?)\s*$", text, re.MULTILINE)
	if not match:
		sys.exit(f"manifest.ini has no {key}")
	return match.group(1).strip('"')


def buildDocs():
	source = ADDON / "doc" / "en" / "readme.md"
	target = ADDON / "doc" / "en" / "readme.html"
	try:
		import markdown
	except ImportError:
		print("markdown is not installed: keeping the existing readme.html")
		return
	body = markdown.markdown(source.read_text(encoding="utf-8"), extensions=["extra"])
	target.write_text(HTML_TEMPLATE.format(body=body), encoding="utf-8")
	print(f"Built {target.relative_to(ROOT)}")


def buildTranslations():
	try:
		import polib
	except ImportError:
		print("polib is not installed: keeping the existing .mo files")
		return
	for po in sorted(ADDON.glob("locale/*/LC_MESSAGES/*.po")):
		polib.pofile(str(po)).save_as_mofile(str(po.with_suffix(".mo")))
		print(f"Built {po.with_suffix('.mo').relative_to(ROOT)}")


def buildAddon():
	version = readManifestValue("version")
	DIST.mkdir(exist_ok=True)
	package = DIST / f"AutoLang-V{version}.nvda-addon"
	with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
		for path in sorted(ADDON.rglob("*")):
			if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
				continue
			archive.write(path, path.relative_to(ADDON).as_posix())
	print(f"Built {package.relative_to(ROOT)}")
	return package


if __name__ == "__main__":
	buildDocs()
	buildTranslations()
	buildAddon()

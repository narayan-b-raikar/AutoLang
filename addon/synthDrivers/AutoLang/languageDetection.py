# Copyright (C) 2024 Alexander Linkov <kvark128@yandex.ru>
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.
# Copyright (C) 2026 Dr. Narayan B Raikar (AutoLang modifications, derived from MultiLang by Alexander Linkov).

import unicodedata
from io import StringIO

from speech.commands import LangChangeCommand
from .scripts import SCRIPTS

LATIN = (
	"en", "ha", "so", "id", "la", "sw", "eu",
	"nr", "zu", "xh", "ss", "st", "tn", "ts",
	"cs", "af", "pl", "hr", "ro", "sk", "sl", "tr", "hu", "az",
	"et", "sq", "ca", "es", "gl", "fr", "de", "nl", "it", "da", "is", "nb", "sv",
	"fi", "lv", "pt", "ve", "lt", "tl", "cy", "vi", "no", "uz",
)

CYRILLIC = ("ru", "uk", "be", "kk", "tt", "uz", "mn", "sr", "mk", "bg", "ky")
ARABIC = ("ar", "fa", "ps", "ur")
DEVANAGARI = ("hi", "sa", "mr", "ne")
CJK = ("zh", "ja", "ko")

# Scripts shared by several languages
SCRIPT_FAMILIES = {
	"Latin": LATIN,
	"Cyrillic": CYRILLIC,
	"Arabic": ARABIC,
	"Devanagari": DEVANAGARI,
	"Han": CJK,
}

# Characters of these scripts never decide the language by themselves
NEUTRAL_SCRIPTS = ("Common", "Inherited")


def _scriptMatchesLang(script, lang, scriptSettings):
	family = SCRIPT_FAMILIES.get(script)
	if family is not None:
		return lang in family
	return getattr(scriptSettings, script, None) == lang


def addDetectedLanguageCommands(speechSequence, defaultLang, scriptSettings, ignoreNumbersInLanguageDetection):
	curScript = None
	curLang = defaultLang
	# True when curLang was set by an explicit language command of the text (not the default voice)
	explicit = False
	for command in speechSequence:
		if isinstance(command, LangChangeCommand):
			if command.lang is None:
				curLang = defaultLang
				explicit = False
			else:
				curLang = command.lang
				explicit = True
			curScript = None
		elif isinstance(command, str):
			sb = StringIO()
			for c in command:
				newScript = SCRIPTS.get(ord(c))
				newLang = curLang
				if newScript in NEUTRAL_SCRIPTS:
					if newScript == "Common" and not ignoreNumbersInLanguageDetection and unicodedata.category(c).startswith("N"):
						newLang = defaultLang
					else:
						newScript = None
				elif newScript is not None and newScript != curScript:
					if explicit and curLang != defaultLang and _scriptMatchesLang(newScript, curLang, scriptSettings):
						# The text explicitly declares a language that uses this script. Respect it
						newLang = curLang
					else:
						newLang = getattr(scriptSettings, newScript, curLang)
				if curLang != newLang:
					if curScript is not None and sb.tell() > 0:
						yield LangChangeCommand(curLang)
						yield sb.getvalue()
						sb = StringIO()
					curLang = newLang
				if newScript is not None:
					curScript = newScript
				sb.write(c)
			# Send the string, if we have one
			if sb.tell() > 0:
				yield LangChangeCommand(curLang)
				yield sb.getvalue()
		else:
			yield command


def detectTextLanguage(text, scriptSettings):
	"""Returns the language of the first letter of the text that belongs to a specific script, or None"""
	for c in text:
		script = SCRIPTS.get(ord(c))
		if script is None or script in NEUTRAL_SCRIPTS:
			continue
		return getattr(scriptSettings, script, None)
	return None

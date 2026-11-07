"""Tests of the language detection. They do not need NVDA: the small part of NVDA that the module uses is replaced."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "addon" / "synthDrivers" / "AutoLang"


class LangChangeCommand:
	def __init__(self, lang):
		self.lang = lang

	def __repr__(self):
		return f"LangChangeCommand({self.lang!r})"


def loadModules():
	"""Loads scripts.py and languageDetection.py as a package, with a replacement for NVDA's speech.commands"""
	commands = types.ModuleType("speech.commands")
	commands.LangChangeCommand = LangChangeCommand
	sys.modules["speech"] = types.ModuleType("speech")
	sys.modules["speech.commands"] = commands
	package = types.ModuleType("autolang_under_test")
	package.__path__ = [str(PACKAGE)]
	sys.modules["autolang_under_test"] = package
	modules = {}
	for name in ("scripts", "languageDetection"):
		spec = importlib.util.spec_from_file_location(f"autolang_under_test.{name}", PACKAGE / f"{name}.py")
		module = importlib.util.module_from_spec(spec)
		sys.modules[spec.name] = module
		spec.loader.exec_module(module)
		modules[name] = module
	return modules["languageDetection"]


detection = loadModules()


class Scripts:
	"""The languages used for the scripts that many languages share"""
	Latin = "en"
	Cyrillic = "ru"
	Arabic = "ar"
	Devanagari = "hi"
	Han = "zh"
	Kannada = "kn"
	Tamil = "ta"


def run(sequence, default="kn", ignoreNumbers=False):
	"""Returns a list of (language, text) pairs"""
	result = []
	lang = None
	for item in detection.addDetectedLanguageCommands(sequence, default, Scripts, ignoreNumbers):
		if isinstance(item, LangChangeCommand):
			lang = item.lang
		else:
			result.append((lang, item))
	return result


class LanguageDetectionTest(unittest.TestCase):

	def test_kannada_and_english_are_separated(self):
		self.assertEqual(run(["ನಮಸ್ಕಾರ hello"]), [("kn", "ನಮಸ್ಕಾರ "), ("en", "hello")])

	def test_numbers_use_the_default_language(self):
		result = run(["hello 123 hello"], default="kn")
		self.assertEqual(result, [("en", "hello "), ("kn", "123 "), ("en", "hello")])

	def test_numbers_follow_the_nearby_text_when_ignored(self):
		self.assertEqual(run(["hello 123 hello"], default="kn", ignoreNumbers=True), [("en", "hello 123 hello")])

	def test_zero_width_joiners_do_not_split_text(self):
		self.assertEqual(run(["ಕ\u200cನ್ನಡ"]), [("kn", "ಕ\u200cನ್ನಡ")])

	def test_shared_script_uses_the_chosen_language(self):
		self.assertEqual(run(["नमस्ते"], default="en"), [("hi", "नमस्ते")])

	def test_explicit_language_of_the_text_is_kept(self):
		sequence = [LangChangeCommand("de"), "Guten Tag"]
		self.assertEqual(run(sequence, default="kn"), [("de", "Guten Tag")])

	def test_text_without_script_stays_in_the_default_language(self):
		self.assertEqual(run(["123 !!"], default="ta"), [("ta", "123 !!")])

	def test_language_of_a_piece_of_text(self):
		self.assertEqual(detection.detectTextLanguage("  ಕನ್ನಡ", Scripts), "kn")
		self.assertEqual(detection.detectTextLanguage("123 abc", Scripts), "en")
		self.assertIsNone(detection.detectTextLanguage("123 !?", Scripts))


if __name__ == "__main__":
	unittest.main()

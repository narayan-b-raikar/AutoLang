# Copyright (C) 2024 Alexander Linkov <kvark128@yandex.ru>
# Copyright (C) 2026 Dr. Narayan B Raikar (AutoLang modifications, derived from MultiLang by Alexander Linkov)
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""AutoLang: a virtual synthesizer that reads every part of a text with the synthesizer, voice and settings chosen for its language."""

import json
import queue
import threading
import time
import importlib
import wx
from collections import OrderedDict, defaultdict
from io import StringIO
from configobj import ConfigObj
from dataclasses import dataclass, field
from typing import Optional

import synthDriverHandler
import languageHandler
import addonHandler
import config
from autoSettingsUtils.utils import StringParameterInfo
from autoSettingsUtils.driverSetting import BooleanDriverSetting, DriverSetting, NumericDriverSetting
from synthDriverHandler import VoiceInfo, synthDoneSpeaking, synthIndexReached
from speech.commands import IndexCommand, CharacterModeCommand, PitchCommand, LangChangeCommand, BaseProsodyCommand
from logHandler import log

try:
	import characterProcessing
except Exception:
	characterProcessing = None

from . import languageDetection

addonHandler.initTranslation()

DRIVER_NAME = "AutoLang"
OLD_DRIVER_NAME = "MultiLang"
DEFAULT_SYNTH = "espeak"
SILENCE_SYNTH = "silence"

# Prefix of the ring settings that belong to one language
LANG_PREFIX = "lang_"
# Settings of one language that are not settings of its synthesizer
PSEUDO_IDS = ("synth", "sendLang", "symbolLevel")
# Settings of the nested synthesizers that are never shown
SKIPPED_SUB_SETTINGS = ("useWasapi",)
# The usual settings come first, in this order
MAIN_SETTINGS_ORDER = ("language", "voice", "variant", "pitch", "rate", "volume")
# Settings that can be changed with the settings ring (NVDA+Control+arrows)
RING_SETTINGS = ("voice", "variant", "pitch", "rate", "volume")
FAILURE_COOLDOWN = 60  # seconds
PRELOAD_INTERVAL = 400  # milliseconds
PRELOAD_START_DELAY = 1500  # milliseconds
NUMBERS_AUTO = "auto"
NUMBERS_DEFAULT = "default"
# Value of the punctuation list that means "use the level of NVDA"
LEVEL_NVDA = -1
# The language support of a synthesizer is not known
UNKNOWN = None


@dataclass
class VoiceSettings:
	synth: str = DEFAULT_SYNTH
	sendLang: bool = True
	# Own settings of the synthesizer for this language: voice, rate, pitch, volume, etc.
	params: dict = field(default_factory=dict)
	# Punctuation level for this language (None: use the level of NVDA)
	symbolLevel: Optional[int] = None


@dataclass
class ScriptSettings:
	Latin: str = "en"
	Cyrillic: str = "ru"
	Arabic: str = "ar"
	Devanagari: str = "hi"
	Han: str = "zh"
	Armenian: str = "hy"
	Hebrew: str = "he"
	Bengali: str = "bn"
	Gurmukhi: str = "pa"
	Greek: str = "el"
	Gujarati: str = "gu"
	Oriya: str = "or"
	Tamil: str = "ta"
	Telugu: str = "te"
	Kannada: str = "kn"
	Malayalam: str = "ml"
	Sinhala: str = "si"
	Thai: str = "th"
	Lao: str = "lo"
	Tibetan: str = "bo"
	Georgian: str = "ka"
	Mongolian: str = "mn"
	Khmer: str = "km"
	Hiragana: str = "ja"
	Katakana: str = "ja"
	Hangul: str = "ko"


# The scripts that many languages share: (name in ScriptSettings, languages of the script, label, old setting id)
SHARED_SCRIPTS = (
	("Latin", languageDetection.LATIN, _("Latin script text (English etc.)"), "latinVoice"),
	("Cyrillic", languageDetection.CYRILLIC, _("Cyrillic script text (Russian etc.)"), "cyrillicVoice"),
	("Arabic", languageDetection.ARABIC, _("Arabic script text (Arabic, Urdu etc.)"), "arabicVoice"),
	("Devanagari", languageDetection.DEVANAGARI, _("Devanagari script text (Hindi, Marathi etc.)"), "devanagariVoice"),
	("Han", languageDetection.CJK, _("Chinese, Japanese and Korean text"), "CJKVoice"),
)

configSpecString = f"""
scriptLanguages = string(default="")

[languages]
	[[__many__]]
		synth = string(default={VoiceSettings.synth})
		sendLang = boolean(default={VoiceSettings.sendLang})
		params = string(default="")
"""


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _wxReady():
	try:
		return wx.GetApp() is not None
	except Exception:
		return False


def _callAfter(func, *args):
	"""wx.CallAfter that is safe before the wx application exists (NVDA loads the synthesizer before creating it)"""
	if _wxReady():
		wx.CallAfter(func, *args)
		return True
	return False


def _callLater(delay, func, *args):
	if _wxReady():
		wx.CallLater(delay, func, *args)
		return True
	return False


def _getSynthInstance(name):
	return importlib.import_module(f"synthDrivers.{name}", package="synthDrivers").SynthDriver()


def _encodeParams(params, symbolLevel=None):
	data = dict(params)
	if symbolLevel is not None:
		data["symbolLevel"] = symbolLevel
	return json.dumps(data, sort_keys=True, ensure_ascii=True) if data else ""


def _decodeParams(value):
	"""Returns (params, symbolLevel)"""
	if not value or not isinstance(value, str):
		return {}, None
	try:
		data = json.loads(value)
	except ValueError:
		log.debugWarning(f"AutoLang: invalid parameters in the configuration: {value!r}")
		return {}, None
	if not isinstance(data, dict):
		return {}, None
	level = data.pop("symbolLevel", None)
	if not isinstance(level, int) or isinstance(level, bool):
		level = None
	return data, level


def _languageName(lang):
	try:
		return languageHandler.getLanguageDescription(lang) or lang
	except Exception:
		return lang


def _baseLanguage(code):
	"""'kn-IN', 'kn_IN' and 'KN' all give 'kn'"""
	if not code or not isinstance(code, str):
		return None
	return code.replace("_", "-").split("-")[0].strip().lower() or None


def _symbolLevels():
	if characterProcessing is None:
		return []
	try:
		return [int(level) for level in characterProcessing.CONFIGURABLE_SPEECH_SYMBOL_LEVELS]
	except Exception:
		return []


def _symbolLevelLabel(level):
	try:
		for key, label in characterProcessing.SPEECH_SYMBOL_LEVEL_LABELS.items():
			if int(key) == level:
				return label
	except Exception:
		pass
	return str(level)


def _symbolLevelOptions():
	options = [(LEVEL_NVDA, _("Same as NVDA setting"))]
	options.extend((level, _symbolLevelLabel(level)) for level in _symbolLevels())
	return options


class _PseudoSetting:
	"""A setting of AutoLang that is shown among the settings of one language, but is not a setting of a nested synthesizer"""
	defaultVal = None
	useConfig = False

	def __init__(self, id, displayName):
		self.id = id
		self.displayName = displayName


class EventWatcher(threading.Thread):

	def __init__(self, event):
		super().__init__()
		self._queue = queue.Queue()
		self._event = event
		self.daemon = True
		self.start()

	def run(self):
		while True:
			timeout = self._queue.get()
			if timeout is None:
				break
			if not self._event.wait(timeout):
				self._event.set()

	def watch(self, timeout):
		self._queue.put(timeout)


# ----------------------------------------------------------------------
# Punctuation level per language
# ----------------------------------------------------------------------

_activeDriver = None
_originalProcessText = None


def _installTextHook(driver):
	"""NVDA converts punctuation to words before the text reaches the synthesizer, using one level for all text.
	This hook lets the level depend on the language of each piece of text. Returns True if the hook is active"""
	global _activeDriver, _originalProcessText
	_activeDriver = driver
	if _originalProcessText is not None:
		return True
	try:
		import speech.speech as speechModule
		original = speechModule.processText
	except Exception:
		log.debugWarning("AutoLang: unable to hook the punctuation processing", exc_info=True)
		return False

	def processText(locale, text, symbolLevel, *args, **kwargs):
		drv = _activeDriver
		if drv is not None:
			try:
				level = drv._getSymbolLevelForText(text, symbolLevel)
				if level is not None:
					symbolLevel = level
			except Exception:
				log.debugWarning("AutoLang: punctuation hook failed", exc_info=True)
		return original(locale, text, symbolLevel, *args, **kwargs)

	_originalProcessText = original
	speechModule.processText = processText
	speechModule._autoLangHook = processText
	return True


def _removeTextHook():
	global _activeDriver, _originalProcessText
	_activeDriver = None
	if _originalProcessText is None:
		return
	try:
		import speech.speech as speechModule
		if getattr(speechModule, "_autoLangHook", None) is speechModule.processText:
			speechModule.processText = _originalProcessText
		del speechModule._autoLangHook
	except Exception:
		log.debugWarning("AutoLang: unable to remove the punctuation hook", exc_info=True)
	_originalProcessText = None


# ----------------------------------------------------------------------
# The driver
# ----------------------------------------------------------------------

class SynthDriver(synthDriverHandler.SynthDriver):
	name = DRIVER_NAME
	description = _("AutoLang")

	supportedCommands = {IndexCommand, CharacterModeCommand, PitchCommand, LangChangeCommand}
	supportedNotifications = {synthIndexReached, synthDoneSpeaking}

	def __init__(self):
		super().__init__()
		self._doneSpeakingFlag = threading.Event()
		self._doneSpeakingFlag.set()
		self._doneSpeakingWatcher = EventWatcher(self._doneSpeakingFlag)
		# name -> (synth instance, default values of its settings)
		self._synthCache = {}
		# name -> list of the settings supported by the instance
		self._subSettingsInfo = {}
		# name -> set of the languages of its voices, or UNKNOWN
		self._synthLanguages = {}
		# id of a ring setting -> (lang, synth name, original setting, setting shown to the user)
		self._proxyById = {}
		self._failedSynths = {}
		self._pausedSynths = set()
		self._appliedState = {}
		# (language, synth) -> own settings, kept while the user is choosing the synthesizer in the dialog
		self._savedParams = {}
		self._terminated = False
		self._starting = False
		self._ready = False
		self._hookActive = False
		self._preloadQueue = []
		self._preloadRunning = False
		self._preloadWanted = False
		# The language and synthesizer whose settings the settings ring shows now
		self._ringLang = None
		self._ringSynth = None
		self._ringMode = False
		self._ringDirty = True
		self._ringRefreshPending = False
		self._allowLoad = False
		self._uiInstalled = False
		self._synth = None
		self._lastSynth = None
		self.confspec = ConfigObj(StringIO(configSpecString), list_values=False, encoding="UTF-8")
		self.speechQueue = queue.Queue()

		self._voice = "en"
		try:
			lang = languageHandler.getLanguage().split("_")[0]
			if lang in self.availableVoices:
				self._voice = lang
		except Exception:
			log.debugWarning("AutoLang: unable to detect the language of NVDA", exc_info=True)
		# The language whose settings are being set up
		self._editLang = self._voice
		self.useUnicodeLanguageDetection = True
		self.numberMode = NUMBERS_DEFAULT
		self.preloadSynths = True

		self._settings = defaultdict(lambda: VoiceSettings())
		self._scriptSettings = ScriptSettings()

		self._originalDefaultValueForBaseProsodyCommand = BaseProsodyCommand.defaultValue
		BaseProsodyCommand.defaultValue = property(self._getProsodyDefault)

		synthDoneSpeaking.register(self._onSynthDoneSpeaking)
		synthIndexReached.register(self._onSynthIndexReached)

	def _getProsodyDefault(self, command):
		synth = self._synth or self._lastSynth
		try:
			return getattr(synth, command.settingName)
		except Exception:
			return 50

	# ------------------------------------------------------------------
	# Configuration
	# ------------------------------------------------------------------

	def getConfigSpec(self):
		spec = super().getConfigSpec()
		spec.update(self.confspec)
		for lang in self.availableVoices:
			spec["languages"][lang] = self.confspec["languages"]["__many__"]
		return spec

	def initSettings(self):
		# This runs while NVDA starts, before its window system exists. It must never fail and must not use wx,
		# otherwise NVDA falls back to another synthesizer
		self._starting = True
		try:
			firstLoad = False
			try:
				firstLoad = not config.conf[self._configSection].isSet(self.name)
			except Exception:
				log.debugWarning("AutoLang: unable to read the configuration", exc_info=True)
			try:
				super().initSettings()
			except Exception:
				log.error("AutoLang: unable to initialize the settings. Using the default settings", exc_info=True)
			if firstLoad:
				try:
					self._migrateOldConfig()
				except Exception:
					log.error("AutoLang: unable to import the settings of MultiLang", exc_info=True)
			self._editLang = self._voice
		finally:
			self._starting = False
			self._ready = True
		try:
			self._hookActive = _installTextHook(self)
		except Exception:
			log.error("AutoLang: unable to install the punctuation hook", exc_info=True)
		self._startLater()

	def _migrateOldConfig(self):
		"""Imports the language settings from the configuration of the MultiLang add-on, if there are any"""
		section = config.conf[self._configSection]
		if not section.isSet(OLD_DRIVER_NAME) or not section[OLD_DRIVER_NAME].isSet("languages"):
			return
		oldLangs = section[OLD_DRIVER_NAME]["languages"]
		newLangs = section[self.name]["languages"]
		for lang in self.availableVoices:
			if not oldLangs.isSet(lang):
				continue
			for key in ("synth", "sendLang"):
				if oldLangs[lang].isSet(key):
					newLangs[lang][key] = oldLangs[lang][key]
		oldVoice = section[OLD_DRIVER_NAME].get("voice")
		if oldVoice in self.availableVoices:
			section[self.name]["voice"] = oldVoice
		self.loadSettings()
		log.info("AutoLang: imported the language settings of MultiLang")

	def saveSettings(self):
		super().saveSettings()
		section = config.conf[self._configSection][self.name]
		conf = section["languages"]
		for lang, settings in list(self._settings.items()):
			langConf = conf[lang]
			if langConf["synth"] != settings.synth:
				langConf["synth"] = settings.synth
			if langConf["sendLang"] != settings.sendLang:
				langConf["sendLang"] = settings.sendLang
			params = _encodeParams(settings.params, settings.symbolLevel)
			if (langConf["params"] or "") != params:
				langConf["params"] = params
		scripts = json.dumps({script: getattr(self._scriptSettings, script) for script, *_ in SHARED_SCRIPTS}, sort_keys=True)
		if (section["scriptLanguages"] or "") != scripts:
			section["scriptLanguages"] = scripts
		if self._ready and not self._terminated:
			self._scheduleRingRefresh()

	def loadSettings(self, onlyChanged=False):
		self._starting = True
		self._savedParams.clear()
		try:
			self._loadLanguageSettings()
			super().loadSettings(onlyChanged=onlyChanged)
			self._appliedState.clear()
		finally:
			self._starting = False
		if self._editLang not in self.availableVoices:
			self._editLang = self._voice
		self._ringDirty = True
		if self._ready and not self._terminated:
			self._schedulePreload(0)
			self._scheduleRingRefresh()

	def _loadLanguageSettings(self):
		section = config.conf[self._configSection][self.name]
		conf = section["languages"]
		self._settings.clear()
		for lang in self.availableVoices:
			if not conf.isSet(lang):
				continue
			settings = self._settings[lang]
			for param, value in conf[lang].items():
				if not conf[lang].isSet(param):
					continue
				if param == "synth" and value in self.availableSynths:
					settings.synth = value
				elif param == "sendLang" and isinstance(value, bool):
					settings.sendLang = value
				elif param == "params":
					settings.params, settings.symbolLevel = _decodeParams(value)
		# Languages of the shared scripts
		self._scriptSettings = ScriptSettings()
		saved = {}
		try:
			data = json.loads(section["scriptLanguages"] or "{}")
			if isinstance(data, dict):
				saved = data
		except ValueError:
			log.debugWarning("AutoLang: invalid script languages in the configuration", exc_info=True)
		for script, family, label, oldId in SHARED_SCRIPTS:
			lang = saved.get(script)
			if lang is None and section.isSet(oldId):
				# Setting of the older versions of AutoLang and MultiLang
				lang = section[oldId]
			if lang in family:
				setattr(self._scriptSettings, script, lang)

	def terminate(self):
		self._terminated = True
		_removeTextHook()
		try:
			from . import settingsUi
			settingsUi.uninstall()
		except Exception:
			log.debugWarning("AutoLang: unable to remove the settings window changes", exc_info=True)
		try:
			self.cancel()
		except Exception:
			log.debugWarning("AutoLang: unable to cancel the speech", exc_info=True)
		try:
			self.saveSettings()
		except Exception:
			log.error("AutoLang: unable to save the settings", exc_info=True)
		self._unregisterConfigSaveAction()
		self._doneSpeakingWatcher.watch(None)
		self._doneSpeakingWatcher.join()
		synthIndexReached.unregister(self._onSynthIndexReached)
		synthDoneSpeaking.unregister(self._onSynthDoneSpeaking)
		BaseProsodyCommand.defaultValue = self._originalDefaultValueForBaseProsodyCommand
		self._synth = None
		self._lastSynth = None
		for synth, defaultConf in list(self._synthCache.values()):
			try:
				synth.cancel()
				synth.terminate()
			except Exception:
				log.debugWarning("AutoLang: unable to terminate a nested synthesizer", exc_info=True)
		self._synthCache.clear()

	@classmethod
	def check(cls):
		return True

	def _startLater(self):
		"""Things that need NVDA's window system. Called when the synthesizer starts and at every speech until they are done"""
		if self._terminated or not _wxReady():
			return
		if not self._uiInstalled:
			try:
				from . import settingsUi
				settingsUi.install(SynthDriver)
				self._uiInstalled = True
			except Exception:
				self._uiInstalled = True
				log.error("AutoLang: unable to add the AutoLang controls to the Speech settings", exc_info=True)
		self._schedulePreload(PRELOAD_START_DELAY)
		if self._ringDirty:
			self._scheduleRingRefresh()

	# ------------------------------------------------------------------
	# Punctuation level
	# ------------------------------------------------------------------

	def _getSymbolLevelForText(self, text, symbolLevel):
		"""Called for every piece of text that NVDA prepares. Returns the level for the language of the text, or None"""
		if not self.useUnicodeLanguageDetection:
			lang = self._voice
		else:
			lang = languageDetection.detectTextLanguage(text, self._scriptSettings) or self._voice
		settings = self._settings.get(lang)
		if settings is None or settings.symbolLevel is None:
			return None
		# Only replace the level chosen by the user in NVDA. Leave levels that NVDA forces (for example when spelling)
		if int(symbolLevel) != int(config.conf["speech"]["symbolLevel"]):
			return None
		level = settings.symbolLevel
		try:
			return characterProcessing.SymbolLevel(level)
		except Exception:
			return level

	# ------------------------------------------------------------------
	# Supported settings.
	# NVDA's Speech settings show only these general settings; the settings of the languages are in AutoLang's own
	# controls and windows (see settingsUi). The settings ring gets more while it is built (see _refreshRing)
	# ------------------------------------------------------------------

	_languageSetting = DriverSetting("editLang", _("Language to set up"), availableInSettingsRing=True, useConfig=False)

	_generalSettings = (
		DriverSetting("voice", _("&Default language"), availableInSettingsRing=True),
		BooleanDriverSetting("useUnicodeLanguageDetection", _("Find the language automatically from the script"), availableInSettingsRing=False, defaultVal=True),
		DriverSetting("numberMode", _("Read &numbers in"), availableInSettingsRing=False, defaultVal=NUMBERS_DEFAULT),
		BooleanDriverSetting("preloadSynths", _("Load synthesizers in advance (avoids delay)"), availableInSettingsRing=False, defaultVal=True),
	)

	def _get_supportedSettings(self):
		if not self._ringMode:
			return list(self._generalSettings)
		settings = [self._languageSetting]
		try:
			settings.extend(self._getLanguageBlock(self._ringLang, self._ringSynth))
		except Exception:
			log.debugWarning("AutoLang: unable to build the settings of the language", exc_info=True)
		settings.extend(self._generalSettings)
		return settings

	def _get_initialSettingsRingSetting(self):
		"""The settings ring starts with the rate of the language, like in NVDA"""
		settings = list(self.supportedSettings)
		for i, s in enumerate(settings):
			if s.availableInSettingsRing and s.id.startswith(LANG_PREFIX) and s.id.endswith("_rate"):
				return i
		for i, s in enumerate(settings):
			if s.availableInSettingsRing:
				return i
		return None

	def _eligibleSubSettings(self, synthName):
		info = self._subSettingsInfo.get(synthName)
		if not info:
			return []
		return [s for s in info if s.id not in SKIPPED_SUB_SETTINGS and not s.id.startswith("_")]

	def _orderedSubSettings(self, synthName):
		"""Settings of the synthesizer: the usual ones first, then the ones only this synthesizer has"""
		available = OrderedDict((s.id, s) for s in self._eligibleSubSettings(synthName))
		main = [available.pop(id) for id in MAIN_SETTINGS_ORDER if id in available]
		return main, list(available.values())

	def _getLanguageBlock(self, lang, synthName):
		"""Settings of one language, for the settings ring"""
		langName = _languageName(lang)
		block = [self._getProxy(lang, synthName, langName, _PseudoSetting("synth", _("Synthesizer")))]
		if synthName not in self._synthCache and not self._isFailed(synthName) and self._allowLoad:
			try:
				self._loadSynth(synthName)
			except Exception:
				self._failedSynths[synthName] = time.monotonic()
				log.error(f"AutoLang: unable to load the {synthName} synthesizer", exc_info=True)
		main, others = self._orderedSubSettings(synthName)
		if main or others:
			block.extend(self._getProxy(lang, synthName, langName, s) for s in main)
			block.extend(self._getProxy(lang, synthName, langName, s) for s in others)
		return block

	def _makeProxyId(self, lang, synthName, settingId):
		# The identifier must be lowercase, because NVDA builds the name of the attribute with the list
		# of available values using str.capitalize()
		if settingId in PSEUDO_IDS:
			return f"{LANG_PREFIX}{lang}_{settingId}".lower()
		return f"{LANG_PREFIX}{lang}_{synthName}_{settingId}".lower()

	def _getProxy(self, lang, synthName, langName, setting):
		id = self._makeProxyId(lang, synthName, setting.id)
		entry = self._proxyById.get(id)
		if entry is None:
			entry = (lang, synthName, setting, self._makeProxySetting(id, langName, setting))
			self._proxyById[id] = entry
		return entry[3]

	def _makeProxySetting(self, id, langName, setting):
		# Translators: Label of a setting of the settings ring that belongs to one language.
		# {language} is the name of the language, {setting} is the name of the setting, e.g. "Rate".
		label = _("{language}: {setting}").format(language=langName, setting=setting.displayName)
		ring = setting.id in RING_SETTINGS or setting.id == "synth"
		if isinstance(setting, NumericDriverSetting):
			return NumericDriverSetting(
				id, label, availableInSettingsRing=ring, defaultVal=setting.defaultVal,
				minVal=setting.minVal, maxVal=setting.maxVal, minStep=setting.minStep,
				normalStep=setting.normalStep, largeStep=setting.largeStep,
				displayName=label, useConfig=False,
			)
		if isinstance(setting, BooleanDriverSetting):
			return BooleanDriverSetting(
				id, label, availableInSettingsRing=ring, displayName=label,
				defaultVal=setting.defaultVal, useConfig=False,
			)
		return DriverSetting(id, label, availableInSettingsRing=ring, defaultVal=setting.defaultVal, displayName=label, useConfig=False)

	def __getattr__(self, name):
		# Called only when the normal lookup fails. Handles the settings of the languages in the settings ring
		if name.startswith("_") or "_proxyById" not in self.__dict__:
			raise AttributeError(name)
		entry = self._proxyById.get(name)
		if entry is not None:
			return self._getLangValue(*entry[:3])
		if name.startswith("availableLang_") and name.endswith("s"):
			entry = self._proxyById.get(LANG_PREFIX + name[len("availableLang_"):-1])
			if entry is not None:
				return self._getLangAvailableValues(*entry[:3])
		raise AttributeError(name)

	def __setattr__(self, name, value):
		if name.startswith(LANG_PREFIX) and "_proxyById" in self.__dict__:
			entry = self._proxyById.get(name)
			if entry is not None:
				self._setLangValue(*entry[:3], value)
				return
		super().__setattr__(name, value)

	# ------------------------------------------------------------------
	# Settings of one language
	# ------------------------------------------------------------------

	def _getLangAvailableValues(self, lang, synthName, setting):
		"""The values of a list setting, as an OrderedDict of StringParameterInfo"""
		if setting.id == "synth":
			return OrderedDict((id, StringParameterInfo(id, name)) for id, name in self.getSynthChoices(lang, load=False))
		if setting.id == "symbolLevel":
			return OrderedDict((id, StringParameterInfo(id, name)) for id, name in _symbolLevelOptions())
		if setting.id == "voice":
			return self.getVoicesForLanguage(synthName, lang)
		entry = self._synthCache.get(synthName)
		if entry is None:
			return OrderedDict()
		attr = f"available{setting.id.capitalize()}s"
		try:
			return getattr(entry[0], attr)
		except Exception:
			log.debugWarning(f"AutoLang: unable to get {attr} of {synthName}", exc_info=True)
			return OrderedDict()

	def _getLangValue(self, lang, synthName, setting):
		settings = self._settings[lang]
		if setting.id == "synth":
			return settings.synth
		if setting.id == "sendLang":
			return settings.sendLang
		if setting.id == "symbolLevel":
			return LEVEL_NVDA if settings.symbolLevel is None else settings.symbolLevel
		value = setting.defaultVal
		entry = self._synthCache.get(synthName)
		if entry is not None and setting.id in entry[1]:
			value = entry[1][setting.id]
		if settings.synth == synthName and setting.id in settings.params:
			value = settings.params[setting.id]
		if not isinstance(setting, (NumericDriverSetting, BooleanDriverSetting)):
			# A list setting must show a value that is in its list
			values = self._getLangAvailableValues(lang, synthName, setting)
			if values and value not in values:
				value = next(iter(values))
		return value

	def _setLangValue(self, lang, synthName, setting, value):
		"""Called by the settings ring"""
		settings = self._settings[lang]
		if setting.id == "synth":
			if value in self.availableSynths and value != settings.synth:
				self.selectSynth(lang, value)
				self._commitRing()
			return
		if setting.id == "symbolLevel":
			if value == LEVEL_NVDA:
				settings.symbolLevel = None
			elif value in _symbolLevels():
				settings.symbolLevel = value
			return
		if settings.synth != synthName:
			return
		value = self._checkValue(lang, synthName, setting, value)
		if value is None:
			return
		settings.params[setting.id] = value
		self._appliedState.pop(synthName, None)

	def _checkValue(self, lang, synthName, setting, value):
		"""Returns the value in the form that the setting accepts, or None"""
		if isinstance(setting, NumericDriverSetting):
			try:
				value = int(value)
			except (TypeError, ValueError):
				return None
			return max(setting.minVal, min(setting.maxVal, value))
		if isinstance(setting, BooleanDriverSetting):
			return bool(value)
		if value not in self._getLangAvailableValues(lang, synthName, setting):
			return None
		return value

	def _set_editLang(self, lang):
		"""The language to set up was changed, for example with the settings ring"""
		if lang in self.availableVoices and lang != self._editLang:
			self._editLang = lang
			self._commitRing()

	def _get_editLang(self):
		return self._editLang

	def _get_availableEditlangs(self):
		return self.availableVoices

	# ------------------------------------------------------------------
	# Used by the settings windows (see settingsUi)
	# ------------------------------------------------------------------

	def getLanguageChoices(self):
		return [(id, info.displayName) for id, info in self.availableVoices.items()]

	def setEditLanguage(self, lang):
		if lang in self.availableVoices:
			self._editLang = lang

	def getSynthName(self, lang):
		return self._settings[lang].synth

	def getSynthDisplayName(self, name):
		info = self.availableSynths.get(name)
		return info.displayName if info is not None else name

	def selectSynth(self, lang, synthName):
		"""Chooses the synthesizer of a language. The own settings of the language belong to the previous synthesizer"""
		settings = self._settings[lang]
		if synthName == settings.synth or synthName not in self.availableSynths:
			return
		self._savedParams[(lang, settings.synth)] = settings.params
		settings.synth = synthName
		settings.params = dict(self._savedParams.get((lang, synthName), {}))
		self._appliedState.pop(synthName, None)

	def ensureSynthLoaded(self, name):
		"""Starts the synthesizer if needed. Returns False if it cannot be started"""
		if name in self._synthCache:
			return True
		try:
			self._loadSynth(name)
			self._failedSynths.pop(name, None)
			return True
		except Exception:
			self._failedSynths[name] = time.monotonic()
			log.error(f"AutoLang: unable to load the {name} synthesizer", exc_info=True)
			return False

	def _computeSynthLanguages(self, name):
		"""The languages that the voices of the synthesizer speak, or UNKNOWN"""
		try:
			voices = self._synthCache[name][0].availableVoices
			languages = {_baseLanguage(getattr(voice, "language", None)) for voice in voices.values()}
		except Exception:
			log.debugWarning(f"AutoLang: unable to read the voices of {name}", exc_info=True)
			return UNKNOWN
		languages.discard(None)
		return languages or UNKNOWN

	def _getSynthLanguages(self, name, load):
		"""Returns a set of languages, UNKNOWN or False (the synthesizer cannot be used)"""
		if name in self._synthLanguages:
			return self._synthLanguages[name]
		if not load:
			return UNKNOWN
		if not self.ensureSynthLoaded(name):
			return False
		self._synthLanguages[name] = self._computeSynthLanguages(name)
		return self._synthLanguages[name]

	def getSynthChoices(self, lang, load):
		"""[(id, name)] of the synthesizers that can speak the language. With load=True every synthesizer is started
		(once) to find out its languages. The synthesizer in use is always in the list"""
		current = self._settings[lang].synth
		choices = []
		for name, info in self.availableSynths.items():
			if name != current:
				languages = self._getSynthLanguages(name, load)
				if languages is False or (languages is not UNKNOWN and lang not in languages):
					continue
			choices.append((name, info.displayName))
		return choices

	def getVoicesForLanguage(self, synthName, lang):
		"""The voices of the synthesizer that speak the language. If it reports no languages, or none of its voices
		speaks this language, all voices are returned so that the user is never left without a choice"""
		entry = self._synthCache.get(synthName)
		if entry is None:
			return OrderedDict()
		try:
			voices = entry[0].availableVoices
		except Exception:
			return OrderedDict()
		matching = OrderedDict((id, v) for id, v in voices.items() if _baseLanguage(getattr(v, "language", None)) == lang)
		return matching or voices

	def getDialogTitle(self, lang):
		# Translators: Title of the window with the settings of one language.
		# {language} is the name of the language, {synth} is the name of the synthesizer.
		return _("{language} - settings of {synth}").format(language=_languageName(lang), synth=self.getSynthDisplayName(self.getSynthName(lang)))

	def getDialogFields(self, lang):
		"""Description of the controls of the window with the settings of one language"""
		synthName = self._settings[lang].synth
		settings = self._settings[lang]
		fields = []
		main, others = self._orderedSubSettings(synthName)

		def add(setting):
			value = self._getLangValue(lang, synthName, setting)
			if isinstance(setting, NumericDriverSetting):
				try:
					value = max(setting.minVal, min(setting.maxVal, int(value)))
				except (TypeError, ValueError):
					value = setting.minVal
				fields.append(dict(
					id=setting.id, kind="slider", label=setting.displayName, value=value,
					min=setting.minVal, max=setting.maxVal, step=setting.minStep, largeStep=setting.largeStep,
				))
			elif isinstance(setting, BooleanDriverSetting):
				fields.append(dict(id=setting.id, kind="check", label=setting.displayName, value=bool(value)))
			else:
				options = [(id, info.displayName) for id, info in self._getLangAvailableValues(lang, synthName, setting).items()]
				if options:
					fields.append(dict(id=setting.id, kind="choice", label=setting.displayName, value=value, options=options))

		for setting in main:
			add(setting)
		if _symbolLevels() and self._hookActive:
			fields.append(dict(
				id="symbolLevel", kind="choice", label=_("Punctuation level"), options=_symbolLevelOptions(),
				value=LEVEL_NVDA if settings.symbolLevel is None else settings.symbolLevel,
			))
		for setting in others:
			add(setting)
		fields.append(dict(id="sendLang", kind="check", label=_("Tell the synthesizer which language is being read"), value=settings.sendLang))
		return fields

	def applyDialogValues(self, lang, values):
		"""Takes the values from the window with the settings of one language"""
		settings = self._settings[lang]
		synthName = settings.synth
		bySetting = {s.id: s for s in self._eligibleSubSettings(synthName)}
		defaults = self._synthCache[synthName][1] if synthName in self._synthCache else {}
		params = dict(settings.params)
		for id, value in values.items():
			if id == "symbolLevel":
				settings.symbolLevel = None if value == LEVEL_NVDA else value
			elif id == "sendLang":
				settings.sendLang = bool(value)
			elif id in bySetting:
				checked = self._checkValue(lang, synthName, bySetting[id], value)
				if checked is None:
					continue
				if id not in ("voice", "language") and id in defaults and defaults[id] == checked:
					# Same as the synthesizer's own value: no need to keep it
					params.pop(id, None)
				else:
					params[id] = checked
		settings.params = params
		self._appliedState.pop(synthName, None)

	def getScriptFields(self):
		fields = []
		for script, family, label, oldId in SHARED_SCRIPTS:
			options = [(id, info.displayName) for id, info in self.availableVoices.items() if id in family]
			fields.append(dict(id=script, label=label, options=options, value=getattr(self._scriptSettings, script)))
		return fields

	def applyScriptValues(self, values):
		for script, family, label, oldId in SHARED_SCRIPTS:
			if values.get(script) in family:
				setattr(self._scriptSettings, script, values[script])

	# ------------------------------------------------------------------
	# The settings ring (NVDA+Control+arrows)
	# ------------------------------------------------------------------

	def _commitRing(self):
		"""The language or the synthesizer of the settings ring changed. Start the synthesizer and rebuild the ring"""
		settings = self._settings[self._editLang]
		self._appliedState.pop(settings.synth, None)
		self._refreshRing()

	def _scheduleRingRefresh(self):
		if self._ringRefreshPending or self._terminated:
			return
		if _callAfter(self._doRingRefresh):
			self._ringRefreshPending = True

	def _doRingRefresh(self):
		self._ringRefreshPending = False
		self._refreshRing()

	def _refreshRing(self):
		"""Makes the settings ring use the settings of the language to set up"""
		try:
			import globalVars
			ring = globalVars.settingsRing
			if ring is None or synthDriverHandler.getSynth() is not self:
				return
			self._ringLang = self._editLang
			self._ringSynth = self._settings[self._editLang].synth
			self._ringMode = True
			self._allowLoad = True
			try:
				ring.updateSupportedSettings(self)
			finally:
				self._ringMode = False
				self._allowLoad = False
			self._ringDirty = False
		except Exception:
			self._ringMode = False
			self._allowLoad = False
			log.debugWarning("AutoLang: unable to refresh the settings ring", exc_info=True)

	# ------------------------------------------------------------------
	# Nested synthesizers
	# ------------------------------------------------------------------

	def _loadSynth(self, name):
		"""Returns the cached instance of the nested synthesizer, creating it if needed. May raise an exception"""
		entry = self._synthCache.get(name)
		if entry is not None:
			return entry
		synth = _getSynthInstance(name)
		defaultConf = {}
		try:
			for setting in synth.supportedSettings:
				if not hasattr(synth, setting.id):
					setattr(synth, setting.id, setting.defaultVal)
				defaultConf[setting.id] = getattr(synth, setting.id)
			# The nested synthesizer must not save its settings to the NVDA configuration
			try:
				synth._unregisterConfigSaveAction()
			except Exception:
				pass
			synth.saveSettings = lambda: None
		except Exception:
			try:
				synth.terminate()
			except Exception:
				pass
			raise
		entry = (synth, defaultConf)
		self._synthCache[name] = entry
		self._subSettingsInfo[name] = list(synth.supportedSettings)
		log.debug(f"AutoLang: loaded the {name} synthesizer")
		if name == self._settings[self._editLang].synth:
			# The settings ring needs to know the settings of this synthesizer
			self._ringDirty = True
			if self._ready:
				self._scheduleRingRefresh()
		return entry

	def _isFailed(self, name):
		failedAt = self._failedSynths.get(name)
		if failedAt is None:
			return False
		if time.monotonic() - failedAt > FAILURE_COOLDOWN:
			del self._failedSynths[name]
			return False
		return True

	def _schedulePreload(self, delay):
		"""Loads the synthesizers in advance, one by one while NVDA is idle, so that the first switch to a language
		does not freeze the screen reader"""
		if not self.preloadSynths or self._terminated:
			return
		for lang in [self._voice] + list(self._settings):
			name = self._settings[lang].synth
			if name not in self._synthCache and name not in self._preloadQueue:
				self._preloadQueue.append(name)
		if not self._preloadQueue or self._preloadRunning:
			return
		if _callLater(delay, self._preloadStep):
			self._preloadRunning = True
			self._preloadWanted = False
		else:
			# NVDA has not created its window system yet. Try again at the first speech
			self._preloadWanted = True

	def _preloadStep(self):
		if self._terminated:
			self._preloadRunning = False
			return
		# Do not interrupt the speech: try again a little later
		if self._synth is not None or not self.speechQueue.empty():
			_callLater(PRELOAD_INTERVAL, self._preloadStep)
			return
		if not self._preloadQueue:
			self._preloadRunning = False
			return
		name = self._preloadQueue.pop(0)
		if name not in self._synthCache and not self._isFailed(name):
			try:
				self._loadSynth(name)
			except Exception:
				self._failedSynths[name] = time.monotonic()
				log.error(f"AutoLang: unable to load the {name} synthesizer", exc_info=True)
		if self._preloadQueue:
			_callLater(PRELOAD_INTERVAL, self._preloadStep)
		else:
			self._preloadRunning = False

	def _getSynth(self, lang):
		"""Returns the nested synthesizer for the language with the language settings applied.
		Never raises: if the configured synthesizer is unavailable, a fallback one is used for the time being"""
		settings = self._settings[lang]
		candidates = [settings.synth]
		for name in (self._settings[self._voice].synth, DEFAULT_SYNTH):
			if name not in candidates:
				candidates.append(name)
		for name in candidates:
			if self._isFailed(name):
				continue
			try:
				synth, defaultConf = self._loadSynth(name)
			except Exception:
				self._failedSynths[name] = time.monotonic()
				log.error(f"AutoLang: unable to load the {name} synthesizer", exc_info=True)
				continue
			params = settings.params if name == settings.synth else {}
			state = (lang, _encodeParams(params))
			if self._appliedState.get(name) != state:
				try:
					self._applySettings(synth, defaultConf, params, lang)
					self._appliedState[name] = state
				except Exception:
					log.error(f"AutoLang: unable to apply the settings to the {name} synthesizer", exc_info=True)
			return synth
		return None

	def _applySettings(self, synth, defaultConf, params, lang):
		# If the synth supports a voice, then we must first set it, since other parameters can be specific to this voice
		# A synthesizer may have a language setting that decides which voices exist, so it comes first
		for first in ("language", "voice"):
			value = params.get(first)
			if value is None or not synth.isSupported(first):
				continue
			try:
				if getattr(synth, first) != value and (first != "voice" or value in synth.availableVoices):
					setattr(synth, first, value)
			except Exception:
				log.debugWarning(f"AutoLang: unable to set {first} of {synth.name}", exc_info=True)
		if "voice" not in params:
			# No voice was chosen for this language. Use the first voice that speaks it, if the synthesizer has such voices
			try:
				voices = self.getVoicesForLanguage(synth.name, lang)
				if voices and synth.isSupported("voice") and synth.voice not in voices and len(voices) != len(synth.availableVoices):
					synth.voice = next(iter(voices))
			except Exception:
				log.debugWarning(f"AutoLang: unable to choose a voice of {synth.name}", exc_info=True)
		for setting in synth.supportedSettings:
			if setting.id in ("language", "voice"):
				continue
			if setting.id in params:
				val = params[setting.id]
			elif setting.useConfig and setting.id in defaultConf:
				val = defaultConf[setting.id]
			else:
				continue
			if val is None:
				continue
			try:
				if getattr(synth, setting.id) != val:
					setattr(synth, setting.id, val)
			except Exception:
				log.debugWarning(f"AutoLang: unable to set {setting.id} of {synth.name}", exc_info=True)

	# ------------------------------------------------------------------
	# Speech
	# ------------------------------------------------------------------

	def _onSynthDoneSpeaking(self, synth):
		if synth is not self:
			if not self._doneSpeakingFlag.isSet():
				self._doneSpeakingFlag.set()
				synthDoneSpeaking.notify(synth=self)
				return
			if not _callAfter(self.pumpSpeech, synth):
				self.pumpSpeech(synth)

	def _onSynthIndexReached(self, synth, index):
		if synth is not self:
			synthIndexReached.notify(synth=self, index=index)

	def _reportIndexes(self, speechSequence):
		for item in speechSequence:
			if isinstance(item, IndexCommand):
				synthIndexReached.notify(synth=self, index=item.index)

	def _filterCommands(self, synth, speechSequence):
		"""Removes the commands that the nested synthesizer does not support"""
		supported = getattr(synth, "supportedCommands", None)
		if not supported:
			return speechSequence
		try:
			allowed = tuple(supported)
			return [item for item in speechSequence if isinstance(item, (str, IndexCommand)) or isinstance(item, allowed)]
		except Exception:
			return speechSequence

	def pumpSpeech(self, synth=None):
		if synth is not self._synth:
			if synth is not None:
				log.debugWarning(f"AutoLang: unexpected done speaking notification from {synth} synth. Current synth is {self._synth}")
			return

		while True:
			try:
				lang, speechSequence, hasText = self.speechQueue.get_nowait()
			except queue.Empty:
				self._synth = None
				synthDoneSpeaking.notify(synth=self)
				return
			if not hasText:
				self._reportIndexes(speechSequence)
				continue
			newSynth = self._getSynth(lang)
			if newSynth is None:
				# No synthesizer is available at all. Do not let NVDA wait for the speech that will never come
				self._reportIndexes(speechSequence)
				continue
			self._synth = newSynth
			self._lastSynth = newSynth
			break

		# Make sure that the synthesizer is not paused
		if self._synth in self._pausedSynths:
			self._pausedSynths.discard(self._synth)
			try:
				self._synth.pause(False)
			except Exception:
				log.debugWarning("AutoLang: unable to resume the synthesizer", exc_info=True)
		try:
			self._synth.speak(self._filterCommands(self._synth, speechSequence))
		except Exception:
			log.error("AutoLang: the synthesizer failed to speak", exc_info=True)
			self._synth = None
			self._reportIndexes(speechSequence)
			if not _callAfter(self._continueAfterError):
				self._continueAfterError()

	def _continueAfterError(self):
		if self._synth is None and not self._terminated:
			self.pumpSpeech()

	def speak(self, speechSequence):
		if self._preloadWanted or not self._uiInstalled or self._ringDirty:
			self._startLater()
		if self.useUnicodeLanguageDetection:
			speechSequence = languageDetection.addDetectedLanguageCommands(
				speechSequence, self._voice, self._scriptSettings, self.numberMode == NUMBERS_AUTO,
			)

		lang = self._voice
		settings = self._settings[lang]
		newSpeechSequence = []
		hasText = False
		for item in speechSequence:
			if isinstance(item, str):
				if item.isspace():
					continue
				if settings.sendLang and not hasText:
					newSpeechSequence.append(LangChangeCommand(lang))
				newSpeechSequence.append(item)
				hasText = True
			elif isinstance(item, LangChangeCommand):
				# For an unknown language, use the default language
				newLang = item.lang if item.lang in self.availableVoices else self._voice
				if newLang == lang:
					continue
				newSettings = self._settings[newLang]
				if newSettings.synth == settings.synth and newSettings.sendLang == settings.sendLang and newSettings.params == settings.params:
					if newSettings.sendLang and hasText:
						newSpeechSequence.append(LangChangeCommand(newLang))
				elif hasText:
					self.speechQueue.put((lang, newSpeechSequence, hasText))
					newSpeechSequence = list(filter(lambda e: not isinstance(e, (str, IndexCommand, LangChangeCommand)), newSpeechSequence))
					hasText = False
				lang = newLang
				settings = newSettings
			else:
				newSpeechSequence.append(item)

		self.speechQueue.put((lang, newSpeechSequence, hasText))
		self.pumpSpeech()

	def pause(self, switch):
		if self._synth is not None:
			if switch:
				self._pausedSynths.add(self._synth)
			else:
				self._pausedSynths.discard(self._synth)
			self._synth.pause(switch)

	def cancel(self):
		try:
			while True:
				self.speechQueue.get_nowait()
		except queue.Empty:
			pass

		if self._synth is not None:
			self._doneSpeakingFlag.clear()
			self._synth.cancel()
			self._synth = None
			# self._doneSpeakingFlag must be set even if the canceled synth does not. A timeout of 25 ms is enough
			self._doneSpeakingWatcher.watch(0.025)

	# ------------------------------------------------------------------
	# Languages and synthesizers
	# ------------------------------------------------------------------

	def _getAvailableVoices(self):
		langs = list(set(languageDetection.LATIN + languageDetection.CYRILLIC + languageDetection.ARABIC + languageDetection.DEVANAGARI + languageDetection.CJK + tuple(vars(ScriptSettings()).values())))
		langs.sort()
		voices = OrderedDict()
		for lang in langs:
			voices[lang] = VoiceInfo(lang, f"{_languageName(lang)}, {lang}", lang)
		return voices

	# The default language
	def _get_voice(self):
		return self._voice

	def _set_voice(self, voice):
		if voice in self.availableVoices:
			self._voice = voice
			if self._ready and not self._starting:
				# NVDA rebuilds the settings ring after a voice change. Add the settings of the language to it again
				self._ringDirty = True
				self._scheduleRingRefresh()

	def _getAvailableSynths(self):
		synths = OrderedDict()
		for id, displayName in synthDriverHandler.getSynthList():
			if id in (self.name, OLD_DRIVER_NAME, SILENCE_SYNTH):
				continue
			synths[id] = StringParameterInfo(id, displayName)
		return synths

	def _get_availableSynths(self):
		if not hasattr(self, "_availableSynths"):
			self._availableSynths = self._getAvailableSynths()
		return self._availableSynths

	# Numbers
	def _get_availableNumbermodes(self):
		return OrderedDict([
			(NUMBERS_DEFAULT, StringParameterInfo(NUMBERS_DEFAULT, _("Always in the default language"))),
			(NUMBERS_AUTO, StringParameterInfo(NUMBERS_AUTO, _("In the same language as the nearby text"))),
		])

	def _get_numberMode(self):
		return self._numberMode

	def _set_numberMode(self, value):
		if value in (NUMBERS_AUTO, NUMBERS_DEFAULT):
			self._numberMode = value

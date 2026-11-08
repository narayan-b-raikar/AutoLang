# Copyright (C) 2026 Dr. Narayan B Raikar
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The AutoLang controls in NVDA's Speech settings, and the two windows that open from them.

Speech settings (when AutoLang is the synthesizer) get, below "Default language":
	* Language to set up
	* Synthesizer for this language
	* a button for the voice, rate, pitch and other settings of that language (own window)
	* a button for the additional configuration: automatic detection, loading in advance and the languages of the shared
	  scripts, such as Latin and Devanagari (own window)

Nothing here changes the controls of NVDA's panel after it is built, so the panel always matches NVDA's own list of settings.
"""

import time
import wx
import addonHandler
from logHandler import log
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsDialog, VoiceSettingsPanel

addonHandler.initTranslation()

# After the user stops changing the language, the list of synthesizers is updated
REFILL_DELAY = 400  # milliseconds

_originalMakeSettings = None


def install(driverClass):
	"""Adds the AutoLang controls to NVDA's Voice settings panel (it is inside the Speech category)"""
	global _originalMakeSettings
	if _originalMakeSettings is not None:
		return
	original = VoiceSettingsPanel.makeSettings

	def makeSettings(self, settingsSizer):
		original(self, settingsSizer)
		try:
			driver = self.driver
			if isinstance(driver, driverClass):
				_PanelExtension(self, settingsSizer, driver)
		except Exception:
			log.error("AutoLang: unable to add the AutoLang controls to the Speech settings", exc_info=True)

	makeSettings._autoLangOriginal = original
	_originalMakeSettings = original
	VoiceSettingsPanel.makeSettings = makeSettings


def uninstall():
	global _originalMakeSettings
	if _originalMakeSettings is None:
		return
	current = VoiceSettingsPanel.makeSettings
	if getattr(current, "_autoLangOriginal", None) is _originalMakeSettings:
		VoiceSettingsPanel.makeSettings = _originalMakeSettings
	_originalMakeSettings = None


def _speak(message):
	try:
		import ui
		ui.message(message)
	except Exception:
		log.debugWarning("AutoLang: unable to speak a message", exc_info=True)


def _showError(parent, message):
	wx.MessageBox(message, _("AutoLang"), wx.OK | wx.ICON_ERROR, parent)


class _Busy:
	"""Shows the busy cursor while the synthesizers are being started"""

	def __enter__(self):
		try:
			wx.BeginBusyCursor()
			self.active = True
		except Exception:
			self.active = False

	def __exit__(self, *args):
		if self.active:
			try:
				wx.EndBusyCursor()
			except Exception:
				pass


class _PanelExtension:
	"""The AutoLang controls inside NVDA's Voice settings panel"""

	def __init__(self, panel, sizer, driver):
		started = time.perf_counter()
		self.panel = panel
		self.sizer = sizer
		self.driver = driver
		# NVDA keeps the panel alive; the panel keeps this object (and so the event handlers) alive
		panel._autoLangExtension = self
		self._refillToken = 0
		self._filledFor = None

		index = self._insertIndex()
		languages = driver.getLanguageChoices()
		self.languageIds = [id for id, name in languages]
		languageHelper = guiHelper.LabeledControlHelper(panel, _("Language to set up"), wx.Choice, choices=[name for id, name in languages])
		self.languageChoice = languageHelper.control
		self.languageChoice.SetSelection(self.languageIds.index(driver.editLang) if driver.editLang in self.languageIds else 0)
		self.languageChoice.Bind(wx.EVT_CHOICE, self.onLanguage)
		sizer.Insert(index, languageHelper.sizer, flag=wx.EXPAND)
		index += 1

		self.synthIds = []
		synthHelper = guiHelper.LabeledControlHelper(panel, _("Synthesizer for this language"), wx.Choice, choices=[])
		self.synthChoice = synthHelper.control
		self.synthChoice.Bind(wx.EVT_CHOICE, self.onSynth)
		self.synthChoice.Bind(wx.EVT_SET_FOCUS, self.onSynthFocus)
		sizer.Insert(index, synthHelper.sizer, flag=wx.EXPAND)
		index += 1
		# Fill the list at once with what is already known, without starting any synthesizer
		self._fillSynths(load=False)

		self.settingsButton = wx.Button(panel, label=_("Voice, rate, pitch and other settings..."))
		self.settingsButton.Bind(wx.EVT_BUTTON, self.onSettings)
		sizer.Insert(index, self.settingsButton)
		index += 1
		self.scriptsButton = wx.Button(panel, label=_("Additional language script configuration..."))
		self.scriptsButton.Bind(wx.EVT_BUTTON, self.onScripts)
		sizer.Insert(index, self.scriptsButton)

		# The controls were added after NVDA's. Put them in the right place in the tab order
		previous = getattr(panel, "voiceList", None)
		for control in (self.languageChoice, self.synthChoice, self.settingsButton, self.scriptsButton):
			if previous is not None:
				control.MoveAfterInTabOrder(previous)
			previous = control
		elapsed = (time.perf_counter() - started) * 1000
		if elapsed > 150:
			log.info(f"AutoLang: the controls of the Speech settings were added in {elapsed:.0f} ms")
		else:
			log.debug(f"AutoLang: the controls of the Speech settings were added in {elapsed:.0f} ms")

	def _insertIndex(self):
		"""Position just after NVDA's "Default language" control"""
		try:
			voiceSizer = self.panel.sizerDict.get("voice")
			for index, item in enumerate(self.sizer.GetChildren()):
				if item.GetSizer() is voiceSizer or item.GetWindow() is voiceSizer:
					return index + 1
		except Exception:
			log.debugWarning("AutoLang: unable to find the Default language control", exc_info=True)
		return 0

	@property
	def language(self):
		return self.languageIds[self.languageChoice.GetSelection()]

	def _fillSynths(self, load):
		"""Shows the synthesizers that can speak the chosen language. With load=True every installed synthesizer is
		started once to find out its languages, which can take a few seconds the first time"""
		language = self.language
		if load:
			if self.driver.needsSynthCheck(language):
				# The synthesizers have to be started once to find out their languages. Tell the user why it takes time
				_speak(_("Checking the synthesizers. Please wait."))
			with _Busy():
				choices = self.driver.getSynthChoices(language, load=True)
		else:
			choices = self.driver.getSynthChoices(language, load=False)
		self.synthIds = [id for id, name in choices]
		self.synthChoice.Set([name for id, name in choices])
		current = self.driver.getSynthName(language)
		if current in self.synthIds:
			self.synthChoice.SetSelection(self.synthIds.index(current))
		self._filledFor = language if load else None

	def onLanguage(self, evt):
		evt.Skip()
		self.driver.setEditLanguage(self.language)
		# Wait until the user stops pressing keys, then update the list of synthesizers
		self._refillToken += 1
		wx.CallLater(REFILL_DELAY, self._refillLater, self._refillToken)

	def _refillLater(self, token):
		try:
			if token == self._refillToken and self.synthChoice and self._filledFor != self.language:
				self._fillSynths(load=True)
		except RuntimeError:
			# The settings window was closed in the meantime
			pass

	def onSynthFocus(self, evt):
		try:
			if self._filledFor != self.language:
				self._fillSynths(load=True)
		finally:
			evt.Skip()

	def onSynth(self, evt):
		evt.Skip()
		selection = self.synthChoice.GetSelection()
		if 0 <= selection < len(self.synthIds):
			self.driver.selectSynth(self.language, self.synthIds[selection])

	def onSettings(self, evt):
		language = self.language
		self.driver.setEditLanguage(language)
		name = self.driver.getSynthName(language)
		with _Busy():
			started = self.driver.ensureSynthLoaded(name)
		if not started:
			# Translators: {synth} is the name of a synthesizer.
			_showError(self.panel, _("The {synth} synthesizer could not be started. Please check that it is installed.").format(synth=self.driver.getSynthDisplayName(name)))
			return
		dialog = SynthSettingsDialog(self.panel, self.driver, language, multiInstanceAllowed=True)
		dialog.ShowModal()
		self.settingsButton.SetFocus()

	def onScripts(self, evt):
		dialog = ScriptLanguagesDialog(self.panel, self.driver, multiInstanceAllowed=True)
		dialog.ShowModal()
		self.scriptsButton.SetFocus()


class _FieldsDialog(SettingsDialog):
	"""A window with a list of settings. Subclasses give the fields and take the values"""

	def __init__(self, parent, driver, **kwargs):
		self.driver = driver
		super().__init__(parent, **kwargs)

	def getFields(self):
		raise NotImplementedError

	def takeValues(self, values):
		raise NotImplementedError

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.controls = []
		for field in self.getFields():
			kind = field.get("kind", "choice")
			if kind == "choice":
				if not field["options"]:
					continue
				control = helper.addLabeledControl(field["label"], wx.Choice, choices=[name for id, name in field["options"]])
				ids = [id for id, name in field["options"]]
				control.SetSelection(ids.index(field["value"]) if field["value"] in ids else 0)
			elif kind == "slider":
				control = helper.addLabeledControl(field["label"], nvdaControls.EnhancedInputSlider, minValue=field["min"], maxValue=field["max"])
				control.SetLineSize(field["step"])
				control.SetPageSize(field["largeStep"])
				control.SetValue(field["value"])
			else:
				control = helper.addItem(wx.CheckBox(self, label=field["label"]))
				control.SetValue(bool(field["value"]))
			self.controls.append((field, control))

	def postInit(self):
		if self.controls:
			self.controls[0][1].SetFocus()

	def onOk(self, evt):
		values = {}
		for field, control in self.controls:
			kind = field.get("kind", "choice")
			if kind == "choice":
				selection = control.GetSelection()
				if selection >= 0:
					values[field["id"]] = field["options"][selection][0]
			else:
				values[field["id"]] = control.GetValue()
		try:
			self.takeValues(values)
		except Exception:
			log.error("AutoLang: unable to take the values of the settings window", exc_info=True)
		super().onOk(evt)


class SynthSettingsDialog(_FieldsDialog):
	"""Voice, variant, pitch, rate, volume, punctuation level and the other settings of the synthesizer of one language"""

	def __init__(self, parent, driver, language, **kwargs):
		self.language = language
		self.title = driver.getDialogTitle(language)
		super().__init__(parent, driver, **kwargs)

	def getFields(self):
		return self.driver.getDialogFields(self.language)

	def takeValues(self, values):
		self.driver.applyDialogValues(self.language, values)


class ScriptLanguagesDialog(_FieldsDialog):
	"""Automatic language detection, loading in advance, and the language used for text in a script that many languages
	share, such as Latin or Devanagari"""

	def __init__(self, parent, driver, **kwargs):
		self.title = _("Additional language script configuration")
		super().__init__(parent, driver, **kwargs)

	def getFields(self):
		return self.driver.getScriptFields()

	def takeValues(self, values):
		self.driver.applyScriptValues(values)

# Copyright (C) 2026 Dr. Narayan B Raikar
# This file is covered by the GNU General Public License.
# See the file COPYING.txt for more details.

"""The AutoLang settings window and the two windows that open from it.

While AutoLang is the synthesizer, NVDA's Tools menu has an "AutoLang settings..." item. It opens a window with:
	* Default language
	* Language to set up
	* Synthesizer for this language
	* a button for the voice, rate, pitch and other settings of that language (own window)
	* a button for the additional language script configuration (own window)
	* Read numbers in
	* Read symbols in

Nothing here changes NVDA's own Speech settings panel, so that panel always matches NVDA's own list of settings.
"""

import time
import wx
import gui
import addonHandler
import synthDriverHandler
from logHandler import log
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsDialog

addonHandler.initTranslation()

_driverClass = None
_menuItem = None


def install(driverClass):
	"""Adds "AutoLang settings..." to NVDA's Tools menu"""
	global _driverClass, _menuItem
	_driverClass = driverClass
	if _menuItem is not None:
		return
	toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu
	_menuItem = toolsMenu.Append(
		wx.ID_ANY,
		# Translators: A menu item of NVDA's Tools menu, and its help text
		_("AutoLang settings..."),
		_("Choose the synthesizer, voice and other settings that AutoLang uses for each language"),
	)
	gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, _onMenu, _menuItem)


def uninstall():
	global _driverClass, _menuItem
	if _menuItem is not None:
		try:
			gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, source=_menuItem)
			gui.mainFrame.sysTrayIcon.toolsMenu.Remove(_menuItem)
		except Exception:
			log.debugWarning("AutoLang: unable to remove the item of the Tools menu", exc_info=True)
	_menuItem = None
	_driverClass = None


def _onMenu(evt):
	driver = synthDriverHandler.getSynth()
	if _driverClass is None or not isinstance(driver, _driverClass):
		wx.MessageBox(_("AutoLang is not the current synthesizer."), _("AutoLang"), wx.OK | wx.ICON_ERROR, gui.mainFrame)
		return
	gui.mainFrame.popupSettingsDialog(AutoLangSettingsDialog, driver)


def _showError(parent, message):
	wx.MessageBox(message, _("AutoLang"), wx.OK | wx.ICON_ERROR, parent)


class _Busy:
	"""Shows the busy cursor while a synthesizer is being started"""

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


class AutoLangSettingsDialog(SettingsDialog):
	"""The main AutoLang window"""

	# Translators: Title of the main AutoLang window
	title = _("AutoLang settings")

	def __init__(self, parent, driver, **kwargs):
		self.driver = driver
		super().__init__(parent, **kwargs)

	def makeSettings(self, settingsSizer):
		started = time.perf_counter()
		driver = self.driver
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		languages = driver.getLanguageChoices()
		self.languageIds = [id for id, name in languages]
		languageNames = [name for id, name in languages]
		self.defaultChoice = helper.addLabeledControl(_("Default language"), wx.Choice, choices=languageNames)
		self._select(self.defaultChoice, self.languageIds, driver.voice)

		self.languageChoice = helper.addLabeledControl(_("Language to set up"), wx.Choice, choices=languageNames)
		self._select(self.languageChoice, self.languageIds, driver.editLang)
		self.languageChoice.Bind(wx.EVT_CHOICE, self.onLanguage)

		self.synthIds = []
		self.synthChoice = helper.addLabeledControl(_("Synthesizer for this language"), wx.Choice, choices=[])
		self.synthChoice.Bind(wx.EVT_CHOICE, self.onSynth)
		self.synthChoice.Bind(wx.EVT_SET_FOCUS, self.onSynthFocus)
		self._fillSynths()

		self.settingsButton = helper.addItem(wx.Button(self, label=_("Voice, rate, pitch and other settings...")))
		self.settingsButton.Bind(wx.EVT_BUTTON, self.onSettings)
		self.scriptsButton = helper.addItem(wx.Button(self, label=_("Additional language script configuration...")))
		self.scriptsButton.Bind(wx.EVT_BUTTON, self.onScripts)

		numbers = driver.getNumberChoices()
		self.numberIds = [id for id, name in numbers]
		self.numberChoice = helper.addLabeledControl(_("Read numbers in"), wx.Choice, choices=[name for id, name in numbers])
		self._select(self.numberChoice, self.numberIds, driver.numberMode)
		symbols = driver.getSymbolChoices()
		self.symbolIds = [id for id, name in symbols]
		self.symbolChoice = helper.addLabeledControl(_("Read symbols in"), wx.Choice, choices=[name for id, name in symbols])
		self._select(self.symbolChoice, self.symbolIds, driver.symbolMode)

		# Find out in the background which languages the other synthesizers speak, if that is not known yet
		driver.ensureProbing()
		elapsed = (time.perf_counter() - started) * 1000
		log.debug(f"AutoLang: the settings window was built in {elapsed:.0f} ms")

	def postInit(self):
		self.defaultChoice.SetFocus()

	@staticmethod
	def _select(choice, ids, value):
		choice.SetSelection(ids.index(value) if value in ids else 0)

	@property
	def language(self):
		return self.languageIds[self.languageChoice.GetSelection()]

	def _fillSynths(self):
		"""Shows the synthesizers that can speak the chosen language. This only uses what is known, so it is instant"""
		language = self.language
		choices = self.driver.getSynthChoices(language)
		self.synthIds = [id for id, name in choices]
		self.synthChoice.Set([name for id, name in choices])
		current = self.driver.getSynthName(language)
		if current in self.synthIds:
			self.synthChoice.SetSelection(self.synthIds.index(current))

	def onLanguage(self, evt):
		evt.Skip()
		self.driver.setEditLanguage(self.language)
		self._fillSynths()

	def onSynthFocus(self, evt):
		# The background check may have found more by now
		try:
			shown = [self.synthChoice.GetString(i) for i in range(self.synthChoice.GetCount())]
			if shown != [name for id, name in self.driver.getSynthChoices(self.language)]:
				self._fillSynths()
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
			_showError(self, _("The {synth} synthesizer could not be started. Please check that it is installed.").format(synth=self.driver.getSynthDisplayName(name)))
			return
		dialog = SynthSettingsDialog(self, self.driver, language, multiInstanceAllowed=True)
		dialog.ShowModal()
		self.settingsButton.SetFocus()

	def onScripts(self, evt):
		dialog = ScriptLanguagesDialog(self, self.driver, multiInstanceAllowed=True)
		dialog.ShowModal()
		self.scriptsButton.SetFocus()

	def onOk(self, evt):
		try:
			self.driver.applyMainValues(
				self.languageIds[self.defaultChoice.GetSelection()],
				self.numberIds[self.numberChoice.GetSelection()],
				self.symbolIds[self.symbolChoice.GetSelection()],
			)
			self.driver.saveSettings()
		except Exception:
			log.error("AutoLang: unable to take the values of the settings window", exc_info=True)
		super().onOk(evt)

	def onCancel(self, evt):
		# Leave everything as it was saved
		try:
			self.driver.loadSettings()
		except Exception:
			log.error("AutoLang: unable to restore the settings", exc_info=True)
		super().onCancel(evt)


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

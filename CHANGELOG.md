# Changelog

All notable changes to AutoLang are listed here. Versions are written as `year.month.number`.

## 2026.11.13

### Changed
- **AutoLang settings now have a window of their own, in NVDA's Tools menu** ("AutoLang settings..."). It replaces the extra controls that were inside NVDA's Speech settings. NVDA's Speech settings now show only the default language for AutoLang. The menu item exists only while AutoLang is the synthesizer.
- The window holds: default language, language to set up, synthesizer for that language, the two buttons (voice, rate, pitch and other settings; additional language script configuration), read numbers in, and read symbols in. OK saves; Cancel forgets the changes made in the window.
- The list of synthesizers for a language is now instant. AutoLang finds out the languages that the synthesizers speak in the background after NVDA starts (one synthesizer at a time, each stopped after it is checked) and remembers the answer for a week. A synthesizer that could not be started is not tried again for a day. Synthesizers that are not checked yet are listed for every language.
- "Read numbers in" and "Read symbols in" are saved by AutoLang itself under the same names as before.

### Added
- **None** for the voice, the variant and the language setting of a synthesizer. It is selected when nothing was chosen. It means: use the synthesizer's own value (for the voice: the own voice if it speaks the language, otherwise the first voice that does).

### Fixed
- A language that did not choose a variant or voice could keep the variant or voice that another language had set on the same synthesizer.
- The delay when choosing a language and moving to the list of synthesizers.

## 2026.11.12

### Added
- **Read symbols in**: choose whether the names of symbols (comma, question mark and so on) are read in the default language or in the language of the text around them. It sits next to "Read numbers in".
- A spoken message, "Checking the synthesizers. Please wait.", when the synthesizers have to be started to find out which languages they speak.
- The time that the AutoLang controls need to appear in the Speech settings is written to the NVDA log, to help find slow starts.

### Changed
- "Languages for scripts" is now **Additional language script configuration**. "Find the language automatically from the script" and "Load synthesizers in advance" moved into it, together with the languages of the shared scripts.
- The languages that each synthesizer speaks are saved in the configuration and trusted for a week. After the first check, choosing a language and moving to the synthesizer list is quick and no synthesizer has to be started for it. A synthesizer that is started for any other reason is checked at the same time.
- The two options that moved are saved by AutoLang itself under the same names as before, so earlier choices are kept.

### Fixed
- The pause after choosing a language and pressing Tab to the synthesizer list (all synthesizers were being started at that moment).
- A Python deprecation warning (`isSet`) that was written to the NVDA log while speaking.
- A harmless "unexpected done speaking" warning that was written to the log whenever speech was cancelled. It is now a debug message.

## 2026.11.11

### Changed
- New settings design. The Speech settings now have fixed controls: default language, language to set up, synthesizer for that language, and two buttons.
- The voice, variant, pitch, rate, volume, punctuation level and synthesizer-specific settings of a language are in their own window.
- The languages of the shared scripts (Latin, Cyrillic, Arabic, Devanagari, CJK) are in their own window.
- For a language, only the synthesizers that can speak it are listed, and only the voices that speak it.
- Only values that differ from the synthesizer's own values are stored in the configuration.

### Fixed
- The Speech settings window stopped working after the language or the synthesizer was changed, and could not be closed. NVDA's settings panel is not rebuilt any more.

## 2026.11.5 to 2026.11.10

- Fixed a freeze of the Speech settings window when a synthesizer with check box settings, such as IBMTTS, was replaced.
- Fixed NVDA starting with another synthesizer after a restart: the add-on used the window system before NVDA had created it.
- Added the settings ring (NVDA+Control+arrows) for the synthesizer, voice, variant, pitch, rate and volume of a language.

## 2026.11.1 to 2026.11.4

- First AutoLang versions, made from MultiLang 2024.
- Synthesizers are started in the background after NVDA starts, so the first switch to a language has no delay.
- Voice, rate, pitch, volume and punctuation level for every language.
- Settings of the old MultiLang add-on are imported.
- Fixed: language settings were not saved when NVDA saved its configuration; a failed synthesizer overwrote the user's choice; the language written in the text was overridden by the Latin setting; zero-width joiners in Indian-language text.

## MultiLang

AutoLang is based on MultiLang by Alexander Linkov (Kvark).

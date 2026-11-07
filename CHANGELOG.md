# Changelog

All notable changes to AutoLang are listed here. Versions are written as `year.month.number`.

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

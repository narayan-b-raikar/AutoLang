# AutoLang

**A multilingual virtual speech synthesizer for the [NVDA](https://www.nvaccess.org/) screen reader.**

![License](https://img.shields.io/badge/license-GPL--2.0-blue)
![NVDA](https://img.shields.io/badge/NVDA-2023.2%20to%202027.1-green)

AutoLang finds the language of a text from its writing script and reads each part with the synthesizer, voice, rate, pitch, volume and punctuation level that **you** chose for that language. A line that mixes Kannada, Hindi and English is read by three different voices, without any manual switching.

## Features

- **Automatic language switching** based on Unicode scripts, including Kannada, Hindi, Tamil, Telugu, Malayalam, Bengali, Gujarati, Gurmukhi, Odia, Sinhala, Latin, Cyrillic, Arabic, Chinese, Japanese, Korean and many more.
- **A different synthesizer for every language.** Use eSpeak NG, IBMTTS (Eloquence), Vocalizer, Windows OneCore, SAPI 5 or any other installed NVDA synthesizer, side by side.
- **Per-language settings:** voice, variant, pitch, rate, volume, punctuation level, and every setting that is specific to the chosen synthesizer (inflection, rate boost, head size, roughness, breathiness and so on). Only the settings that the synthesizer really has are shown.
- **Only what fits the language.** For a language, only the synthesizers that can speak it are offered, and only the voices that speak it.
- **A settings window of its own** in NVDA's Tools menu, with separate windows for the synthesizer settings of a language and for the additional language script configuration (automatic detection, loading in advance, and the languages of shared scripts such as Latin and Devanagari). NVDA's own Speech settings stay as they are.
- **"None" for voice and variant:** leave them unchosen and AutoLang uses the synthesizer's own voice and variant, or the first voice that speaks the language.
- **Numbers and symbols:** choose whether numbers and the names of symbols such as comma are read in the default language or in the language of the text around them.
- **NVDA settings ring support:** change the synthesizer, voice, variant, pitch, rate and volume of a language quickly from the keyboard.
- **No pauses.** Synthesizers are started in the background after NVDA starts, so the first switch to a language is instant. A synthesizer that fails to start never stops NVDA from speaking.
- **Safe at startup:** AutoLang never prevents NVDA from starting with it as the chosen synthesizer.

## Requirements

- NVDA 2023.2 or newer (checked against the NVDA 2025.3, 2026.3 and development sources, which cover the 2026.4 and 2027.1 line).
- At least one other synthesizer, for example the eSpeak NG that comes with NVDA.

## Installation

1. Download `AutoLang-V<version>.nvda-addon` from the [Releases](../../releases) page.
2. Open the file. NVDA asks to install it. Restart NVDA when asked.
3. Press `NVDA+Control+S`, choose **AutoLang** and press OK.

## Quick start

1. Open the NVDA menu (`NVDA+N`), then **Tools**, then **AutoLang settings...**.
2. In **Language to set up**, choose a language, for example Kannada.
3. In **Synthesizer for this language**, choose the synthesizer.
4. Press **Voice, rate, pitch and other settings...** and choose the voice and the other settings in the window that opens. Press OK.
5. Repeat for every language you read. Press **Additional language script configuration...** to choose which language is used for Latin, Cyrillic, Arabic, Devanagari and CJK text, and to switch automatic detection and loading in advance on or off.
6. Press OK in the AutoLang settings window.

The full guide is in [`addon/doc/en/readme.md`](addon/doc/en/readme.md).

## How it works

AutoLang is an NVDA synthesizer driver. It does not make sound by itself. It splits the speech into pieces by language and passes every piece to the nested synthesizer of that language.

| Part | File | Job |
| --- | --- | --- |
| Driver | `addon/synthDrivers/AutoLang/__init__.py` | Splits speech by language, runs the nested synthesizers, keeps the settings, builds the settings ring |
| Language detection | `addon/synthDrivers/AutoLang/languageDetection.py`, `scripts.py` | Finds the language of text from the Unicode script of its characters |
| Settings windows | `addon/synthDrivers/AutoLang/settingsUi.py` | The Tools menu item, the AutoLang settings window and the two windows that open from it |

Design decisions worth knowing:

- NVDA starts the synthesizer *before* its window system exists. AutoLang therefore does nothing with windows at that time, and adds its Tools menu item and starts its background work later.
- The list of settings that NVDA reads from the driver (`supportedSettings`) holds only the default language. The per-language settings live in AutoLang's own windows (opened from the Tools menu), so NVDA's Speech panel never needs to be rebuilt. Only the settings ring gets a longer list, and only while it is being built.
- A synthesizer's languages are read from the `language` of its voices. A synthesizer that does not report languages is offered for every language. The synthesizers that are not in use are started once in the background, one by one, then stopped. What is learned is saved in the configuration and trusted for a week, so the synthesizer list of the window is always instant.

## Building

```
pip install markdown polib      # optional: builds the guide and the translations
python build.py
```

The add-on is written to `dist/AutoLang-V<version>.nvda-addon`.

## Tests

```
python -m unittest discover -s tests -v
```

The tests of the language detection do not need NVDA. The driver and the settings windows depend on NVDA itself and must be tried in NVDA.

## Translations

`translations/AutoLang.pot` lists the text of the user interface. Translations are in `addon/locale/<language>/LC_MESSAGES/nvda.po`. Russian and Kannada are included.

## Contributing

Issues and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first. When you report a problem, add the lines of the NVDA log (`NVDA+F1`) that contain the word `AutoLang`.

## Credits and license

- Made and maintained by **Dr. Narayan B Raikar**.
- Based on **MultiLang** by **Alexander Linkov (Kvark)**: <https://gitverse.ru/kvark128/MultiLang>. AutoLang keeps his language detection and the idea of a virtual synthesizer that switches languages, and extends them.
- Licensed under the **GNU General Public License, version 2**. See [LICENSE](LICENSE).

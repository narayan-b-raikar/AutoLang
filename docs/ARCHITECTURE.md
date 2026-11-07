# AutoLang architecture

## Speech

1. NVDA sends a speech sequence to `SynthDriver.speak`.
2. `languageDetection.addDetectedLanguageCommands` adds a language command in front of every piece of text, from the Unicode script of its characters. Numbers and symbols belong to no script.
3. `speak` puts the pieces that use the same synthesizer and the same settings together, and queues the others separately.
4. `pumpSpeech` takes the next piece, gets the nested synthesizer for its language (`_getSynth`), applies the language's settings to it (`_applySettings`) and speaks. When the nested synthesizer reports that it has finished, the next piece is taken.
5. If a nested synthesizer cannot start, the synthesizer of the default language, or eSpeak NG, is used for a minute. NVDA is never left waiting.

## Settings

Everything the user sets for a language is kept in memory in `VoiceSettings` and saved in NVDA's configuration under `[speech][AutoLang][languages][<language code>]`:

| Key | Meaning |
| --- | --- |
| `synth` | Name of the synthesizer for the language |
| `sendLang` | Whether the nested synthesizer is told the language of the text |
| `params` | JSON with the voice, variant, pitch, rate, volume and other values that differ from the synthesizer's own, and the punctuation level |

`scriptLanguages` (JSON) holds the languages of the shared scripts.

NVDA reads a driver's `supportedSettings` to build the Speech panel and to save and load settings. AutoLang keeps this list fixed (default language, automatic detection, number mode, advance loading). The settings that depend on the language and the synthesizer are shown by `settingsUi.py` in separate controls and windows.

## Settings ring

The settings ring (NVDA+Control+arrows) reads `supportedSettings` when it is built. `SynthDriver._refreshRing` switches the driver to a "ring mode" for that moment, so that the list also holds the settings of the language to set up. Ring entries are proxies whose values are read and written through `__getattr__` and `__setattr__`.

## Punctuation level per language

NVDA turns punctuation into words before the text reaches the synthesizer, with one level for all text. AutoLang wraps `speech.speech.processText` while it is the synthesizer, finds the language of the text and replaces the level if that language has its own. A level that NVDA forces, for example when it spells a word, is left as it is.

## Start order

NVDA creates the synthesizer before its window system. `initSettings` must not fail and must not use `wx`. `_startLater` finishes the work when the window system exists: it adds the controls to the Speech panel (`settingsUi.install`), starts the background loading of the synthesizers and builds the settings ring.

# AutoLang

Version 2026.11.13

AutoLang is a multilingual virtual speech synthesizer for NVDA. It finds the language of the text from its script (for example Kannada, Hindi, Tamil or English letters) and reads each part in the right language. For every language you can choose a different synthesizer, voice, rate, pitch and volume.

## Credits

* AutoLang is made and maintained by **Dr. Narayan B Raikar**.
* It is based on the **MultiLang** add-on written by **Alexander Linkov (Kvark)**. Please support the original author.
    * Original project: <https://gitverse.ru/kvark128/MultiLang>
    * Original author's e-mail: kvark128@yandex.ru
* License: GNU General Public License (see the file COPYING.txt).

## How to start

1. Press NVDA+Control+S, choose **AutoLang** and press OK.
2. Open the NVDA menu (NVDA+N), go to **Tools** and choose **AutoLang settings...**. (This item is in the Tools menu only while AutoLang is your synthesizer.)
3. Set up each language you need, as given below.
4. Press OK. Your settings are saved, like the other NVDA settings.

NVDA's own Speech settings show only **Default language** for AutoLang. All the other AutoLang settings are in the AutoLang settings window.

## The AutoLang settings window

The window has these controls, in this order:

1. **Default language**: the main language of NVDA. It is also used for text that has no script of its own, such as numbers and symbols.
2. **Language to set up**: choose the language you want to set up, for example Kannada. This does not change the default language.
3. **Synthesizer for this language**: the synthesizer that will read this language. Only the synthesizers that can speak the language are shown. This list appears at once. AutoLang finds out the languages of your synthesizers in the background after NVDA starts and remembers them for a week. A synthesizer that has not been checked yet is shown for every language. The synthesizer that is already chosen for the language is always shown.
4. **Voice, rate, pitch and other settings** button: opens a separate window (see below).
5. **Additional language script configuration** button: opens a separate window (see below).
6. **Read numbers in**: "Always in the default language" or "In the same language as the nearby text".
7. **Read symbols in**: "Always in the default language" or "In the language of the text". Symbols are the signs such as comma and question mark that NVDA reads aloud as words. With the second choice, the name of the symbol is spoken in the language of the text around it (if NVDA has symbol names for that language).

Press OK to save everything. Press Cancel to leave the window and forget the changes you made in it.

## Voice, rate, pitch and other settings window

Press the button after the synthesizer list. A window opens for the language and synthesizer you chose. It shows these settings, in this order:

1. **Voice**: only the voices that speak this language are shown. If the synthesizer does not tell the language of its voices, all voices are shown. **None** is the first choice. It means that you have not chosen a voice: AutoLang then uses the synthesizer's own voice, or the first voice that speaks the language.
2. **Variant**: **None** means the synthesizer's own variant.
3. **Pitch**, **Rate** and **Volume**
4. **Punctuation level**: Same as NVDA setting, none, some, most or all. Each language can have its own level, and it is used for text written in that language.
5. **Other settings of the synthesizer**: for example language (which also has **None**), inflection, rate boost, head size, roughness and breathiness. You see only the settings that your synthesizer has.
6. **Tell the synthesizer which language is being read**: keep this on, unless your synthesizer has a problem with it.

Press OK to go back to the AutoLang settings window. Press Cancel to leave this window without changes. Your choices are saved when you press OK in the AutoLang settings window.

## Additional language script configuration window

Press the button after the voice settings button. This window has settings that are for all languages:

1. **Find the language automatically from the script**: switch automatic language detection on or off. Keep it on to let AutoLang switch languages by itself.
2. **Load synthesizers in advance (avoids delay)**: see "Speed" below.
3. **The language for each shared script.** Many languages share one script. For example, English, German and French all use Latin letters, and Hindi and Marathi both use Devanagari. Here you choose the language that is used for each of these scripts: Latin, Cyrillic, Arabic, Devanagari, and Chinese, Japanese and Korean. Kannada, Tamil, Telugu and other scripts that belong to one language need no choice.

## Settings ring

Use NVDA+Control+Left or Right arrow to move between the settings, and NVDA+Control+Up or Down arrow to change the value. If your NVDA key is CapsLock, use CapsLock+Control+arrows.

The ring works on the language chosen in "Language to set up" (in the AutoLang settings window or in the ring). It has:

1. Language to set up
2. Synthesizer
3. Voice
4. Variant
5. Pitch
6. Rate
7. Volume
8. Default language

The ring starts on Rate. When you change the language or the synthesizer in the ring, the next items change to match. A synthesizer without variants has no Variant item. Ring changes are saved when NVDA saves its settings (press NVDA+Control+C, or turn on "Save configuration on exit" in General settings).

## Speed

A moment after NVDA starts, AutoLang loads the synthesizers you chose, one by one in the background. So there is no delay when a language is used for the first time. You can switch this off in the additional language script configuration window. If a synthesizer cannot start, AutoLang keeps speaking with the synthesizer of the default language (or eSpeak NG) and tries again after one minute.

## If you used MultiLang before

The first time AutoLang starts, it copies your synthesizer choices from MultiLang. After that, please remove the MultiLang add-on. Voice, rate, pitch and volume must be set again. Settings profiles are not used any more.

## If something goes wrong

* Open the NVDA log (NVDA+F1) and find lines with the word "AutoLang". Send these lines to the person who maintains the add-on.
* To keep AutoLang after restarting NVDA, save your settings: press NVDA+Control+C, or turn on "Save configuration on exit" in General settings.

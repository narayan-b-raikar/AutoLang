# Contributing to AutoLang

Thank you for your interest in AutoLang.

## Report a problem

Please open an issue and tell us:

- the NVDA version,
- the synthesizers you use for the languages,
- what you did, what you expected and what happened,
- the lines of the NVDA log (`NVDA+F1`) that contain `AutoLang`.

## Code

- The add-on is in `addon/`. Python files use tabs, like NVDA.
- Do not use NVDA's window system (`wx`) while the synthesizer is starting. NVDA creates it later. Use the helpers `_callAfter` and `_callLater` of the driver, which do nothing until it exists.
- Do not change the list of settings that NVDA reads from the driver (`supportedSettings`) while NVDA's Speech panel is open. NVDA needs a control for every setting in the list.
- Run the tests and build the add-on before you send a pull request:

```
python -m unittest discover -s tests -v
python build.py
```

- Install the built add-on in NVDA and check at least: starting NVDA with AutoLang chosen, the Speech settings, both settings windows, Cancel and OK, and speaking text that mixes two languages.

## Translations

Copy `translations/AutoLang.pot` to `addon/locale/<language>/LC_MESSAGES/nvda.po`, translate it and run `python build.py`.

## License

By contributing you agree that your work is licensed under the GNU General Public License, version 2.

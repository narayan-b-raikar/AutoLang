# AutoLang

**A Multilingual Virtual Speech Synthesizer for the [NVDA](https://www.nvaccess.org/) Screen Reader**

![License](https://img.shields.io/badge/license-GPL--2.0-blue)
![NVDA](https://img.shields.io/badge/NVDA-2023.2%20to%202027.1-green)

**AutoLang** dynamically detects the language of input text based on its Unicode script character set and routes discrete segments to designated synthesizers, voices, rate profiles, pitch profiles, volume levels, and punctuation thresholds configured for each script. For instance, a single continuous line containing a mix of Kannada, Hindi, and English is processed sequentially through three distinct text-to-speech engines without manual intervention.

---

## Key Features

- **Automated Script-Based Language Switching:** Supports real-time Unicode script recognition across Kannada, Hindi, Tamil, Telugu, Malayalam, Bengali, Gujarati, Gurmukhi, Odia, Sinhala, Latin, Cyrillic, Arabic, Chinese, Japanese, Korean, and various other global writing systems.
- **Independent Per-Language Synthesizer Routing:** Assign individual engines—such as eSpeak NG, IBMTTS (Eloquence), Vocalizer, Windows OneCore, SAPI 5, or any standard NVDA-compatible driver—simultaneously across different scripts.
- **Granular Parameter Customisation:** Configurable per-language parameters include voice selection, voice variant, pitch, speaking rate, master volume, punctuation verbosity, and engine-specific parameters (e.g., inflection, rate boost, head size, roughness, breathiness). Interface controls adapt dynamically to display only supported parameters for a given engine.
- **Context-Aware Engine Filtering:** Offers only speech engines and localized voices capable of processing the targeted language profile.
- **Native NVDA Integration:** Integrated directly into NVDA’s Speech settings panel, complemented by dedicated modular dialogs for managing engine properties and script-to-language mappings (e.g., Latin, Devanagari).
- **NVDA Settings Ring Integration:** Modify synthesizer, voice profile, pitch, rate, and volume parameters on the fly via standard desktop shortcuts.
- **Asynchronous Engine Initialization:** Initializes engines non-blockingly in the background following NVDA startup, eliminating delay during initial language switches. Faulty or non-responsive engines are isolated to prevent core screen-reader disruption.
- **Fail-Safe Startup Architecture:** Engineered to ensure NVDA remains operational under all startup conditions, even if initialized as the active default synthesizer.

---

## System Requirements

- **NVDA Version:** 2023.2 or newer (tested against NVDA 2025.3, 2026.3, and active development builds up to the 2026.4 / 2027.1 cycle).
- **Dependencies:** Requires at least one secondary speech synthesizer engine installed (e.g., bundled eSpeak NG).

---

## Installation

1. Download the latest `AutoLang-V<version>.nvda-addon` package from the [Releases](../../releases) directory.
2. Execute the file to prompt NVDA installation, and confirm the application restart.
3. Open the synthesizer selection dialog using `NVDA+Control+S`, select **AutoLang**, and confirm with **OK**.

---

## Quick Start Guide

1. Launch Speech Settings via `NVDA+Control+V`.
2. Locate **Language to set up** and select your target language (e.g., **Kannada**).
3. Under **Synthesizer for this language**, assign your preferred engine.
4. Click **Voice, rate, pitch and other settings...** to configure engine-specific parameters in the pop-up modal, then confirm with **OK**.
5. Repeat the process for required language profiles. Utilize **Languages for scripts...** to assign primary language mappings for shared scripts (e.g., Latin, Cyrillic, Arabic, Devanagari, CJK).
6. Click **OK** to commit changes within NVDA Speech Settings.

For comprehensive configuration guidelines, refer to the full documentation at [`addon/doc/en/readme.md`](addon/doc/en/readme.md).

---

## Architecture & Implementation

AutoLang functions as a virtual driver layer for NVDA speech synthesis. Rather than producing audio natively, it parses incoming text strings into discrete language tokens and dispatches them to their corresponding underlying synthesizer instances.

| Component | Target File | Core Functionality |
| :--- | :--- | :--- |
| **Driver Engine** | `addon/synthDrivers/AutoLang/__init__.py` | Executes text parsing, orchestrates child engine instances, manages parameter state, and populates the settings ring. |
| **Language Detection** | `addon/synthDrivers/AutoLang/languageDetection.py`<br>`addon/synthDrivers/AutoLang/scripts.py` | Performs character-level Unicode script analysis to determine language boundaries. |
| **User Interface** | `addon/synthDrivers/AutoLang/settingsUi.py` | Manages Speech panel integration and auxiliary configuration dialogs. |

### Technical Considerations

- **Lifecycle Synchronization:** NVDA initializes speech drivers prior to rendering window systems. AutoLang defers GUI component initialization and background process invocation until the GUI loop active state is confirmed.
- **Fixed Interface Signatures:** AutoLang maintains a constant `supportedSettings` registration within NVDA’s master Speech panel to maintain UI stability. Specific per-language parameters are handled within secondary dedicated interface modals, updating the settings ring dynamically during runtime.
- **Capability Discovery:** Driver language compatibility is derived from metadata reported by individual voice profiles. Synthesizers omitting language tags are treated as universal fallback engines.

---

## Build System

To compile the add-on from source:

```bash
# Optional dependencies for rendering documentation and localization files
pip install markdown polib

# Execute build workflow
python build.py
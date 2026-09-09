"""Shared offline Japanese translation service."""


class ArgosTranslator:
    """Translate Japanese into English and Traditional Chinese with local models."""

    def __init__(self) -> None:
        try:
            import argostranslate.translate
            from opencc import OpenCC
        except ImportError as error:
            raise RuntimeError(
                "Translation dependencies are missing; install the translation extra"
            ) from error

        installed_codes = {
            language.code for language in argostranslate.translate.get_installed_languages()
        }
        missing = {"ja", "en", "zh"} - installed_codes
        if missing:
            raise RuntimeError(
                "Argos language models are incomplete (missing: "
                + ", ".join(sorted(missing))
                + ")"
            )
        self._english = argostranslate.translate.get_translation_from_codes("ja", "en")
        self._chinese = argostranslate.translate.get_translation_from_codes("ja", "zh")
        if self._english is None or self._chinese is None:
            raise RuntimeError("Argos has no usable ja->en and ja->zh translation paths")
        self._traditional = OpenCC("s2twp")

    def translate(self, text: str, target: str) -> str:
        if target == "en":
            result = self._english.translate(text)
        elif target == "zh":
            result = self._traditional.convert(self._chinese.translate(text))
        else:
            raise ValueError(f"Unsupported target language: {target}")
        return result.strip()

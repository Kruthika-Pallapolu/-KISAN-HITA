import { LANGUAGES, type SupportedLanguage } from '../i18n/translations.ts';

export const LANGUAGE_PREFERENCE_KEY = 'kisan_hita_lang';

export function readLanguagePreference(storage: Pick<Storage, 'getItem'> = localStorage): SupportedLanguage | null {
  const saved = storage.getItem(LANGUAGE_PREFERENCE_KEY);
  return LANGUAGES.some((language) => language.code === saved) ? saved as SupportedLanguage : null;
}

export function saveLanguagePreference(language: SupportedLanguage, storage: Pick<Storage, 'setItem'> = localStorage): void {
  storage.setItem(LANGUAGE_PREFERENCE_KEY, language);
}

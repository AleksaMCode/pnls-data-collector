const LOCALE_MAP = {
  en: 'en-US',
  fr: 'fr-FR',
  de: 'de-DE',
};

export function getLanguageCode(resolvedLanguage) {
  return (resolvedLanguage || 'en').split('-')[0];
}

export function getLocale(resolvedLanguage, fallback = 'en-US') {
  const languageCode = getLanguageCode(resolvedLanguage);
  return LOCALE_MAP[languageCode] ?? fallback;
}

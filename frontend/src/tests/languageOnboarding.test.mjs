import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { readLanguagePreference, saveLanguagePreference, LANGUAGE_PREFERENCE_KEY } from '../services/languagePreference.ts';
import { authErrorTranslationKey } from '../services/authErrors.ts';
import { LANGUAGES, translations } from '../i18n/translations.ts';

test('first visit has no assumed language, and a choice persists for the next visit', () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  assert.equal(readLanguagePreference(storage), null);
  saveLanguagePreference('en', storage);
  assert.equal(values.get(LANGUAGE_PREFERENCE_KEY), 'en');
  assert.equal(readLanguagePreference(storage), 'en');
  saveLanguagePreference('te', storage);
  assert.equal(readLanguagePreference(storage), 'te');
  values.set(LANGUAGE_PREFERENCE_KEY, 'xx');
  assert.equal(readLanguagePreference(storage), null);
});

test('first-visit language chooser exposes all seven native labels and blocks login until selection', () => {
  const chooser = readFileSync(new URL('../components/FirstVisitLanguageSelection.tsx', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../App.tsx', import.meta.url), 'utf8');
  assert.match(chooser, /item\.nativeName/);
  assert.match(chooser, /onClick=\{\(\) => setLanguage\(item\.code\)\}/);
  assert.match(app, /hasChosenLanguage[\s\S]*<AuthPage onContinueGuest=/);
  for (const language of LANGUAGES) assert.ok(translations[language.code].firstVisitLanguageQuestion);
});

test('language preference onboarding does not request wake phrase or microphone setup', () => {
  const modal = readFileSync(new URL('../components/LanguageModal.tsx', import.meta.url), 'utf8');
  const settings = readFileSync(new URL('../components/SettingsModal.tsx', import.meta.url), 'utf8');
  assert.match(modal, /setLanguage\(code\)/);
  assert.doesNotMatch(modal, /wakePhrase|VoiceRecognitionService|Microphone/);
  assert.doesNotMatch(settings, /wakePhrase|wake phrase/i);
});

test('assistant identity remains fixed and no wake assistant component is mounted', () => {
  const identity = readFileSync(new URL('../services/productIdentity.ts', import.meta.url), 'utf8');
  const navbar = readFileSync(new URL('../components/Navbar.tsx', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../App.tsx', import.meta.url), 'utf8');
  assert.match(identity, /KISAN_HITA_NAME\s*=\s*'Kisan Hita'/);
  assert.match(navbar, /KISAN_HITA_NAME/);
  assert.doesNotMatch(app, /HeyKisanVoiceMode|hands-free-voice-widget/);
  assert.doesNotMatch(navbar, /profile\.assistantName/);
});

test('guest entry opens the real app with a server-issued session and per-guest state', () => {
  const authPage = readFileSync(new URL('../pages/AuthPage.tsx', import.meta.url), 'utf8');
  const authContext = readFileSync(new URL('../context/AuthContext.tsx', import.meta.url), 'utf8');
  const assistantContext = readFileSync(new URL('../context/AssistantContext.tsx', import.meta.url), 'utf8');
  const farmContext = readFileSync(new URL('../context/FarmProfileContext.tsx', import.meta.url), 'utf8');
  const backendAuth = readFileSync(new URL('../../../backend/app/auth.py', import.meta.url), 'utf8');
  const backendRoutes = readFileSync(new URL('../../../backend/app/routers/authentication.py', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../App.tsx', import.meta.url), 'utf8');
  assert.match(authPage, /Continue without an account/);
  assert.match(authPage, /onContinueGuest/);
  assert.match(authContext, /fetch\('\/api\/auth\/guest'/);
  assert.match(authContext, /credentials: 'same-origin'/);
  assert.match(app, /if \(!user && !isGuest\)/);
  assert.match(app, /<FarmProfileProvider isGuest=\{isGuest\} guestContextId=\{guestContextId\}><AssistantProvider isGuest=\{isGuest\}/);
  assert.doesNotMatch(app, /GuestLandingPage/);
  assert.match(assistantContext, /window\.sessionStorage/);
  assert.match(assistantContext, /kisan_hita_guest_\$\{guestScope\}/);
  assert.match(farmContext, /if \(isGuest\) \{ setProfileLoaded\(true\); return; \}/);
  assert.match(backendAuth, /session\["session_type"\] != "account"/);
  assert.match(backendAuth, /return f"guest:\{session\['session_id'\]\}"/);
  assert.match(backendRoutes, /@router\.post\("\/guest"\)/);
  assert.match(backendRoutes, /@router\.post\("\/guest\/end"\)/);
});

test('login interface uses the selected language and synchronizes profile preference after authentication', () => {
  const authPage = readFileSync(new URL('../pages/AuthPage.tsx', import.meta.url), 'utf8');
  const authContext = readFileSync(new URL('../context/AuthContext.tsx', import.meta.url), 'utf8');
  assert.match(authPage, /const text = COPY\[language\]/);
  assert.match(authPage, /t\(authErrorTranslationKey\(error\)\)/);
  assert.match(authPage, /noValidate/);
  assert.match(authContext, /setLanguage\(profile\.selected_language/);
  assert.match(authContext, /language: input\.language/);
});

test('authentication failures map to localized error keys instead of exposing server wording', () => {
  assert.equal(authErrorTranslationKey('An account with this email already exists.'), 'authAccountExists');
  assert.equal(authErrorTranslationKey('Email or password is incorrect.'), 'authInvalidCredentials');
  assert.equal(authErrorTranslationKey('Password must be between 10 and 128 characters.'), 'authPasswordLength');
  assert.equal(authErrorTranslationKey('Failed to fetch'), 'authGenericError');
  for (const language of ['te', 'en', 'hi', 'ta', 'kn', 'ml', 'mr']) {
    for (const key of ['authEmailRequired', 'authEmailInvalid', 'authPasswordRequired', 'authPasswordMismatch', 'authAccountExists', 'authInvalidCredentials', 'authPasswordLength', 'authPasswordInvalid', 'authGenericError']) {
      assert.ok(translations[language][key], `${language}.${key} is required`);
    }
  }
});

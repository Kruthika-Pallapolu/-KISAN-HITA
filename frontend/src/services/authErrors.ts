export function authErrorTranslationKey(message: string): string {
  const normalized = message.toLocaleLowerCase();
  if (normalized.includes('already exists')) return 'authAccountExists';
  if (normalized.includes('email or password') || normalized.includes('invalid credentials')) return 'authInvalidCredentials';
  if (normalized.includes('between 10 and 128') || normalized.includes('between 10 and')) return 'authPasswordLength';
  if (normalized.includes('valid password')) return 'authPasswordInvalid';
  return 'authGenericError';
}

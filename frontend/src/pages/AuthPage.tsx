import React, { FormEvent, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import type { SupportedLanguage } from '../i18n/translations';
import { authErrorTranslationKey } from '../services/authErrors';

const COPY: Record<SupportedLanguage, Record<string, string>> = {
  en: { title: 'Kisan Hita', subtitle: 'Your farming companion', signin: 'Sign in', signup: 'Create account', email: 'Email address', password: 'Password', confirm: 'Confirm password', language: 'Preferred language', submitIn: 'Sign in', submitUp: 'Create account', switchIn: 'Already have an account? Sign in', switchUp: 'New to Kisan Hita? Create an account', passwordHint: 'Use at least 10 characters.', mismatch: 'Passwords do not match.', busy: 'Please wait…' },
  te: { title: 'కిసాన్ హిత', subtitle: 'మీ వ్యవసాయ సహాయకుడు', signin: 'సైన్ ఇన్', signup: 'ఖాతా సృష్టించండి', email: 'ఇమెయిల్ చిరునామా', password: 'పాస్‌వర్డ్', confirm: 'పాస్‌వర్డ్ నిర్ధారించండి', language: 'మీ భాష', submitIn: 'సైన్ ఇన్', submitUp: 'ఖాతా సృష్టించండి', switchIn: 'ఇప్పటికే ఖాతా ఉందా? సైన్ ఇన్ చేయండి', switchUp: 'కిసాన్ హితకు కొత్తా? ఖాతా సృష్టించండి', passwordHint: 'కనీసం 10 అక్షరాలు ఉపయోగించండి.', mismatch: 'పాస్‌వర్డ్‌లు సరిపోలలేదు.', busy: 'దయచేసి వేచి ఉండండి…' },
  hi: { title: 'किसान हित', subtitle: 'आपका खेती साथी', signin: 'साइन इन', signup: 'खाता बनाएं', email: 'ईमेल पता', password: 'पासवर्ड', confirm: 'पासवर्ड की पुष्टि', language: 'पसंदीदा भाषा', submitIn: 'साइन इन', submitUp: 'खाता बनाएं', switchIn: 'पहले से खाता है? साइन इन करें', switchUp: 'किसान हित पर नए हैं? खाता बनाएं', passwordHint: 'कम से कम 10 अक्षर इस्तेमाल करें।', mismatch: 'पासवर्ड मेल नहीं खाते।', busy: 'कृपया प्रतीक्षा करें…' },
  ta: { title: 'கிசான் ஹிதா', subtitle: 'உங்கள் விவசாயத் துணை', signin: 'உள்நுழை', signup: 'கணக்கை உருவாக்கு', email: 'மின்னஞ்சல் முகவரி', password: 'கடவுச்சொல்', confirm: 'கடவுச்சொல்லை உறுதிப்படுத்து', language: 'விருப்ப மொழி', submitIn: 'உள்நுழை', submitUp: 'கணக்கை உருவாக்கு', switchIn: 'ஏற்கனவே கணக்கு உள்ளதா? உள்நுழையுங்கள்', switchUp: 'கிசான் ஹிதாவுக்குப் புதியவரா? கணக்கை உருவாக்குங்கள்', passwordHint: 'குறைந்தது 10 எழுத்துகளைப் பயன்படுத்துங்கள்.', mismatch: 'கடவுச்சொற்கள் பொருந்தவில்லை.', busy: 'காத்திருக்கவும்…' },
  kn: { title: 'ಕಿಸಾನ್ ಹಿತ', subtitle: 'ನಿಮ್ಮ ಕೃಷಿ ಸಂಗಾತಿ', signin: 'ಸೈನ್ ಇನ್', signup: 'ಖಾತೆ ರಚಿಸಿ', email: 'ಇಮೇಲ್ ವಿಳಾಸ', password: 'ಪಾಸ್‌ವರ್ಡ್', confirm: 'ಪಾಸ್‌ವರ್ಡ್ ದೃಢೀಕರಿಸಿ', language: 'ಆದ್ಯತೆಯ ಭಾಷೆ', submitIn: 'ಸೈನ್ ಇನ್', submitUp: 'ಖಾತೆ ರಚಿಸಿ', switchIn: 'ಈಗಾಗಲೇ ಖಾತೆ ಇದೆಯೇ? ಸೈನ್ ಇನ್ ಮಾಡಿ', switchUp: 'ಕಿಸಾನ್ ಹಿತಕ್ಕೆ ಹೊಸಬರೇ? ಖಾತೆ ರಚಿಸಿ', passwordHint: 'ಕನಿಷ್ಠ 10 ಅಕ್ಷರಗಳನ್ನು ಬಳಸಿ.', mismatch: 'ಪಾಸ್‌ವರ್ಡ್‌ಗಳು ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ.', busy: 'ದಯವಿಟ್ಟು ಕಾಯಿರಿ…' },
  ml: { title: 'കിസാൻ ഹിത', subtitle: 'നിങ്ങളുടെ കൃഷി സഹായി', signin: 'സൈൻ ഇൻ', signup: 'അക്കൗണ്ട് സൃഷ്ടിക്കുക', email: 'ഇമെയിൽ വിലാസം', password: 'പാസ്‌വേഡ്', confirm: 'പാസ്‌വേഡ് സ്ഥിരീകരിക്കുക', language: 'ഇഷ്ടമുള്ള ഭാഷ', submitIn: 'സൈൻ ഇൻ', submitUp: 'അക്കൗണ്ട് സൃഷ്ടിക്കുക', switchIn: 'അക്കൗണ്ട് ഉണ്ടോ? സൈൻ ഇൻ ചെയ്യുക', switchUp: 'കിസാൻ ഹിതയിൽ പുതുതാണോ? അക്കൗണ്ട് സൃഷ്ടിക്കുക', passwordHint: 'കുറഞ്ഞത് 10 അക്ഷരങ്ങൾ ഉപയോഗിക്കുക.', mismatch: 'പാസ്‌വേഡുകൾ പൊരുത്തപ്പെടുന്നില്ല.', busy: 'ദയവായി കാത്തിരിക്കുക…' },
  mr: { title: 'किसान हित', subtitle: 'तुमचा शेती साथीदार', signin: 'साइन इन', signup: 'खाते तयार करा', email: 'ईमेल पत्ता', password: 'पासवर्ड', confirm: 'पासवर्डची पुष्टी करा', language: 'पसंतीची भाषा', submitIn: 'साइन इन', submitUp: 'खाते तयार करा', switchIn: 'आधीच खाते आहे? साइन इन करा', switchUp: 'किसान हितावर नवीन आहात? खाते तयार करा', passwordHint: 'किमान 10 अक्षरे वापरा.', mismatch: 'पासवर्ड जुळत नाहीत.', busy: 'कृपया थांबा…' },
};

const CONTINUE_GUEST: Record<SupportedLanguage, string> = {
  en: 'Continue without an account', te: 'ఖాతా లేకుండా కొనసాగండి', hi: 'बिना खाते के आगे बढ़ें',
  ta: 'கணக்கு இல்லாமல் தொடரவும்', kn: 'ಖಾತೆ ಇಲ್ಲದೆ ಮುಂದುವರಿಯಿರಿ',
  ml: 'അക്കൗണ്ട് ഇല്ലാതെ തുടരുക', mr: 'खात्याशिवाय पुढे जा',
};
const GUEST_ACCESS_ERROR: Record<SupportedLanguage, string> = {
  en: 'Guest access could not be started. Please try again.', te: 'అతిథి ప్రవేశాన్ని ప్రారంభించలేకపోయాము. మళ్లీ ప్రయత్నించండి.',
  hi: 'अतिथि प्रवेश शुरू नहीं हो सका। कृपया फिर से कोशिश करें।', ta: 'விருந்தினர் அணுகலைத் தொடங்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.',
  kn: 'ಅತಿಥಿ ಪ್ರವೇಶ ಆರಂಭಿಸಲಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.', ml: 'അതിഥി പ്രവേശനം ആരംഭിക്കാനായില്ല. വീണ്ടും ശ്രമിക്കുക.',
  mr: 'अतिथी प्रवेश सुरू करता आला नाही. कृपया पुन्हा प्रयत्न करा.',
};

export const AuthPage: React.FC<{ onContinueGuest?: () => Promise<void> }> = ({ onContinueGuest }) => {
  const { signIn, signUp, error, clearError } = useAuth();
  const { language, setLanguage, languages, t } = useLanguage();
  const text = COPY[language];
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [localErrorKey, setLocalErrorKey] = useState('');
  const [guestError, setGuestError] = useState(false);
  const [guestBusy, setGuestBusy] = useState(false);

  const continueGuest = async () => {
    if (!onContinueGuest) return;
    setGuestError(false); setGuestBusy(true);
    try { await onContinueGuest(); } catch { setGuestError(true); }
    finally { setGuestBusy(false); }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLocalErrorKey(''); clearError(); setBusy(true);
    try {
      if (!email.trim()) { setLocalErrorKey('authEmailRequired'); return; }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) { setLocalErrorKey('authEmailInvalid'); return; }
      if (!password) { setLocalErrorKey('authPasswordRequired'); return; }
      if (mode === 'signup') {
        if (password.length < 10 || password.length > 128) { setLocalErrorKey('authPasswordLength'); return; }
        if (password !== confirm) { setLocalErrorKey('authPasswordMismatch'); return; }
        await signUp({ email: email.trim(), password, language });
      } else await signIn(email.trim(), password);
    } catch { /* AuthContext presents the server's non-sensitive error. */ }
    finally { setBusy(false); }
  };

  const inputStyle: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '0.8rem 0.9rem', borderRadius: '0.7rem', border: '1px solid var(--border-subtle)', background: 'rgba(10, 11, 7, 0.6)', color: 'var(--cream)', fontSize: '1rem' };
  const labelStyle: React.CSSProperties = { display: 'block', color: 'var(--cream)', fontSize: '0.86rem', fontWeight: 650, marginBottom: '0.4rem' };

  return <main className="auth-shell" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: '1.2rem', background: 'transparent' }}>
    <form className="auth-card" noValidate onSubmit={submit} style={{ width: 'min(100%, 440px)', padding: 'clamp(1.3rem, 5vw, 2.2rem)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-lg)', background: 'var(--char-card)', boxShadow: '0 20px 55px rgba(0,0,0,.35)' }}>
      <h1 style={{ color: 'var(--amber)', margin: '0 0 .25rem', fontSize: '1.8rem' }}>{text.title}</h1>
      <p style={{ color: 'var(--text-muted)', margin: '0 0 1.4rem' }}>{text.subtitle}</p>
      <div style={{ display: 'grid', gap: '1rem' }}>
        <label><span style={labelStyle}>{text.language}</span><select style={inputStyle} value={language} onChange={(e) => setLanguage(e.target.value as SupportedLanguage)}>{languages.map((item) => <option key={item.code} value={item.code}>{item.nativeName} — {item.name}</option>)}</select></label>
        <label><span style={labelStyle}>{text.email}</span><input style={inputStyle} type="email" autoComplete="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label><span style={labelStyle}>{text.password}</span><input style={inputStyle} type="password" autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} required minLength={mode === 'signup' ? 10 : 1} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {mode === 'signup' && <>
          <div style={{ color: 'var(--text-muted)', fontSize: '.76rem', marginTop: '-.7rem' }}>{text.passwordHint}</div>
          <label><span style={labelStyle}>{text.confirm}</span><input style={inputStyle} type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
        </>}
      </div>
      {(localErrorKey || error) && <p role="alert" style={{ color: '#f87171', fontSize: '.86rem', margin: '1rem 0 0' }}>{localErrorKey ? t(localErrorKey) : t(authErrorTranslationKey(error))}</p>}
      {guestError && <p role="alert" style={{ color: '#f87171', fontSize: '.86rem', margin: '.75rem 0 0' }}>{GUEST_ACCESS_ERROR[language]}</p>}
      <button disabled={busy} type="submit" style={{ width: '100%', marginTop: '1.25rem', padding: '.85rem', border: 0, borderRadius: 'var(--radius-full)', background: 'var(--amber)', color: 'var(--char)', fontWeight: 800, fontSize: '1rem', cursor: busy ? 'wait' : 'pointer' }}>{busy ? text.busy : mode === 'login' ? text.submitIn : text.submitUp}</button>
      <button type="button" onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setLocalErrorKey(''); clearError(); }} style={{ width: '100%', marginTop: '.9rem', padding: '.65rem', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-full)', background: 'transparent', color: 'var(--cream)', cursor: 'pointer' }}>{mode === 'login' ? text.switchUp : text.switchIn}</button>
      {mode === 'login' && onContinueGuest && <button type="button" disabled={guestBusy} onClick={() => void continueGuest()} className="guest-continue-button">{guestBusy ? text.busy : CONTINUE_GUEST[language]}</button>}
    </form>
  </main>;
};

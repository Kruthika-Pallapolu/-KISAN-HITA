import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import type { SupportedLanguage } from '../i18n/translations';
import { CloudSun, Sprout, ShieldAlert, TrendingUp, LogIn } from 'lucide-react';

const GUEST_COPY: Record<SupportedLanguage, { eyebrow: string; title: string; intro: string; limit: string; requires: string; signIn: string; languageLabel: string }> = {
  en: { eyebrow: 'A first look', title: 'Welcome to Kisan Hita', intro: 'Explore the farming tools available in Kisan Hita before creating an account.', limit: 'These tools need a signed-in account to securely save your farm profile and request results. This preview does not send data or create a guest session.', requires: 'Sign in required', signIn: 'Sign in or create an account', languageLabel: 'Language' },
  te: { eyebrow: 'ఒక పరిచయం', title: 'కిసాన్ హితకు స్వాగతం', intro: 'ఖాతా సృష్టించే ముందు కిసాన్ హితలోని వ్యవసాయ సాధనాలను చూడండి.', limit: 'మీ వ్యవసాయ వివరాలను భద్రంగా ఉంచి ఫలితాలు పొందడానికి ఈ సాధనాలకు సైన్ ఇన్ చేసిన ఖాతా అవసరం. ఈ ప్రివ్యూ ఎలాంటి వివరాలు పంపదు, అతిథి సెషన్‌ను సృష్టించదు.', requires: 'సైన్ ఇన్ అవసరం', signIn: 'సైన్ ఇన్ చేయండి లేదా ఖాతా సృష్టించండి', languageLabel: 'భాష' },
  hi: { eyebrow: 'एक परिचय', title: 'किसान हित में आपका स्वागत है', intro: 'खाता बनाने से पहले किसान हित के खेती के साधनों को देखें।', limit: 'खेती की जानकारी सुरक्षित रखने और नतीजे पाने के लिए इन साधनों में साइन इन करना ज़रूरी है। यह झलक कोई जानकारी नहीं भेजती और अतिथि सत्र नहीं बनाती।', requires: 'साइन इन ज़रूरी है', signIn: 'साइन इन करें या खाता बनाएं', languageLabel: 'भाषा' },
  ta: { eyebrow: 'ஒரு அறிமுகம்', title: 'கிசான் ஹிதாவுக்கு வரவேற்கிறோம்', intro: 'கணக்கை உருவாக்கும் முன் கிசான் ஹிதாவின் விவசாயக் கருவிகளைப் பாருங்கள்.', limit: 'உங்கள் பண்ணை விவரங்களைப் பாதுகாப்பாகச் சேமித்து முடிவுகளைப் பெற இந்தக் கருவிகளுக்கு உள்நுழைந்த கணக்கு தேவை. இந்த முன்னோட்டம் எந்தத் தரவையும் அனுப்பாது; விருந்தினர் அமர்வையும் உருவாக்காது.', requires: 'உள்நுழைவு தேவை', signIn: 'உள்நுழையுங்கள் அல்லது கணக்கை உருவாக்குங்கள்', languageLabel: 'மொழி' },
  kn: { eyebrow: 'ಒಂದು ಪರಿಚಯ', title: 'ಕಿಸಾನ್ ಹಿತಕ್ಕೆ ಸ್ವಾಗತ', intro: 'ಖಾತೆ ತೆರೆಯುವ ಮೊದಲು ಕಿಸಾನ್ ಹಿತದ ಕೃಷಿ ಸಾಧನಗಳನ್ನು ನೋಡಿ.', limit: 'ನಿಮ್ಮ ಕೃಷಿ ವಿವರಗಳನ್ನು ಸುರಕ್ಷಿತವಾಗಿ ಉಳಿಸಿ ಫಲಿತಾಂಶ ಪಡೆಯಲು ಈ ಸಾಧನಗಳಿಗೆ ಸೈನ್ ಇನ್ ಮಾಡಿದ ಖಾತೆ ಬೇಕು. ಈ ಪೂರ್ವವೀಕ್ಷಣೆ ಯಾವುದೇ ಮಾಹಿತಿಯನ್ನು ಕಳುಹಿಸುವುದಿಲ್ಲ ಅಥವಾ ಅತಿಥಿ ಸೆಷನ್ ಸೃಷ್ಟಿಸುವುದಿಲ್ಲ.', requires: 'ಸೈನ್ ಇನ್ ಅಗತ್ಯ', signIn: 'ಸೈನ್ ಇನ್ ಮಾಡಿ ಅಥವಾ ಖಾತೆ ರಚಿಸಿ', languageLabel: 'ಭಾಷೆ' },
  ml: { eyebrow: 'ഒരു പരിചയം', title: 'കിസാൻ ഹിതയിലേക്ക് സ്വാഗതം', intro: 'അക്കൗണ്ട് സൃഷ്ടിക്കുന്നതിന് മുമ്പ് കിസാൻ ഹിതയിലെ കൃഷി ഉപകരണങ്ങൾ കാണുക.', limit: 'കൃഷിവിവരങ്ങൾ സുരക്ഷിതമായി സൂക്ഷിച്ച് ഫലങ്ങൾ ലഭിക്കാൻ ഈ ഉപകരണങ്ങൾക്ക് സൈൻ ഇൻ ചെയ്ത അക്കൗണ്ട് വേണം. ഈ പ്രിവ്യൂ വിവരങ്ങൾ അയയ്ക്കുകയോ അതിഥി സെഷൻ സൃഷ്ടിക്കുകയോ ചെയ്യില്ല.', requires: 'സൈൻ ഇൻ വേണം', signIn: 'സൈൻ ഇൻ ചെയ്യുക അല്ലെങ്കിൽ അക്കൗണ്ട് സൃഷ്ടിക്കുക', languageLabel: 'ഭാഷ' },
  mr: { eyebrow: 'एक ओळख', title: 'किसान हितमध्ये स्वागत आहे', intro: 'खाते तयार करण्यापूर्वी किसान हितमधील शेतीची साधने पाहा.', limit: 'शेतीची माहिती सुरक्षित ठेवून निकाल मिळवण्यासाठी या साधनांसाठी साइन इन केलेले खाते आवश्यक आहे. या पूर्वदृश्यातून माहिती पाठवली जात नाही किंवा अतिथी सत्र तयार होत नाही.', requires: 'साइन इन आवश्यक', signIn: 'साइन इन करा किंवा खाते तयार करा', languageLabel: 'भाषा' },
};

export const GuestLandingPage: React.FC<{ onSignIn: () => void }> = ({ onSignIn }) => {
  const { language, setLanguageLocally, languages, t } = useLanguage();
  const copy = GUEST_COPY[language];
  const tools = [
    { icon: CloudSun, title: t('weatherTitle'), description: t('weatherSub') },
    { icon: Sprout, title: t('cropAdvisorTitle'), description: t('cropAdvisorSub') },
    { icon: ShieldAlert, title: t('cropHealthTitle'), description: t('cropHealthSub') },
    { icon: TrendingUp, title: t('marketTitle'), description: t('marketSub') },
  ];

  return <main className="guest-landing auth-shell">
    <div className="guest-landing-inner">
      <div className="guest-topline">
        <span className="guest-brand">{t('appName')}</span>
        <label className="guest-language-label">
          <span className="sr-only">{copy.languageLabel}</span>
          <select aria-label={copy.languageLabel} value={language} onChange={(event) => setLanguageLocally(event.target.value as SupportedLanguage)}>
            {languages.map((item) => <option key={item.code} value={item.code}>{item.nativeName}</option>)}
          </select>
        </label>
      </div>
      <section className="guest-intro">
        <span className="mono guest-eyebrow">{copy.eyebrow}</span>
        <h1>{copy.title}</h1>
        <p>{copy.intro}</p>
        <div className="guest-account-note" role="note">{copy.limit}</div>
      </section>
      <section aria-label={copy.title} className="guest-tool-grid">
        {tools.map(({ icon: Icon, title, description }) => <article className="guest-tool-card" key={title}>
          <Icon aria-hidden="true" size={24} />
          <h2>{title}</h2>
          <p>{description}</p>
          <span className="badge">{copy.requires}</span>
        </article>)}
      </section>
      <button type="button" onClick={onSignIn} className="btn btn-primary guest-signin-button"><LogIn size={18} />{copy.signIn}</button>
    </div>
  </main>;
};

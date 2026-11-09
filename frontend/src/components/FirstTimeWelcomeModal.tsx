import React, { useState, useEffect } from 'react';
import { useLanguage } from '../context/LanguageContext';
import { useAssistant } from '../context/AssistantContext';
import { Bot, Mic, Volume2, Square, ArrowRight, Sparkles, CheckCircle2, ShieldCheck, X } from 'lucide-react';

interface WelcomeContent {
  title: string;
  subtitle: string;
  body: string;
  voiceNote: string;
  startBtn: string;
  exploreBtn: string;
  features: string[];
}

const WELCOME_CONTENT: Record<string, WelcomeContent> = {
  te: {
    title: 'నమస్కారం రైతు సోదరా! 🙏',
    subtitle: 'కిసాన్ హితకు స్వాగతం — మీ నమ్మకమైన డిజిటల్ వ్యవసాయ తోడు.',
    body: 'మీ ప్రాంత వాతావరణం, డెమో/సూచన పంట ఎంపికలు, పంట ఆరోగ్య జాగ్రత్తలు, మరియు DEMOగా గుర్తించిన మార్కెట్ ధరల గురించి అడగండి.',
    voiceNote: 'టైప్ చేయడం ఎప్పుడూ అందుబాటులో ఉంటుంది. మీ బ్రౌజర్ మద్దతిస్తే మైక్రోఫోన్‌తో మాట్లాడండి; భాషల మద్దతు పరికరాన్ని బట్టి మారుతుంది.',
    startBtn: 'మాట్లాడటం ప్రారంభించండి',
    exploreBtn: 'సేవలను చూడండి',
    features: [
      'వ్యవసాయ వాతావరణ సూచన & పిచికారీ సలహా',
      'డెమో/సూచన పంట ఎంపికలు — విత్తే ముందు స్థానికంగా నిర్ధారించండి',
      'బాధ్యతాయుతమైన పంట ఆరోగ్య సంరక్షణ (రసాయనాల మితిమీరిన వాడకం నివారణ)',
      'DEMO మార్కెట్ ధరలు — లైవ్ లేదా అధికారిక ధరలు కావు',
    ],
  },
  en: {
    title: 'Namaste! Welcome to Kisan Hita 🙏',
    subtitle: 'Your voice-first digital agricultural companion.',
    body: 'Ask about demo/reference crop options, plant-health precautions, and market price samples clearly marked DEMO.',
    voiceNote: 'Typing is always available. Use the microphone when your browser supports speech recognition; language support varies by device.',
    startBtn: 'Start Voice Conversation',
    exploreBtn: 'Explore Agricultural Services',
    features: [
      'Demo/reference crop options — verify locally before planting',
      'Safety-first plant health & cultural practices',
      'DEMO market prices — not live or official mandi rates',
    ],
  },
  hi: {
    title: 'नमस्ते किसान भाई! 🙏',
    subtitle: 'किसान हिता में आपका स्वागत है — आपका अपना डिजिटल कृषि साथी।',
    body: 'स्थानीय मौसम, डेमो/संदर्भ फसल विकल्प, सुरक्षित फसल स्वास्थ्य और DEMO के रूप में चिह्नित नमूना मंडी भाव पूछें।',
    voiceNote: 'टाइप करना हमेशा उपलब्ध है। ब्राउज़र समर्थन करे तो माइक्रोफ़ोन से बोलें; भाषा का समर्थन डिवाइस पर निर्भर करता है।',
    startBtn: 'बातचीत शुरू करें',
    exploreBtn: 'कृषि सेवाएं देखें',
    features: [
      'कृषि मौसम पूर्वानुमान एवं छिड़काव सलाह',
      'डेमो/संदर्भ फसल विकल्प — बुवाई से पहले स्थानीय पुष्टि करें',
      'सुरक्षित फसल स्वास्थ्य एवं कीट प्रबंधन',
      'DEMO मंडी भाव — लाइव या आधिकारिक दरें नहीं',
    ],
  },
  ta: {
    title: 'வணக்கம் உழவர் தோழரே! 🙏',
    subtitle: 'கிசான் ஹிதாவுக்கு நல்வரவு — உங்கள் டிஜிட்டல் விவசாய தோழன்.',
    body: 'உள்ளூர் வானிலை, DEMO/குறிப்பு பயிர் விருப்பங்கள், பயிர் பாதுகாப்பு மற்றும் DEMO எனக் குறிக்கப்பட்ட சந்தை மாதிரி விலைகளைப் பற்றிக் கேளுங்கள்.',
    voiceNote: 'தட்டச்சு எப்போதும் கிடைக்கும். உங்கள் உலாவி ஆதரித்தால் மைக்ரோஃபோனில் பேசலாம்; மொழி ஆதரவு சாதனத்தைப் பொறுத்து மாறும்.',
    startBtn: 'பேசத் தொடங்குங்கள்',
    exploreBtn: 'சேவைகளைப் பார்க்க',
    features: [
      'விவசாய வானிலை மற்றும் தெளிப்பான் ஆலோசனை',
      'DEMO/குறிப்பு பயிர் விருப்பங்கள் — நடுவதற்கு முன் உள்ளூரில் உறுதிப்படுத்தவும்',
      'பொறுப்பான பயிர் ஆரோக்கிய பாதுகாப்பு',
      'DEMO சந்தை விலைகள் — நேரடி அல்லது அதிகாரப்பூர்வ விலைகள் அல்ல',
    ],
  },
  kn: {
    title: 'ನಮಸ್ಕಾರ ರೈತ ಬಾಂಧವರೇ! 🙏',
    subtitle: 'ಕಿಸಾನ್ ಹಿತಾಗೆ ಸ್ವಾಗತ — ನಿಮ್ಮ ನಂಬಿಕಸ್ಥ ಡಿಜಿಟಲ್ ಕೃಷಿ ಸಂಗಾತಿ.',
    body: 'ಸ್ಥಳೀಯ ಹವಾಮಾನ, DEMO/ಉಲ್ಲೇಖ ಬೆಳೆ ಆಯ್ಕೆಗಳು, ಬೆಳೆ ಆರೋಗ್ಯ ಜಾಗ್ರತೆ ಮತ್ತು DEMO ಎಂದು ಗುರುತಿಸಿದ ಮಾರುಕಟ್ಟೆ ಮಾದರಿ ಬೆಲೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ.',
    voiceNote: 'ಟೈಪ್ ಮಾಡುವ ಆಯ್ಕೆ ಯಾವಾಗಲೂ ಇದೆ. ನಿಮ್ಮ ಬ್ರೌಸರ್ ಬೆಂಬಲಿಸಿದರೆ ಮೈಕ್ ಬಳಸಿ ಮಾತನಾಡಿ; ಭಾಷೆಯ ಬೆಂಬಲ ಸಾಧನಕ್ಕೆ ಅನುಗುಣವಾಗಿ ಬದಲಾಗುತ್ತದೆ.',
    startBtn: 'ಮಾತನಾಡಲು ಪ್ರಾರಂಭಿಸಿ',
    exploreBtn: 'ಕೃಷಿ ಸೇವೆಗಳನ್ನು ವೀಕ್ಷಿಸಿ',
    features: [
      'ಕೃಷಿ ಹವಾಮಾನ ಮುನ್ಸೂಚನೆ ಮತ್ತು ಸಿಂಪಡಣೆ ಸಲಹೆ',
      'DEMO/ಉಲ್ಲೇಖ ಬೆಳೆ ಆಯ್ಕೆಗಳು — ಬಿತ್ತುವ ಮೊದಲು ಸ್ಥಳೀಯವಾಗಿ ದೃಢಪಡಿಸಿ',
      'ಸುರಕ್ಷಿತ ಬೆಳೆ ಆರೋಗ್ಯ ನಿರ್ವಹಣೆ',
      'DEMO ಮಾರುಕಟ್ಟೆ ಬೆಲೆಗಳು — ಲೈವ್ ಅಥವಾ ಅಧಿಕೃತ ದರಗಳಲ್ಲ',
    ],
  },
  ml: {
    title: 'നമസ്കാരം കർഷക സുഹൃത്തേ! 🙏',
    subtitle: 'കിസാൻ ഹിതയിലേക്ക് സ്വാഗതം — നിങ്ങളുടെ വിശ്വസ്ത കാർഷിക സഹായി.',
    body: 'പ്രാദേശിക കാലാവസ്ഥ, DEMO/സൂചനാ വിളകൾ, വിള ആരോഗ്യ ജാഗ്രതകൾ, DEMO എന്ന് അടയാളപ്പെടുത്തിയ വിപണി മാതൃകാ വിലകൾ എന്നിവ ചോദിക്കാം.',
    voiceNote: 'ടൈപ്പ് ചെയ്യാനുള്ള സൗകര്യം എപ്പോഴും ഉണ്ട്. ബ്രൗസർ പിന്തുണയ്ക്കുമ്പോൾ മൈക്രോഫോണിൽ സംസാരിക്കാം; ഭാഷാ പിന്തുണ ഉപകരണത്തെ ആശ്രയിച്ചിരിക്കും.',
    startBtn: 'സംഭാഷണം ആരംഭിക്കുക',
    exploreBtn: 'സേവനങ്ങൾ കാണുക',
    features: [
      'കാലാവസ്ഥാ പ്രവചനവും തളിക്കൽ നിർദ്ദേശങ്ങളും',
      'DEMO/സൂചനാ വിളകൾ — കൃഷിക്ക് മുമ്പ് പ്രാദേശികമായി ഉറപ്പാക്കുക',
      'സുരക്ഷിതമായ വിള ആരോഗ്യ സംരക്ഷണം',
      'DEMO വിപണി വിലകൾ — തത്സമയമോ ഔദ്യോഗികമോ അല്ല',
    ],
  },
  mr: {
    title: 'नमस्कार शेतकरी मित्रांनो! 🙏',
    subtitle: 'किसान हिता मध्ये आपले स्वागत आहे — आपला डिजिटल शेती मित्र.',
    body: 'स्थानिक हवामान, DEMO/संदर्भ पीक पर्याय, पीक आरोग्याची काळजी आणि DEMO म्हणून दाखवलेले नमुना बाजारभाव विचारा.',
    voiceNote: 'टाइप करण्याचा पर्याय नेहमी उपलब्ध आहे. ब्राउझर समर्थन देत असल्यास मायक्रोफोन वापरा; भाषेचे समर्थन उपकरणानुसार बदलते.',
    startBtn: 'बोलणे सुरू करा',
    exploreBtn: 'कृषी सेवा पहा',
    features: [
      'हवामान अंदाज व फवारणी सल्ला',
      'DEMO/संदर्भ पीक पर्याय — पेरणीपूर्वी स्थानिक खात्री करा',
      'सुरक्षित पीक आरोग्य मार्गदर्शन',
      'DEMO बाजारभाव — थेट किंवा अधिकृत दर नाहीत',
    ],
  },
};

export const FirstTimeWelcomeModal: React.FC = () => {
  const { language, showLanguageModal, t } = useLanguage();
  const { openAssistant } = useAssistant();

  const [isOpen, setIsOpen] = useState<boolean>(false);

  useEffect(() => {
    // Show welcome modal if language modal is closed and intro has not been seen yet
    const introSeen = localStorage.getItem('kisan_hita_intro_seen');
    if (!introSeen && !showLanguageModal) {
      setIsOpen(true);
    }
  }, [showLanguageModal]);

  if (!isOpen) return null;

  const content = WELCOME_CONTENT[language] || WELCOME_CONTENT['en'];

  const handleDismiss = () => {
    localStorage.setItem('kisan_hita_intro_seen', 'true');
    setIsOpen(false);
  };

  const handleStartAssistant = () => {
    handleDismiss();
    openAssistant();
  };

  return (
    <div className="cinematic-modal-overlay" style={{
      position: 'fixed',
      inset: 0,
      zIndex: 95,
      background: 'rgba(10, 11, 7, 0.82)',
      backdropFilter: 'blur(10px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1.2rem',
    }}>
      <div className="cinematic-modal-surface" style={{
        background: 'var(--char-card)',
        border: '1.5px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        maxWidth: '620px',
        width: '100%',
        padding: '2.2rem 2rem',
        boxShadow: '0 25px 65px rgba(0, 0, 0, 0.7)',
        position: 'relative',
        animation: 'fadeIn 0.25s ease-out',
      }}>
        {/* Close Button */}
        <button
          onClick={handleDismiss}
          style={{
            position: 'absolute',
            top: '1.2rem',
            right: '1.2rem',
            background: 'none',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
          }}
          title={t('dismiss')}
        >
          <X size={20} />
        </button>

        {/* Header Icon & Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', marginBottom: '0.8rem' }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #2f3a1c, #8a6a45)',
            border: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--amber)',
            flexShrink: 0,
          }}>
            <Bot size={24} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.45rem', fontWeight: 800, color: 'var(--cream)', lineHeight: 1.2 }}>
              {content.title}
            </h2>
            <div style={{ fontSize: '0.86rem', color: 'var(--amber)', fontWeight: 600 }}>
              {content.subtitle}
            </div>
          </div>
        </div>

        {/* Conversational Explanation */}
        <p style={{
          color: 'var(--text-muted)',
          fontSize: '0.94rem',
          lineHeight: 1.6,
          marginTop: '1rem',
          marginBottom: '1.2rem',
        }}>
          {content.body}
        </p>

        {/* Feature Highlights Grid */}
        <div style={{
          background: 'rgba(28, 30, 20, 0.65)',
          border: '1px solid var(--border-card)',
          borderRadius: 'var(--radius-md)',
          padding: '1rem',
          marginBottom: '1.4rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.55rem',
        }}>
          {content.features.map((feat, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.55rem', fontSize: '0.85rem', color: 'var(--cream)' }}>
              <CheckCircle2 size={16} style={{ color: 'var(--amber)', flexShrink: 0, marginTop: '2px' }} />
              <span>{feat}</span>
            </div>
          ))}
        </div>

        {/* Information Callout */}
        <div style={{
          background: 'rgba(240, 168, 58, 0.1)',
          border: '1px solid rgba(240, 168, 58, 0.25)',
          borderRadius: 'var(--radius-md)',
          padding: '0.85rem 1rem',
          marginBottom: '1.6rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.6rem',
        }}>
          <Sparkles size={18} style={{ color: 'var(--amber)', flexShrink: 0 }} />
          <span style={{ fontSize: '0.84rem', color: 'var(--cream)', fontWeight: 600 }}>
            {content.voiceNote}
          </span>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.85rem', justifyContent: 'flex-end' }}>
          <button
            onClick={handleDismiss}
            className="btn btn-secondary"
            style={{ padding: '0.75rem 1.4rem', fontSize: '0.9rem' }}
          >
            {content.exploreBtn}
          </button>
          <button
            onClick={handleStartAssistant}
            className="btn btn-primary"
            style={{ padding: '0.75rem 1.6rem', fontSize: '0.9rem' }}
          >
            <Bot size={16} />
            <span>{content.startBtn}</span>
          </button>
        </div>
      </div>
    </div>
  );
};


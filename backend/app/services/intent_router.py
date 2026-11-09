import re
import logging
import unicodedata
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
from ..models.schemas import ChatResponse
from ..database import (
    get_conversation_session,
    save_conversation_session,
    clear_conversation_session,
)
from .crop_service import CropAdvisorService
from .crop_health_service import CropHealthService
from .market_service import MarketPriceService
from .market_provider import MarketProviderError
from .gemini_service import GeminiAIService
from .crop_health_localization import format_assistant_crop_health_reply

logger = logging.getLogger(__name__)


_LANGUAGE_SCRIPTS = {
    "te": "TELUGU",
    "en": "LATIN",
    "hi": "DEVANAGARI",
    "mr": "DEVANAGARI",
    "ta": "TAMIL",
    "kn": "KANNADA",
    "ml": "MALAYALAM",
}


def response_matches_language_script(text: Optional[str], language: str) -> bool:
    """Reject model/fallback text that is predominantly in the wrong script."""
    code = (language or "en")[:2].lower()
    expected = _LANGUAGE_SCRIPTS.get(code)
    letters = [char for char in (text or "") if char.isalpha()]
    if not expected or not letters:
        return False
    matching = sum(expected in unicodedata.name(char, "") for char in letters)
    return matching / len(letters) >= 0.35


def _localized_unavailable_reply(language: str) -> str:
    replies = {
        "te": "క్షమించండి, ఈ ప్రశ్నకు నమ్మదగిన సమాధానం ఇప్పుడే ఇవ్వలేకపోయాను. కొద్దిసేపటికి మళ్లీ ప్రయత్నించండి లేదా వాతావరణం, పంట ఎంపిక, పంట ఆరోగ్యం, మార్కెట్ ధరల గురించి అడగండి.",
        "hi": "क्षमा करें, अभी इस सवाल का भरोसेमंद जवाब नहीं दे पाया। थोड़ी देर बाद फिर कोशिश करें या मौसम, फसल विकल्प, फसल स्वास्थ्य और मंडी भाव के बारे में पूछें।",
        "ta": "மன்னிக்கவும், இந்தக் கேள்விக்கு இப்போது நம்பகமான பதிலை வழங்க முடியவில்லை. சிறிது நேரம் கழித்து மீண்டும் முயற்சிக்கவும் அல்லது வானிலை, பயிர் தேர்வு, பயிர் நலம், சந்தை விலை பற்றி கேளுங்கள்.",
        "kn": "ಕ್ಷಮಿಸಿ, ಈ ಪ್ರಶ್ನೆಗೆ ಈಗ ವಿಶ್ವಾಸಾರ್ಹ ಉತ್ತರ ನೀಡಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ಸ್ವಲ್ಪ ಸಮಯದ ನಂತರ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ ಅಥವಾ ಹವಾಮಾನ, ಬೆಳೆ ಆಯ್ಕೆ, ಬೆಳೆ ಆರೋಗ್ಯ, ಮಾರುಕಟ್ಟೆ ದರಗಳ ಬಗ್ಗೆ ಕೇಳಿ.",
        "ml": "ക്ഷമിക്കണം, ഈ ചോദ്യത്തിന് ഇപ്പോൾ വിശ്വസനീയമായ മറുപടി നൽകാനായില്ല. കുറച്ച് കഴിഞ്ഞ് വീണ്ടും ശ്രമിക്കൂ, അല്ലെങ്കിൽ കാലാവസ്ഥ, വിള തിരഞ്ഞെടുപ്പ്, വിള ആരോഗ്യം, വിപണി വില എന്നിവ ചോദിക്കൂ.",
        "mr": "क्षमस्व, या प्रश्नाचे विश्वासार्ह उत्तर आत्ता देता आले नाही. थोड्या वेळाने पुन्हा प्रयत्न करा किंवा हवामान, पीक निवड, पीक आरोग्य आणि बाजारभाव विचारा.",
        "en": "I couldn't generate a reliable answer to that question just now. Please try again shortly, or ask about crop options, crop health, or market prices.",
    }
    return replies.get((language or "en")[:2].lower(), replies["en"])


def _market_record_reply(record: Any, language: str) -> str:
    """Describe only a returned district-level illustrative reference."""
    lang = (language or "en")[:2].lower()
    localized_key = "Chilli" if record.commodity == "Chilli (dry)" else record.commodity
    commodity = COMMODITY_LOCALIZED_NAMES.get(localized_key, {}).get(lang, record.commodity)
    prices = []
    if record.modal_price_per_kg is not None:
        prices.append(f"modal ₹{record.modal_price_per_kg:,.2f}/kg")
    if record.min_price_per_kg is not None:
        prices.append(f"minimum ₹{record.min_price_per_kg:,.2f}/kg")
    if record.max_price_per_kg is not None:
        prices.append(f"maximum ₹{record.max_price_per_kg:,.2f}/kg")
    price_text = ", ".join(prices) or "no price fields were provided"
    templates = {
        "en": f"DEMO DATA for {commodity} in {record.district}, {record.state}: {price_text}. This is a deterministic illustrative district reference in ₹/kg, not a live, verified, official, or mandi-reported price. No mandi or reporting date is provided.",
        "te": f"{record.district}, {record.state}లో {commodity}కు ప్రదర్శన డేటా: {price_text}. ఇవి ₹/కిలోలో స్థిరమైన నమూనా జిల్లా సూచన విలువలు మాత్రమే; ప్రత్యక్ష, ధృవీకరించిన, అధికారిక లేదా మండీ నివేదించిన ధరలు కావు. మండీ పేరు లేదా నివేదిక తేదీ ఇవ్వలేదు.",
        "hi": f"{record.district}, {record.state} में {commodity} के लिए DEMO डेटा: {price_text}। ये ₹/किलो में स्थिर उदाहरणात्मक जिला संदर्भ हैं, लाइव, सत्यापित, आधिकारिक या मंडी द्वारा दर्ज भाव नहीं। मंडी का नाम या रिपोर्ट तारीख उपलब्ध नहीं है।",
        "ta": f"{record.district}, {record.state} பகுதியில் {commodity}க்கான DEMO தரவு: {price_text}. இவை ₹/கிலோவில் நிலையான எடுத்துக்காட்டு மாவட்டக் குறிப்புகள் மட்டுமே; நேரடி, சரிபார்க்கப்பட்ட, அதிகாரப்பூர்வ அல்லது சந்தை அறிக்கை விலைகள் அல்ல. சந்தை பெயர் அல்லது அறிக்கை தேதி வழங்கப்படவில்லை.",
        "kn": f"{record.district}, {record.state} ಪ್ರದೇಶದ {commodity}ಗೆ DEMO ಡೇಟಾ: {price_text}. ಇವು ₹/ಕೆ.ಜಿ.ಯಲ್ಲಿನ ಸ್ಥಿರ ಉದಾಹರಣೆಯ ಜಿಲ್ಲಾ ಉಲ್ಲೇಖಗಳು ಮಾತ್ರ; ನೇರ, ಪರಿಶೀಲಿತ, ಅಧಿಕೃತ ಅಥವಾ ಮಾರುಕಟ್ಟೆ ವರದಿ ದರಗಳಲ್ಲ. ಮಾರುಕಟ್ಟೆ ಹೆಸರು ಅಥವಾ ವರದಿ ದಿನಾಂಕ ನೀಡಿಲ್ಲ.",
        "ml": f"{record.district}, {record.state} പ്രദേശത്തെ {commodity}ക്കുള്ള DEMO ഡാറ്റ: {price_text}. ഇവ ₹/കിലോയിലെ സ്ഥിരമായ ഉദാഹരണ ജില്ലാ സൂചനകൾ മാത്രമാണ്; തത്സമയ, പരിശോധിച്ച, ഔദ്യോഗിക, വിപണി റിപ്പോർട്ട് വിലകളല്ല. വിപണിയുടെ പേരോ റിപ്പോർട്ട് തീയതിയോ നൽകിയിട്ടില്ല.",
        "mr": f"{record.district}, {record.state} येथील {commodity}साठी DEMO डेटा: {price_text}. हे ₹/किलोमधील स्थिर उदाहरणार्थ जिल्हा संदर्भ आहेत; थेट, पडताळलेले, अधिकृत किंवा बाजाराने नोंदवलेले भाव नाहीत. बाजाराचे नाव किंवा अहवालाची तारीख दिलेली नाही.",
    }
    return templates.get(lang, templates["en"])


def _cotton_pest_information_fallback(symptoms: str, language: str) -> Optional[str]:
    """Safe general cotton-pest information for when Gemini is unreachable."""
    text = (symptoms or "").casefold()
    pest_question = any(term in text for term in ("insect", "pest", "worm", "white", "పురుగు", "తెల్ల", "कीट", "सफेद", "பூச்சி", "வெள்ளை", "ಕೀಟ", "ಬಿಳಿ", "കീട", "വെള്ളി", "कीड", "पांढरी"))
    if not pest_question:
        return None
    lang = (language or "en")[:2].lower()
    white = any(term in text for term in ("white", "తెల్ల", "सफेद", "வெள்ளை", "ಬಿಳಿ", "വെള്ളി", "पांढरी"))
    answers = {
        "en": ("Whiteflies are one possibility when small white insects are under cotton leaves; aphids, jassids and thrips can also occur. Disturb a leaf to see whether tiny white adults fly up, and check for sticky honeydew. This description alone cannot confirm the pest. For general cotton scouting, also inspect leaf undersides and look for damaged squares or holes in bolls from bollworms. What do you see when you disturb the leaves?" if white else "Common cotton pests include aphids, jassids, whiteflies and thrips, which feed on leaves, as well as bollworms, whose larvae can damage squares and bolls. Check leaf undersides for insects or sticky honeydew, and inspect squares and bolls for holes or caterpillars. These are general possibilities, not a finding about your field. What signs are you seeing?"),
        "te": ("పత్తి ఆకుల కింద చిన్న తెల్ల పురుగులు ఉంటే తెల్లదోమ ఒక అవకాశం; పేనుబంక, పచ్చదోమ లేదా తామర పురుగులూ ఉండవచ్చు. ఆకును కదిలించినప్పుడు చిన్న తెల్ల పురుగులు ఎగురుతాయా, ఆకులపై తేనె వంటి జిగురు ఉందా చూడండి. ఈ వివరణతో పురుగును నిర్ధారించలేం. మీకు ఆకును కదిలించినప్పుడు ఏమి కనిపిస్తోంది?" if white else "పత్తిలో పేనుబంక, పచ్చదోమ, తెల్లదోమ, తామర పురుగులు ఆకులపై కనిపించవచ్చు. కాయతొలిచే పురుగులు పూల మొగ్గలు, కాయలను దెబ్బతీయవచ్చు. ఆకుల అడుగు భాగం, జిగురు, పూల మొగ్గలు మరియు కాయలపై రంధ్రాలు ఉన్నాయా చూడండి. ఇవి సాధారణ సమాచారం మాత్రమే; మీ పొలంలో ఉన్నాయని నిర్ధారణ కాదు. మీరు ఏ లక్షణం చూస్తున్నారు?"),
        "hi": ("कपास की पत्तियों के नीचे छोटे सफेद कीट दिखें तो सफेद मक्खी एक संभावना है; माहू, जैसिड या थ्रिप्स भी हो सकते हैं। पत्ती हिलाकर देखें कि छोटी सफेद मक्खियाँ उड़ती हैं या नहीं, और चिपचिपा मधुरस देखें। केवल इस वर्णन से कीट की पुष्टि नहीं होती। पत्ती हिलाने पर आपको क्या दिखता है?" if white else "कपास में माहू, जैसिड, सफेद मक्खी और थ्रिप्स पत्तियों पर मिल सकते हैं। बॉलवर्म की सुंडी फूल की कलियों और टिंडों को नुकसान पहुँचा सकती है। पत्तियों के नीचे कीट या चिपचिपापन और कलियों/टिंडों में छेद देखें। यह सामान्य जानकारी है, आपके खेत की पुष्टि नहीं। आपको कौन सा लक्षण दिख रहा है?"),
        "ta": ("பருத்தி இலைகளின் கீழே சிறிய வெள்ளை பூச்சிகள் இருந்தால் வெள்ளை ஈ ஒரு சாத்தியம்; அசுவினி, ஜாசிட் அல்லது த்ரிப்ஸும் இருக்கலாம். இலையை அசைக்கும்போது சிறிய வெள்ளை ஈக்கள் பறக்கிறதா, ஒட்டும் தேன் போன்ற சாறு உள்ளதா பாருங்கள். இந்த விளக்கத்தால் மட்டும் பூச்சியை உறுதி செய்ய முடியாது. இலையை அசைத்தால் என்ன தெரிகிறது?" if white else "பருத்தியில் அசுவினி, ஜாசிட், வெள்ளை ஈ, த்ரிப்ஸ் ஆகியவை இலைகளில் இருக்கலாம். காய்ப்புழுக்கள் பூ மொட்டுகளையும் காய்களையும் சேதப்படுத்தலாம். இலை அடிப்பக்கம், ஒட்டும் சாறு, மொட்டுகள் மற்றும் காய்களில் துளைகள் உள்ளதா பாருங்கள். இது பொதுத் தகவல்; உங்கள் வயலில் உள்ளதை உறுதி செய்யவில்லை. என்ன அறிகுறி தெரிகிறது?"),
        "kn": ("ಹತ್ತಿ ಎಲೆಗಳ ಕೆಳಗೆ ಸಣ್ಣ ಬಿಳಿ ಕೀಟಗಳಿದ್ದರೆ ಬಿಳಿನೊಣ ಒಂದು ಸಾಧ್ಯತೆ; ಹೇನು, ಜಾಸಿಡ್ ಅಥವಾ ಥ್ರಿಪ್ಸ್ ಕೂಡ ಇರಬಹುದು. ಎಲೆಯನ್ನು ಅಲುಗಿಸಿದಾಗ ಬಿಳಿ ಕೀಟಗಳು ಹಾರುತ್ತವೆಯೇ ಮತ್ತು ಅಂಟುವ ಸಿಹಿ ದ್ರವವಿದೆಯೇ ನೋಡಿ. ಈ ವಿವರಣೆಯಿಂದ ಮಾತ್ರ ಕೀಟವನ್ನು ಖಚಿತಪಡಿಸಲಾಗದು. ಎಲೆಯನ್ನು ಅಲುಗಿಸಿದಾಗ ಏನು ಕಾಣುತ್ತದೆ?" if white else "ಹತ್ತಿಯಲ್ಲಿ ಹೇನು, ಜಾಸಿಡ್, ಬಿಳಿನೊಣ ಮತ್ತು ಥ್ರಿಪ್ಸ್ ಎಲೆಗಳ ಮೇಲೆ ಕಾಣಬಹುದು. ಬೋಲ್‌ವರ್ಮ್ ಹುಳು ಹೂಮೊಗ್ಗು ಮತ್ತು ಕಾಯಿಗೆ ಹಾನಿ ಮಾಡಬಹುದು. ಎಲೆಯ ಕೆಳಭಾಗ, ಅಂಟುವ ದ್ರವ, ಮೊಗ್ಗು ಮತ್ತು ಕಾಯಿಗಳಲ್ಲಿನ ರಂಧ್ರಗಳನ್ನು ಪರಿಶೀಲಿಸಿ. ಇದು ಸಾಮಾನ್ಯ ಮಾಹಿತಿ ಮಾತ್ರ; ನಿಮ್ಮ ಹೊಲದ ದೃಢೀಕರಣವಲ್ಲ. ಯಾವ ಲಕ್ಷಣ ಕಾಣುತ್ತಿದೆ?"),
        "ml": ("പരുത്തിയിലയുടെ അടിയിൽ ചെറിയ വെള്ള കീടങ്ങൾ കണ്ടാൽ വെള്ളീച്ച ഒരു സാധ്യതയാണ്; മുഞ്ഞ, ജാസിഡ്, ത്രിപ്സ് എന്നിവയും ഉണ്ടാകാം. ഇല കുലുക്കുമ്പോൾ ചെറിയ വെള്ളീച്ചകൾ പറക്കുന്നുണ്ടോ, ഒട്ടുന്ന മധുരസ്രവമുണ്ടോ നോക്കൂ. ഈ വിവരണം മാത്രം കൊണ്ട് കീടം ഉറപ്പിക്കാനാവില്ല. ഇല കുലുക്കുമ്പോൾ എന്താണ് കാണുന്നത്?" if white else "പരുത്തിയിൽ മുഞ്ഞ, ജാസിഡ്, വെള്ളീച്ച, ത്രിപ്സ് എന്നിവ ഇലകളിൽ കാണാം. ബോൾവോം പുഴു പൂമൊട്ടുകളെയും കായുകളെയും നശിപ്പിക്കാം. ഇലയുടെ അടിഭാഗം, ഒട്ടുന്ന സ്രവം, പൂമൊട്ടുകൾ, കായിലെ തുളകൾ എന്നിവ പരിശോധിക്കുക. ഇത് പൊതുവിവരമാണ്; നിങ്ങളുടെ വയലിലെ കീടത്തെ സ്ഥിരീകരിക്കുന്നില്ല. എന്ത് ലക്ഷണമാണ് കാണുന്നത്?"),
        "mr": ("कापसाच्या पानांखाली छोटे पांढरे कीटक दिसत असतील तर पांढरी माशी एक शक्यता आहे; मावा, तुडतुडे किंवा फुलकिडेही असू शकतात. पान हलवल्यावर लहान पांढऱ्या माशा उडतात का आणि चिकट मधुरस आहे का पाहा. या वर्णनावरून कीड निश्चित होत नाही. पान हलवल्यावर काय दिसते?" if white else "कापसावर मावा, तुडतुडे, पांढरी माशी आणि फुलकिडे पानांवर आढळू शकतात. बोंडअळीची अळी फुले आणि बोंडांचे नुकसान करू शकते. पानांच्या खालच्या बाजूला कीड किंवा चिकटपणा, तसेच फुले/बोंडांवरील छिद्रे तपासा. ही सामान्य माहिती आहे; तुमच्या शेतातील कीड निश्चित केलेली नाही. कोणती लक्षणे दिसत आहेत?"),
    }
    return answers.get(lang, answers["en"])


COTTON_PEST_EDUCATION = {
    "en": """Common cotton pests include aphids, jassids, whiteflies, thrips and bollworms. Aphids cluster on tender shoots and leaf undersides; feeding can curl leaves and leave sticky honeydew. Jassids feed along leaf veins and may cause yellowing or browning at the margins. Whitefly adults flutter up when a leaf is disturbed; their nymphs stay on the underside and can leave honeydew. Thrips scrape leaves, causing silvery patches and distortion. Bollworm larvae feed on squares and flowers and bore into bolls; look for damaged squares, entry holes and frass.

Inspect representative plants regularly: check new growth and the undersides of upper, middle and lower leaves, then open damaged squares or bolls. A hand lens and gently tapping a leaf over white paper can help distinguish small insects. Keep field edges and weeds managed, avoid excess nitrogen, and conserve beneficial insects; do not spray without identifying the pest and following locally approved crop guidance.

Are you noticing white insects under leaves, leaf curling, damaged flowers, or holes in the cotton bolls?""",
    "te": """పత్తిలో పేనుబంక, పచ్చదోమ, తెల్లదోమ, తామర పురుగులు, కాయతొలిచే పురుగులు సాధారణంగా కనిపించవచ్చు. పేనుబంక లేత కొమ్మలు, ఆకుల కింద గుంపులుగా ఉండి ఆకులు ముడుచుకునేలా, జిగురు స్రావం కలిగేలా చేస్తుంది. పచ్చదోమ ఆకుల అంచుల వద్ద పసుపుదనం లేదా గోధుమరంగు కలిగించవచ్చు. ఆకును కదిలిస్తే తెల్లదోమలు ఎగురుతాయి; వాటి పిల్ల పురుగులు ఆకుల కిందే ఉంటాయి. తామర పురుగులు ఆకులపై వెండి రంగు గీతలు, వంకరను కలిగిస్తాయి. కాయతొలిచే పురుగులు పూల మొగ్గలు, పూలు, కాయలను దెబ్బతీస్తాయి; రంధ్రాలు, పురుగు విసర్జన కోసం చూడండి.

కొత్త చిగుళ్లు, ఆకుల పై-కింది భాగాలు, పూల మొగ్గలు, కాయలను తరచూ పరిశీలించండి. ఆకును తెల్ల కాగితం మీద మెల్లగా తట్టి పురుగులను చూడండి. పొలం అంచులు, కలుపును నిర్వహించండి; అధిక నత్రజనిని నివారించి మిత్ర పురుగులను కాపాడండి. పురుగును గుర్తించకుండా మందు పిచికారీ చేయవద్దు.

మీకు ఆకుల కింద తెల్ల పురుగులు, ఆకుల ముడత, దెబ్బతిన్న పూలు లేదా కాయల్లో రంధ్రాలు కనిపిస్తున్నాయా?""",
    "hi": """कपास में माहू, जैसिड, सफेद मक्खी, थ्रिप्स और बॉलवर्म आम कीट हैं। माहू कोमल टहनियों और पत्तियों के नीचे समूह में मिलते हैं; इनके कारण पत्तियां मुड़ सकती हैं और चिपचिपा मधुरस दिख सकता है। जैसिड पत्ती की नसों के पास रस चूसते हैं और किनारों पर पीलापन या भूरापन ला सकते हैं। पत्ती हिलाने पर सफेद मक्खी उड़ती है; उसके बच्चे पत्ती के नीचे चिपके रहते हैं। थ्रिप्स पत्तियों को खुरचकर चांदी जैसे निशान और विकृति बनाते हैं। बॉलवर्म की सुंडी कलियों और फूलों को खाकर बाद में टिंडों में छेद कर सकती है; छेद और भुरभुरा मल देखें।

नई बढ़त, पत्तियों की दोनों तरफ, कलियों और टिंडों की नियमित जांच करें। पत्ती को सफेद कागज पर हल्के से थपथपाएं और आवर्धक लेंस से देखें। खेत की मेड़ों और खरपतवार का प्रबंधन करें, अधिक नाइट्रोजन से बचें और मित्र कीटों को बचाएं। कीट पहचाने बिना छिड़काव न करें।

क्या आपको पत्तियों के नीचे सफेद कीट, मुड़ी पत्तियां, खराब फूल या टिंडों में छेद दिख रहे हैं?""",
    "ta": """பருத்தியில் அசுவினி, ஜாசிட், வெள்ளை ஈ, த்ரிப்ஸ் மற்றும் காய்ப்புழுக்கள் பொதுவாகக் காணப்படலாம். அசுவினி மென்மையான தளிர்களிலும் இலை அடிப்பக்கத்திலும் கூட்டமாக இருந்து இலை சுருக்கத்தையும் ஒட்டும் சாற்றையும் ஏற்படுத்தலாம். ஜாசிட் இலை நரம்புகளருகே சாறு உறிஞ்சி ஓரங்களில் மஞ்சள் அல்லது பழுப்பு நிறத்தை ஏற்படுத்தலாம். இலையை அசைத்தால் வெள்ளை ஈ பறக்கும்; அதன் இளம் நிலைகள் அடிப்பக்கத்தில் ஒட்டியிருக்கும். த்ரிப்ஸ் வெள்ளி போன்ற தடங்கள், இலை சுருக்கம் உண்டாக்கும். காய்ப்புழுக்கள் மொட்டுகள், பூக்களை உண்டு காய்களில் துளை போடலாம்; துளை மற்றும் கழிவைப் பாருங்கள்.

புதிய தளிர்கள், இலைகளின் இருபுறம், மொட்டுகள், காய்களைத் தொடர்ந்து பரிசோதிக்கவும். இலையை வெள்ளைத் தாளின் மேல் மெதுவாகத் தட்டி பூச்சிகளைப் பாருங்கள். வயல் ஓரங்களையும் களைகளையும் பராமரித்து, அதிக நைட்ரஜனைத் தவிர்த்து நன்மை செய்யும் பூச்சிகளைப் பாதுகாக்கவும். பூச்சியை அடையாளம் காணாமல் தெளிக்க வேண்டாம்.

இலைக்கீழ் வெள்ளைப் பூச்சிகள், சுருண்ட இலைகள், சேதமான பூக்கள் அல்லது காய்களில் துளைகள் உள்ளனவா?""",
    "kn": """ಹತ್ತಿಯಲ್ಲಿ ಹೇನು, ಜಾಸಿಡ್, ಬಿಳಿನೊಣ, ಥ್ರಿಪ್ಸ್ ಮತ್ತು ಕಾಯಿಕೊರಕ ಹುಳುಗಳು ಸಾಮಾನ್ಯ ಕೀಟಗಳು. ಹೇನು ಮೃದು ಚಿಗುರು ಮತ್ತು ಎಲೆಗಳ ಕೆಳಭಾಗದಲ್ಲಿ ಗುಂಪಾಗಿದ್ದು ಎಲೆ ಮುದುಡುವಿಕೆ ಹಾಗೂ ಅಂಟುವ ಸ್ರಾವ ಉಂಟುಮಾಡಬಹುದು. ಜಾಸಿಡ್ ಎಲೆ ನರಗಳ ಬಳಿ ರಸ ಹೀರಿ ಅಂಚು ಹಳದಿ ಅಥವಾ ಕಂದು ಬಣ್ಣವಾಗಿಸಬಹುದು. ಎಲೆಯನ್ನು ಅಲುಗಿಸಿದರೆ ಬಿಳಿನೊಣ ಹಾರುತ್ತದೆ; ಅದರ ಮರಿಹುಳುಗಳು ಎಲೆಯ ಕೆಳಗೆ ಅಂಟಿರುತ್ತವೆ. ಥ್ರಿಪ್ಸ್ ಬೆಳ್ಳಿಯ ಗೆರೆ ಮತ್ತು ಎಲೆ ವಕ್ರತೆ ಉಂಟುಮಾಡುತ್ತದೆ. ಕಾಯಿಕೊರಕಗಳು ಮೊಗ್ಗು, ಹೂವುಗಳನ್ನು ತಿಂದು ಕಾಯಿಗೆ ರಂಧ್ರ ಮಾಡಬಹುದು; ರಂಧ್ರ ಮತ್ತು ಹುಳದ ಮಲವನ್ನು ನೋಡಿ.

ಹೊಸ ಚಿಗುರು, ಎಲೆಗಳ ಮೇಲೂ ಕೆಳಗೂ, ಮೊಗ್ಗು ಮತ್ತು ಕಾಯಿಗಳನ್ನು ನಿಯಮಿತವಾಗಿ ಪರಿಶೀಲಿಸಿ. ಎಲೆಯನ್ನು ಬಿಳಿ ಕಾಗದದ ಮೇಲೆ ನಿಧಾನವಾಗಿ ತಟ್ಟಿ ಕೀಟಗಳನ್ನು ನೋಡಿ. ಹೊಲದ ಅಂಚು ಮತ್ತು ಕಳೆಗಳನ್ನು ನಿರ್ವಹಿಸಿ, ಅತಿಯಾದ ಸಾರಜನಕ ತಪ್ಪಿಸಿ, ಉಪಕಾರಿ ಕೀಟಗಳನ್ನು ಉಳಿಸಿ. ಕೀಟ ಗುರುತಿಸದೆ ಸಿಂಪಡಣೆ ಮಾಡಬೇಡಿ.

ಎಲೆಗಳ ಕೆಳಗೆ ಬಿಳಿ ಕೀಟ, ಮುದುಡಿದ ಎಲೆ, ಹಾನಿಯಾದ ಹೂವು ಅಥವಾ ಕಾಯಿಯಲ್ಲಿ ರಂಧ್ರ ಕಾಣುತ್ತಿದೆಯೇ?""",
    "ml": """പരുത്തിയിൽ മുഞ്ഞ, ജാസിഡ്, വെള്ളീച്ച, ത്രിപ്സ്, കായ്തുരപ്പൻ പുഴുക്കൾ എന്നിവ സാധാരണ കീടങ്ങളാണ്. മുഞ്ഞ ഇളം തണ്ടുകളിലും ഇലയുടെ അടിയിലും കൂട്ടമായി കാണാം; ഇല ചുരുളാനും ഒട്ടുന്ന സ്രവം ഉണ്ടാകാനും ഇടയാക്കും. ജാസിഡ് ഇലയുടെ അരികിൽ മഞ്ഞയോ തവിട്ടോ നിറം വരുത്താം. ഇല കുലുക്കുമ്പോൾ വെള്ളീച്ച പറക്കും; അതിന്റെ കുഞ്ഞുങ്ങൾ ഇലയുടെ അടിയിൽ ഒട്ടിയിരിക്കും. ത്രിപ്സ് വെള്ളിനിറത്തിലുള്ള പാടുകളും ഇലവളവും ഉണ്ടാക്കാം. കായ്തുരപ്പൻ പുഴുക്കൾ മുകുളങ്ങളും പൂക്കളും തിന്ന് കായിൽ തുളയിടും; തുളയും പുഴുവിന്റെ വിസർജ്യവും നോക്കുക.

പുതിയ തളിരുകൾ, ഇലയുടെ ഇരുവശം, മുകുളങ്ങൾ, കായുകൾ എന്നിവ പതിവായി പരിശോധിക്കുക. ഇല വെള്ളക്കടലാസിന് മുകളിൽ മെല്ലെ തട്ടി കീടങ്ങളെ നോക്കാം. വയൽവക്കുകളും കളകളും നിയന്ത്രിക്കുക, അധിക നൈട്രജൻ ഒഴിവാക്കുക, ഉപകാരിയായ കീടങ്ങളെ സംരക്ഷിക്കുക. കീടത്തെ തിരിച്ചറിയാതെ തളിക്കരുത്.

ഇലയുടെ അടിയിൽ വെള്ള കീടങ്ങളോ, ചുരുണ്ട ഇലകളോ, കേടായ പൂക്കളോ, കായിൽ തുളകളോ കാണുന്നുണ്ടോ?""",
    "mr": """कापसावर मावा, तुडतुडे, पांढरी माशी, फुलकिडे आणि बोंडअळी हे सामान्य कीटक आहेत. मावा कोवळ्या शेंड्यांवर व पानांच्या खालच्या बाजूस समूहाने राहतो; पाने वळू शकतात आणि चिकट स्राव दिसू शकतो. तुडतुडे पानांच्या कडांना पिवळसर किंवा तपकिरी करू शकतात. पान हलवल्यावर पांढरी माशी उडते; तिची पिल्ले पानाखाली चिकटलेली असतात. फुलकिडे चंदेरी ओरखडे आणि पाने वाकडी करतात. बोंडअळी कळ्या व फुले खाते आणि बोंडात छिद्र करू शकते; छिद्र व भुसभुशीत विष्ठा तपासा.

नवीन वाढ, पानांच्या दोन्ही बाजू, कळ्या व बोंडे नियमित तपासा. पान पांढऱ्या कागदावर हलकेच झटकून कीटक पाहा. बांधावरील तण नियंत्रणात ठेवा, अतिरिक्त नत्र टाळा आणि उपयुक्त कीटक जपा. कीड ओळखल्याशिवाय फवारणी करू नका.

पानाखाली पांढरे कीटक, वळलेली पाने, खराब फुले किंवा बोंडात छिद्रे दिसत आहेत का?""",
}


def _is_cotton_pest_education(text: str) -> bool:
    lower = (text or "").casefold()
    return any(word in lower for word in ("cotton", "patti", "పత్తి", "कपास", "பருத்தி", "ಹತ್ತி", "പരുത്തി", "कापूस")) and is_general_pest_education_question(lower)


def _is_white_insect_field_report(text: str) -> bool:
    lower = (text or "").casefold()
    white = any(word in lower for word in ("white", "తెల్ల", "सफेद", "வெள்ளை", "ಬಿಳಿ", "വെള്ളി", "पांढरी"))
    field = any(word in lower for word in ("my", "under", "there are", "there is", "నా", "मेरे", "मेरी", "என்", "ನನ್ನ", "എന്റെ", "माझ्या"))
    return white and field


def _cotton_pest_education_fallback(language: str) -> str:
    return COTTON_PEST_EDUCATION.get((language or "en")[:2].lower(), COTTON_PEST_EDUCATION["en"])

# Multilingual keywords and intent patterns across 7 languages
UNSUPPORTED_FORECAST_KEYWORDS = [
    "weather", "rain", "rainfall", "temperature", "forecast", "will it rain", "weather tomorrow",
    "వాతావరణం", "వర్షం", "వాన", "రేపు వర్షం", "మంచు",
    "मौसम", "बारिश", "बरसात", "तापमान", "कल बारिश",
    "வானிலை", "மழை", "வெப்பநிலை", "நாளை மழை",
    "ಹವಾಮಾನ", "ಮಳೆ", "ತಾಪಮಾನ", "ನಾಳೆ ಮಳೆ",
    "കാലാവസ്ഥ", "മഴ", "താപനില", "നാളെ മഴ",
    "हवामान", "पाऊस", "तापमान", "उद्या पाऊस",
]


def is_unsupported_forecast_request(text: str) -> bool:
    lower = (text or "").casefold()
    for keyword in UNSUPPORTED_FORECAST_KEYWORDS:
        if keyword.isascii():
            if re.search(rf"(?<![a-z]){re.escape(keyword)}(?![a-z])", lower):
                return True
        elif keyword in lower:
            return True
    return False


UNSUPPORTED_FORECAST_REPLIES = {
    "te": "క్షమించండి, కిసాన్ హితా స్థానిక ప్రత్యక్ష సూచనను పొందలదు. పంట ఎంపిక, పంట ఆరోగ్యం లేదా మార్కెట్ ధరల గురించి నేను సహాయం చేయగలను.",
    "en": "Sorry, Kisan Hita cannot retrieve a reliable local forecast. I can help with crop choice, crop health, or market reference prices instead.",
    "hi": "क्षमा करें, किसान हित स्थानीय पूर्वानुमान प्राप्त नहीं कर सकता। मैं फसल चयन, फसल स्वास्थ्य या बाजार संदर्भ भाव में मदद कर सकता हूँ।",
    "ta": "மன்னிக்கவும், கிசான் ஹிதா உள்ளூர் முன்னறிவிப்பைப் பெற முடியாது. பயிர் தேர்வு, பயிர் நலம் அல்லது சந்தை குறிப்புவிலைகளில் உதவலாம்.",
    "kn": "ಕ್ಷಮಿಸಿ, ಕಿಸಾನ್ ಹಿತಾ ಸ್ಥಳೀಯ ಮುನ್ಸೂಚನೆಯನ್ನು ಪಡೆಯಲು ಸಾಧ್ಯವಿಲ್ಲ. ಬೆಳೆ ಆಯ್ಕೆ, ಬೆಳೆ ಆರೋಗ್ಯ ಅಥವಾ ಮಾರುಕಟ್ಟೆ ಉಲ್ಲೇಖ ದರಗಳಲ್ಲಿ ಸಹಾಯ ಮಾಡಬಹುದು.",
    "ml": "ക്ഷമിക്കണം, കിസാൻ ഹിതയ്ക്ക് പ്രാദേശിക പ്രവചനം ലഭ്യമാക്കാനാവില്ല. വിള തിരഞ്ഞെടുപ്പ്, വിളയുടെ ആരോഗ്യം, വിപണി സൂചനാ വിലകൾ എന്നിവയിൽ സഹായിക്കാം.",
    "mr": "क्षमस्व, किसान हित स्थानिक अंदाज मिळवू शकत नाही. पीक निवड, पीक आरोग्य किंवा बाजार संदर्भभावाबद्दल मदत करू शकतो.",
}

# Explicit crop selection / recommendation phrases (bare 'crop' removed to avoid false triggers)
CROP_ADVISOR_KEYWORDS = [
    # English
    "which crop", "choose crop", "choose a crop", "help me choose a crop", "help me choose a crop for", "recommend crop", "suggest crop", "crop suit",
    "crop to grow", "what to grow", "suitable crop", "best crop", "crop for rabi",
    "crop for kharif", "crop for summer", "crops for rabi", "crops for kharif",
    "crop selection", "recommend a crop", "crops suitable for", "which crop to sow",
    "what should i grow", "which crop is suitable", "crop recommendation",
    "crop for black soil", "crop for red soil", "crops for black soil", "crops for red soil",
    # Telugu
    "ఏ పంట", "పంట ఎంపిక", "పంట సిఫార్సు", "ఏ పంట వేయాలి", "ఏ పంటలు", "రబీ పంటలు",
    "ఖరీఫ్ పంటలు", "నల్ల రేగడికి ఏ పంట", "ఎర్ర నేలకు ఏ పంట", "ఏ పంట అనుకూలం",
    # Hindi
    "कौन सी फसल", "कौनसी फसल", "फसल चयन", "फसल सिफारिश", "फसल उगाएं", "फसल लगाएं",
    "रबी की फसल", "खरीफ की फसल", "काली मिट्टी के लिए फसल", "कौन सी फसल उपयुक्त",
    # Tamil
    "எந்த பயிர்", "பயிர் தேர்வு", "பயிர் செய்யலாம்", "பருவ பயிர்",
    # Kannada
    "ಯಾವ ಬೆಳೆ", "ಬೆಳೆ ಆಯ್ಕೆ", "ಬೆಳೆ ಬೆಳೆಯಲು", "ಯಾವ ಬೆಳೆ ಸೂಕ್ತ",
    # Malayalam
    "ഏത് വിള", "വിള തെരഞ്ഞെടുപ്പ്", "വിള കൃഷി", "ഏത് വിളയാണ് അനുയോജ്യം",
    # Marathi
    "कोणते पीक", "कोणतं पीक", "पीक निवड", "पीक लावावे", "कोणते पीक योग्य"
]

# Harvesting & post-harvest management keywords across all 7 languages
HARVESTING_KEYWORDS = [
    # English
    "harvest", "harvesting", "when to harvest", "how to harvest", "picking", "sun drying",
    "post-harvest", "plucking", "dry chilli", "drying chilli", "drying",
    # Telugu
    "కోత", "కోయడం", "కొయ్యాలి", "కోత కోయడం", "తీత", "తీయడం", "ఎండబెట్టడం", "ఆరబెట్టడం",
    # Hindi
    "कटाई", "तोड़ाई", "चुनाई", "तुड़ाई", "काटना", "सुखाना", "मिर्च सुखाना",
    # Tamil
    "அறுவடை", "பறித்தல்", "உலர்த்துதல்",
    # Kannada
    "ಕೊಯ್ಲು", "ಕಟಾವು", "ಕಿಳುವುದು", "ಒಣಗಿಸುವುದು",
    # Malayalam
    "വിളവെടുപ്പ്", "പറിക്കൽ", "ഉണക്കൽ",
    # Marathi
    "कापणी", "तोडणी", "सुकवणे"
]

CULTIVATION_PRACTICE_KEYWORDS = [
    # English
    "how to grow", "how to cultivate", "cultivation practice", "package of practices",
    "spacing", "fertilizer application", "irrigation schedule", "weeding",
    "transplanting", "nursery management",
    # Telugu
    "సాగు పద్ధతి", "ఎలా సాగు చేయాలి", "ఎరువుల యాజమాన్యం", "నారుమడి",
    # Hindi
    "खेती कैसे करें", "उर्वरक प्रबंधन", "खरपतवार नियंत्रण",
    # Tamil
    "சாகுபடி முறை", "உர நிர்வாகம்",
    # Kannada
    "ಬೇಸಾಯ ಪದ್ಧತಿ", "ಗೊಬ್ಬರ ನಿರ್ವಹಣೆ",
    # Malayalam
    "കൃഷി രീതി", "വളപ്രയോഗം",
    # Marathi
    "लागवड पद्धत", "खत व्यवस्थापन"
]

CROP_HEALTH_KEYWORDS = [
    # English
    "yellow", "leaves", "leaf", "pest", "disease", "fungus", "spot", "blight", "wilt", "insect", "damaged", "worm", "attack", "curling", "curl", "wilting", "holes", "hole in the bolls",
    # Telugu
    "ఆకులు", "ఆకు", "పసుపు", "తెగులు", "పురుగు", "మచ్చ", "ఎండిపోవడం", "ముడత",
    # Hindi
    "पत्तियां", "पत्ते", "पत्ता", "पीली", "पीले", "पीला", "कीट", "रोग", "फफूंद", "धब्बे", "मुरझा", "सुखना", "मुरझाना",
    # Tamil
    "இலைகள்", "இலை", "மஞ்சள்", "பூச்சி", "நோய்", "வாடல்", "புள்ளி",
    # Kannada
    "ಎಲೆಗಳು", "ಎಲೆ", "ಹಳದಿ", "ಕೀಟ", "ರೋಗ", "ಮಚ್ಚೆ", "ಒಣಗುವಿಕೆ",
    # Malayalam
    "ഇലകൾ", "ഇല", "മഞ്ഞ", "കീടം", "രോഗം", "വാട്ടം", "പുള്ളി",
    # Marathi
    "पाने", "पान", "पिवळी", "पिवळे", "पिवळा", "कीड", "रोग", "करपा", "सुकायला", "अळी"
]

GENERAL_PEST_EDUCATION_PATTERNS = [
    r"\btell me (?:more )?about\b.*\b(pests?|insects?)\b",
    r"\bwhich insects? (?:attack|affect)\b",
    r"\bhow (?:can i|do i) identify\b.*\b(whiteflies|pests?|insects?)\b",
    r"\bwhat damage does\b.*\b(cause|do)\b",
    r"\bhow (?:do i|can i) prevent\b.*\b(pests?|insects?)\b",
    r"\b(common|important)\b.*\b(cotton )?pests?\b",
    r"\bpests? of cotton\b",
    r"పత్తి.*పురుగుల గురించి",
    r"कपास.*कीटों के बारे में",
    r"பருத்தி.*பூச்சிகள் பற்றி",
    r"ಹತ್ತಿ.*ಕೀಟಗಳ ಬಗ್ಗೆ",
    r"പരുത്തി.*കീടങ്ങളെ കുറിച്ച്",
    r"कापूस.*किडींबद्दल",
]

FIELD_DIAGNOSIS_PATTERNS = [
    r"\b(my|our)\b.*\b(crop|plant|leaf|leaves|cotton|bolls?|field)\b",
    r"\bthere (?:are|is)\b.*\b(insects?|spots?|holes?|damage|yellow)\b",
    r"\b(under my|on my|in my)\b",
    r"\b(leaves?|crop|bolls?) (?:are|is|have|has)\b",
    r"\bshowing\b.*\b(symptoms?|spots?|yellow|curl|holes?)\b",
]


def is_general_pest_education_question(text: str) -> bool:
    lower = (text or "").casefold()
    if any(re.search(pattern, lower, re.I) for pattern in FIELD_DIAGNOSIS_PATTERNS):
        return False
    return any(re.search(pattern, lower, re.I) for pattern in GENERAL_PEST_EDUCATION_PATTERNS)


def _looks_like_diagnostic_template_response(text: Optional[str]) -> bool:
    lower = (text or "").casefold()
    diagnostic_markers = (
        "farmer-reported", "farmer reported", "onset:", "affected area", "visual analysis status",
        "possible contributing factors", "expert-confirmed", "expert confirmed", "laboratory confirmation",
        "open crop health", "open check crop", "కనిపించిన లక్షణాలు", "ரైతு", "రైతు నివేదించిన సమాచారం",
        "किसान द्वारा दर्ज जानकारी", "விவசாயி தெரிவித்த தகவல்", "ರೈತರು ವರದಿ ಮಾಡಿದ ವಿವರ",
        "കർഷകൻ രേഖപ്പെടുത്തിയ വിവരങ്ങൾ", "शेतकऱ्याने नोंदवलेली माहिती", "संभावित कारक",
        "சாத்தியமான காரணிகள்", "ಸಂಭಾವ್ಯ ಅಂಶಗಳು", "സാധ്യമായ കാരണങ്ങൾ", "संभाव्य घटक",
        "रासायनिक रहित प्रबंधन", "രാസേതര പരിപാലന മാർഗ്ഗങ്ങൾ", "ರಾಸಾಯನಿಕ ರಹಿತ ನಿರ್ವಹಣಾ ಕ್ರಮಗಳು",
    )
    return any(marker in lower for marker in diagnostic_markers)

MARKET_PRICE_KEYWORDS = [
    # English
    "price", "mandi", "market", "rate", "quintal", "selling", "bhav", "cost", "chilli price", "cotton price", "tomato price",
    # Telugu
    "ధర", "మార్కెట్", "మండి", "రేటు", "క్వింటాల్", "మిర్చి ధర", "పత్తి ధర", "టమాటా ధర",
    # Hindi
    "दाम", "भाव", "मंडी", "बाजार", "कीमत", "क्विंटल", "मिर्च का भाव", "कपास का भाव",
    # Tamil
    "விலை", "மண்டி", "சந்தை", "விகிதம்",
    # Kannada
    "ಬೆಲೆ", "ಮಾರುಕಟ್ಟೆ", "ಮಂಡಿ", "ದರ",
    # Malayalam
    "വില", "വിപണി", "മാർക്കറ്റ്", "നിരക്ക്",
    # Marathi
    "भाव", "बाजार", "मार्केट", "दर", "किंमत"
]

CANCEL_WORDS = [
    "cancel", "stop", "never mind", "exit", "quit", "skip",
    "రద్దు", "వద్దు", "ఆపు", "ఆపండి",
    "रद्द", "रोकें", "बंद करो", "नहीं चाहिए",
    "ரத்து", "நிறுத்து",
    "ರದ್ದು", "ನಿಲ್ಲಿಸಿ",
    "റദ്ദാക്കുക", "നിർത്തുക",
    "रद्द करा", "थांबवा"
]

def is_cancel_intent(text: str) -> bool:
    lower = text.lower().strip()
    return any(cw in lower for cw in CANCEL_WORDS)

def detect_intent(text: str) -> str:
    lower = text.lower()

    # 1. Harvesting and agronomic practices (checked first so they are not hijacked by Crop Advisor)
    for kw in HARVESTING_KEYWORDS + CULTIVATION_PRACTICE_KEYWORDS:
        if kw in lower:
            return "general"

    # Suitability language wins over terms such as irrigation that also occur
    # in general water-management questions. Keep this after practice checks.
    for phrase in CROP_ADVISOR_KEYWORDS:
        if phrase in lower:
            return "crop_advisor"

    # Educational pest questions are not crop diagnoses. Route them to the
    # conversational assistant before broad pest/insect symptom keywords.
    if is_general_pest_education_question(lower):
        return "general"

    # 2. Crop Health (symptoms, pests, diseases)
    for kw in CROP_HEALTH_KEYWORDS:
        if kw in lower:
            return "crop_health"

    # 3. Market Prices (prices, mandi, rates)
    for kw in MARKET_PRICE_KEYWORDS:
        if kw in lower:
            return "market_prices"

    # 5. Crop Advisor multi-word selection phrases
    for phrase in CROP_ADVISOR_KEYWORDS:
        if phrase in lower:
            return "crop_advisor"

    return "general"

# ----------------- ENTITY EXTRACTION HELPERS -----------------

COMMODITY_MAPPINGS = [
    ("Chilli", ["chilli", "chili", "mirchi", "మిర్చి", "मिर्च", "மிளகாய்", "ಮೆಣಸಿನಕಾಯಿ", "മുളക്", "मिरची"]),
    ("Cotton", ["cotton", "patti", "పత్తి", "कपास", "பருத்தி", "ಹತ್ತಿ", "പരുത്തി", "कापूस", "कापस"]),
    ("Tomato", ["tomato", "tamatar", "టమాటా", "టమాట", "टमाटर", "தக்காளி", "ಟೊಮೆಟೊ", "തക്കാളി", "टोमॅटो"]),
    ("Paddy", ["paddy", "rice", "వరి", "ధాన్యం", "బియ్యం", "धान", "चावल", "நெல்", "அரிசி", "ಭತ್ತ", "ಅಕ್ಕಿ", "നെല്ല്", "അരി", "भात", "तांदूळ"]),
    ("Groundnut", ["groundnut", "peanut", "వేరుశనగ", "పల్లీ", "मूंगफली", "நிலக்கடலை", "வேர்க்கடலை", "ಕಡಲೆಕಾಯಿ", "നിലക്കടല", "भुईमूग"]),
    ("Onion", ["onion", "pyaz", "ఉల్లి", "ఉల్లిపాయ", "प्याज", "வெங்காயம்", "ಈರುಳ್ಳಿ", "സവാള", "कांदा"]),
    ("Bengal Gram", ["bengal gram", "chana", "gram", "శనగలు", "శనగ", "चना", "கொண்டைக்கடலை", "கடலை", "ಕಡಲೆ", "കടല", "हरभरा"]),
    ("Soybean", ["soybean", "soya", "సోయాబీన్", "సోయా", "सोयाबीन", "சோயாபீன்", "ಸೋಯಾಬೀನ್"]),
    ("Maize", ["maize", "corn", "మొక్కజొన్న", "मक्का", "மக்காச்சோளம்", "ಮೆಕ್ಕೆಜೋಳ", "മക്കച്ചോളം", "मका"]),
    ("Turmeric", ["turmeric", "haldi", "పసుపు", "हल्दी", "மஞ்சள்", "ಅರಿಶಿನ", "മഞ്ഞൾ", "हळद"]),
]

COMMODITY_LOCALIZED_NAMES = {
    "Chilli": {
        "te": "మిర్చి",
        "hi": "मिर्च",
        "ta": "மிளகாய்",
        "kn": "ಮೆಣಸಿನಕಾಯಿ",
        "ml": "മുളക്",
        "mr": "मिरची"
    },
    "Cotton": {
        "te": "పత్తి",
        "hi": "कपास",
        "ta": "பருத்தி",
        "kn": "ಹತ್ತಿ",
        "ml": "പരുത്തി",
        "mr": "कापूस"
    },
    "Tomato": {
        "te": "టమాటా",
        "hi": "टमाटर",
        "ta": "தக்காளி",
        "kn": "ಟೊಮೆಟೊ",
        "ml": "തക്കാളി",
        "mr": "टोमॅटो"
    },
    "Paddy": {
        "te": "వరి / ధాన్యం",
        "hi": "धान / चावल",
        "ta": "நெல்",
        "kn": "ಭತ್ತ",
        "ml": "നെല്ല്",
        "mr": "भात"
    },
    "Groundnut": {
        "te": "వేరుశనగ",
        "hi": "मूंगफली",
        "ta": "நிலக்கடலை",
        "kn": "ಕಡಲೆಕಾಯಿ",
        "ml": "നിലക്കടല",
        "mr": "भुईमूग"
    },
    "Onion": {
        "te": "ఉల్లిపాయ",
        "hi": "प्याज",
        "ta": "வெங்காயம்",
        "kn": "ಈರುಳ್ಳಿ",
        "ml": "സവാള",
        "mr": "कांदा"
    },
    "Bengal Gram": {
        "te": "శనగలు",
        "hi": "चना",
        "ta": "கொண்டைக்கடலை",
        "kn": "ಕಡಲೆ",
        "ml": "കടല",
        "mr": "हरभरा"
    },
    "Soybean": {
        "te": "సోయాబీన్",
        "hi": "सोयाबीन",
        "ta": "சோயாபீன்",
        "kn": "ಸೋಯಾಬೀನ್",
        "ml": "സോയാബീൻ",
        "mr": "सोयाबीन"
    }
}

DISTRICT_MAPPINGS = [
    ("Warangal", ["warangal", "వరంగల్", "वारंगल", "वारंगळ", "வாரங்கல்", "ವಾರಂಗಲ್", "വാറങ്കൽ"]),
    ("Khammam", ["khammam", "ఖమ్మం", "खम्मम", "கம்மம்", "ಖಮ್ಮಂ", "ഖമ്മം"]),
    ("Guntur", ["guntur", "గుంటూరు", "गुंटूर", "குண்டூர்", "ಗುಂಟೂರು", "ഗുണ്ടൂർ"]),
    ("Karimnagar", ["karimnagar", "కరీంనగర్", "करीमनगर", "கரீம்நகர்", "ಕರೀಂನಗರ"]),
    ("Nalgonda", ["nalgonda", "నల్గొండ", "नलगोंडा", "நல்கொண்டா", "ನಲ್ಗೊಂಡ"]),
    ("Nizamabad", ["nizamabad", "నిజామాబాద్", "निजामाबाद", "நிசாமாபாத்", "ನಿಜಾಮಾಬಾದ್"]),
    ("Nellore", ["nellore", "నెల్లూరు", "नेल्लोर", "நெல்லூர்", "ನೆಲ್ಲೂರು"]),
    ("Kurnool", ["kurnool", "కర్నూలు", "कुरनूल", "கர்னூல்", "ಕರ್ನೂಲು"]),
    ("Nagpur", ["nagpur", "నాగ్‌పూర్", "నాగపూర్", "नागपूर", "नागपुर"]),
    ("Nashik", ["nashik", "నాసిక్", "नाशिक"]),
    ("Amravati", ["amravati", "అమరావతి", "अमरावती"]),
    ("Raichur", ["raichur", "రాయచూర్", "रायचूर", "ರಾಯಚೂರು"]),
    ("Coimbatore", ["coimbatore", "కోయంబత్తూరు", "कोयंबटूर", "கோயம்புத்தூர்"]),
]

SOIL_MAPPINGS = [
    ("Black Cotton Soil", ["black cotton", "black soil", "నల్ల రేగడి", "నల్ల నేల", "నల్లమట్టి", "काली मिट्टी", "कपास मिट्टी", "கரிசல் மண்", "கரிசல்", "ಕಪ್ಪು ಮಣ್ಣು", "കറുത്ത മണ്ണ്", "काळी माती"]),
    ("Red Sandy Loam", ["red soil", "red sandy", "red loam", "ఎర్ర నేల", "ఎర్ర మట్టి", "लाल मिट्टी", "செம்மண்", "ಕೆಂಪು ಮಣ್ಣು", "ചുവന്ന മണ്ണ്", "तांबडी माती", "लाल माती"]),
    ("Alluvial Soil", ["alluvial", "sandy loam", "loam", "sandy", "ఒండ్రు నేల", "ఒండ్రు", "ఇసుక నేల", "ఇసుక రేగడి", "दोमट मिट्टी", "बलुई", "வண்டல் மண்", "வண்டல்", "ಮೆಕ್ಕಲು ಮಣ್ಣು", "എക്കൽ മണ്ണ്", "गाळाची माती"]),
]

WATER_MAPPINGS = [
    ("Good irrigation", ["good irrigation", "canal", "borewell", "bore", "well", "tubewell", "good water", "మంచి నీరు", "బావి", "బోరు", "బోరు బావి", "కాల్వ", "మంచి నీటిపారుదల", "अच्छी सिंचाई", "ट्यूबवेल", "नहर", "நல்ல பாசனம்", "கிணறு", "ಉತ್ತಮ ನೀರಾವರಿ", "ಬೋರ್‌ವೆಲ್", "നല്ല നനയ്ക്കൽ", "കുഴൽക്കിണർ", "चांगली सिंचन सोय", "विहीर"]),
    ("Moderate irrigation", ["moderate irrigation", "limited water", "medium", "moderate", "మోస్తరు", "పరిమిత నీరు", "ఒక మోస్తరు", "मध्यम सिंचाई", "सीमित", "மிதமான பாசனம்", "ಮಧ್ಯಮ ನೀರಾವರಿ", "മിതമായ നനയ്ക്കൽ", "मध्यम सिंचन"]),
    ("Rainfed / Dryland", ["rainfed", "dryland", "rain dependent", "dry", "వర్షాధారం", "కేవలం వర్షం", "వర్షాధార", "वर्षा आधारित", "केवल बारिश", "बारिश पर निर्भर", "மானாவாரி", "மழையை நம்பி", "ಮಳೆಯಾಶ್ರಿತ", "മഴയെ ആശ്രയിച്ച്", "कोरडवाहू", "पावसावर आधारित"]),
]

CROP_HEALTH_CROP_MAPPINGS = [
    ("Cotton", ["cotton", "పత్తి", "कपास", "பருத்தி", "ಹತ್ತಿ", "പരുത്തി", "कापूस", "कापस"]),
    ("Chilli", ["chilli", "chili", "mirchi", "మిర్చి", "मिर्च", "மிளகாய்", "ಮೆಣಸಿನಕಾಯಿ", "മുളക്", "मिरची"]),
    ("Paddy", ["paddy", "rice", "వరి", "ధాన్యం", "धान", "चावल", "நெல்", "ಭತ್ತ", "നെല്ല്", "भात"]),
    ("Tomato", ["tomato", "టమాటా", "టమాట", "टमाटर", "தக்காளி", "ಟೊಮೆಟೊ", "തക്കാളി", "टोमॅटो"]),
    ("Groundnut", ["groundnut", "వేరుశనగ", "मूंगफली", "நிலக்கடலை", "ಕಡಲೆಕಾಯಿ", "നിലക്കടല", "भुईमूग"]),
    ("Bengal Gram", ["bengal gram", "gram", "శనగలు", "चना", "கொண்டைக்கடலை", "ಕಡಲೆ", "കടല", "हरभरा"]),
    ("Soybean", ["soybean", "సోయాబీన్", "सोयाबीन", "சோயாபீன்", "ಸೋಯಾಬೀನ್"]),
]

def match_synonym(syn: str, text: str) -> bool:
    lower = text.lower()
    if syn.isascii():
        pattern = r'(?<![a-z0-9])' + re.escape(syn.lower()) + r'(?![a-z0-9])'
        return bool(re.search(pattern, lower))
    return syn in lower

def extract_commodity(text: str) -> Optional[str]:
    for canonical, synonyms in COMMODITY_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

def extract_district(text: str) -> Optional[str]:
    for canonical, synonyms in DISTRICT_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

def extract_mandi(text: str) -> Optional[str]:
    """Extract an explicitly named mandi without relying on sample records."""
    # Bare terms such as "Chilli mandi prices" describe the task, not a named
    # market. Require the explicit yard suffix; district names are extracted
    # separately and remain exact.
    match = re.search(r"\b([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,2}\s+(?:APMC\s+Yard|Market\s+Yard))\b", text, re.I)
    if not match:
        return None
    candidate = match.group(1).strip(" .,-")
    candidate = re.split(r"\b(?:at|in|near)\b", candidate, flags=re.I)[-1].strip()
    return candidate if len(candidate) > 3 else None

def extract_soil_type(text: str) -> Optional[str]:
    for canonical, synonyms in SOIL_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

def extract_water_source(text: str) -> Optional[str]:
    for canonical, synonyms in WATER_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

SEASON_MAPPINGS = [
    ("Rabi (Winter)", ["rabi", "winter", "cold season", "రబీ", "యాసంగి", "చలికాలం", "रबी", "सर्दी", "சம்பா", "குளிர்காலம்", "ಹಿಂಗಾರು", "ಚಳಿಗಾಲ", "റബി", "ശീതകാലം", "हिवाळा"]),
    ("Kharif (Monsoon)", ["kharif", "monsoon", "rainy season", "ఖరీఫ్", "వానాకాలం", "వర్షాకాలం", "खरीफ", "मानसून", "बरसात", "குறுவை", "மழைக்காலம்", "ಮುಂಗಾರು", "ಮಳೆಗಾಲ", "ഖാരിഫ്", "മഴക്കാലം", "पावसाळा"]),
    ("Summer (Zaid)", ["summer", "zaid", "hot season", "ఎండాకాలం", "జాయెద్", "जायद", "गर्मी", "கோடை", "ಬೇಸಿಗೆ", "വേനൽ", "उन्हाळा"])
]

def extract_season(text: str) -> Optional[str]:
    for canonical, synonyms in SEASON_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

def extract_health_crop(text: str) -> Optional[str]:
    for canonical, synonyms in CROP_HEALTH_CROP_MAPPINGS:
        for syn in synonyms:
            if match_synonym(syn, text):
                return canonical
    return None

# ----------------- LOCALIZED SEQUENTIAL SLOT PROMPTS -----------------

SLOT_PROMPTS = {
    "market_prices": {
        "commodity": {
            "te": "మీరు ఏ పంట లేదా సరుకు మార్కెట్ ధర తెలుసుకోవాలనుకుంటున్నారు? (ఉదాహరణకు: మిర్చి, పత్తి, టమాటా, ధాన్యం)",
            "hi": "आप किस फसल या जिंस का मंडी भाव जानना चाहते हैं? (जैसे: मिर्च, कपास, टमाटर, धान)",
            "ta": "எந்த பயிர் அல்லது பொருளின் சந்தை விலையை அறிய விரும்புகிறீர்கள்? (எ.கா: மிளகாய், பருத்தி, தக்காளி, நெல்)",
            "kn": "ನೀವು ಯಾವ ಬೆಳೆ ಅಥವಾ ಸರಕಿನ ಮಾರುಕಟ್ಟೆ ದರವನ್ನು ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ? (ಉದಾ: ಮೆಣಸಿನಕಾಯಿ, ಹತ್ತಿ, ಟೊಮೆಟೊ, ಭತ್ತ)",
            "ml": "ഏത് വിളയുടെ അല്ലെങ്കിൽ ഉൽപ്പന്നത്തിന്റെ വിപണി വിലയാണ് അറിയേണ്ടത്? (ഉദാ: മുളക്, പരുത്തി, തക്കാളി, നെല്ല്)",
            "mr": "आपण कोणत्या पिकाचा किंवा शेतमालाचा बाजार भाव जाणून घेऊ इच्छिता? (उदा: मिरची, कापूस, टोमॅटो, भात)",
            "en": "Which crop or commodity's market price would you like to check? (e.g. Chilli, Cotton, Tomato, Paddy)",
        },
        "district": {
            "te": "{commodity} ధర కోసం మీ జిల్లా లేదా సమీప మార్కెట్ యార్డు ఏది? (ఉదా: వరంగల్, ఖమ్మం, గుంటూరు)",
            "hi": "{commodity} के भाव के लिए आपका जिला या मंडी कौन सा है? (जैसे: वारंगल, खम्मम, गुंटूर)",
            "ta": "{commodity} விலைக்கு உங்கள் மாவட்டம் அல்லது சந்தை எது? (எ.கா: வாரங்கல், குண்டூர்)",
            "kn": "{commodity} ದರಕ್ಕಾಗಿ ನಿಮ್ಮ ಜಿಲ್ಲೆ ಅಥವಾ ಮಂಡಿ ಯಾವುದು? (ಉದಾ: ವಾರಂಗಲ್, ಖಮ್ಮಂ, ಗುಂಟೂರು)",
            "ml": "{commodity} വിലയ്ക്കായി ഏത് ജില്ല അല്ലെങ്കിൽ മാർക്കറ്റ് ആണ് വേണ്ടത്? (ഉദാ: വാറങ്കൽ, ഗുണ്ടൂർ)",
            "mr": "{commodity} च्या भावासाठी आपला जिल्हा किंवा बाजारपेठ कोणती आहे? (उदा: वारंगळ, खम्मम, गुंटूर)",
            "en": "Which district or mandi would you like to check for {commodity}? (e.g. Warangal, Khammam, Guntur)",
        }
    },
    "crop_advisor": {
        "district": {
            "te": "మీ పొలం ఏ జిల్లాలో ఉంది? (ఉదా: నెల్లూరు, వరంగల్, గుంటూరు)",
            "hi": "आपका खेत किस जिले में है? (जैसे: नेल्लोर, वारंगल, गुंटूर)",
            "ta": "உங்கள் நிலம் எந்த மாவட்டத்தில் உள்ளது? (எ.கா: நெல்லூர், வாரங்கல், குண்டூர்)",
            "kn": "ನಿಮ್ಮ ಹೊಲ ಯಾವ ಜಿಲ್ಲೆಯಲ್ಲಿದೆ? (ಉದಾ: ನೆಲ್ಲೂರು, ವಾರಂಗಲ್, ಗುಂಟೂರು)",
            "ml": "നിങ്ങളുടെ കൃഷിയിടം ഏത് ജില്ലയിലാണ്? (ഉദാ: നെല്ലൂർ, വാറങ്കൽ, ഗുണ്ടൂർ)",
            "mr": "तुमचे शेत कोणत्या जिल्ह्यात आहे? (उदा: नेल्लोर, वारंगळ, गुंटूर)",
            "en": "Which district is your farm in? (e.g. Nellore, Warangal, Guntur)",
        },
        "soil_type": {
            "te": "మీ పొలంలో నేల రకం ఏమిటి? (ఉదా: నల్ల రేగడి నేల, ఎర్ర నేల, లేదా ఇసుక/ఒండ్రు నేల)",
            "hi": "आपके खेत की मिट्टी का प्रकार क्या है? (जैसे: काली मिट्टी, लाल मिट्टी, या दोमट मिट्टी)",
            "ta": "உங்கள் நிலத்தின் மண் வகை என்ன? (எ.கா: கரிசல் மண், செம்மண், வண்டல் மண்)",
            "kn": "ನಿಮ್ಮ ಜಮೀನಿನ ಮಣ್ಣಿನ ಪ್ರಕಾರ ಯಾವುದು? (ಉದಾ: ಕಪ್ಪು ಮಣ್ಣು, ಕೆಂಪು ಮಣ್ಣು)",
            "ml": "നിങ്ങളുടെ കൃഷിഭൂമിയിലെ മണ്ണിന്റെ തരം ഏതാണ്? (ഉദാ: കറുത്ത മണ്ണ്, ചുവന്ന മണ്ണ്)",
            "mr": "आपल्या शेतातील मातीचा प्रकार कोणता आहे? (उदा: काळी माती, तांबडी माती)",
            "en": "What type of soil does your farm have? (e.g. Black Cotton Soil, Red Soil, or Alluvial Loam)",
        },
        "water_source": {
            "te": "మీ పొలానికి నీటి సదుపాయం ఎలా ఉంది? (ఉదా: మంచి నీటిపారుదల / బోర్, ఒక మోస్తరు నీరు, లేదా వర్షాధారం?)",
            "hi": "आपके खेत में सिंचाई / पानी की क्या व्यवस्था है? (जैसे: अच्छी सिंचाई, मध्यम, या केवल वर्षा आधारित?)",
            "ta": "உங்கள் பாசன வசதி எவ்வாறு உள்ளது? (எ.கா: நல்ல பாசனம், மிதமான பாசனம், அல்லது மானாவாரி?)",
            "kn": "ನಿಮ್ಮ ನೀರಾವರಿ ಸೌಲಭ್ಯ ಹೇಗಿದೆ? (ಉದಾ: ಉತ್ತಮ ನೀರಾವರಿ, ಮಧ್ಯಮ, ಅಥವಾ ಮಳೆಯಾಶ್ರಿತ?)",
            "ml": "നിങ്ങളുടെ നനയ്ക്കൽ സൗകര്യം എങ്ങനെയുണ്ട്? (ഉദാ: നല്ല നനയ്ക്കൽ, മിതമായത്, അല്ലെങ്കിൽ മഴയെ ആശ്രയിച്ച്?)",
            "mr": "आपल्या शेतात सिंचनाची सोय कशी आहे? (उदा: चांगली सिंचन सोय, मध्यम, किंवा कोरडवाहू?)",
            "en": "What is your irrigation availability? (e.g. Good irrigation, Moderate, or Rainfed / Dryland)",
        }
    },
    "crop_health": {
        "crop_name": {
            "te": "మీరు ఏ పంట సాగు చేస్తున్నారు? (ఉదా: పత్తి, మిర్చి, వరి, టమాటా)",
            "hi": "आप किस फसल की खेती कर रहे हैं? (जैसे: कपास, मिर्च, धान, टमाटर)",
            "ta": "நீங்கள் எந்தப் பயிரை சாகுபடி செய்கிறீர்கள்? (எ.கா: பருத்தி, மிளகாய், நெல், தக்காளி)",
            "kn": "ನೀವು ಯಾವ ಬೆಳೆಯನ್ನು ಬೆಳೆಯುತ್ತಿದ್ದೀರಿ? (ಉದಾ: ಹತ್ತಿ, ಮೆಣಸಿನಕಾಯಿ, ಭತ್ತ, ಟೊಮೆಟೊ)",
            "ml": "നിങ്ങൾ ഏത് വിളയാണ് കൃഷി ചെയ്യുന്നത്? (ഉദാ: പരുത്തി, മുളക്, നെല്ല്, തക്കാളി)",
            "mr": "आपण कोणते पीक घेत आहात? (उदा: कापूस, मिरची, भात, टोमॅटो)",
            "en": "Which crop are you currently growing? (e.g. Cotton, Chilli, Paddy, Tomato)",
        },
        "symptoms": {
            "te": "{crop_name} మొక్కలపై మీరు ఏ లక్షణాలు గమనించారు? (ఉదా: ఆకులు పసుపు రంగులోకి మారడం, ముడత, గోధుమ మచ్చలు, లేదా వాడిపోవడం)",
            "hi": "{crop_name} पर आपको क्या लक्षण दिखाई दे रहे हैं? (जैसे: पत्तियां पीली पड़ना, मुड़ना, धब्बे, या मुरझाना)",
            "ta": "{crop_name} பயிரில் நீங்கள் காணும் அறிகுறிகள் என்ன? (எ.கா: இலை மஞ்சள் ஆகுதல், சுருங்குதல், புள்ளிகள்)",
            "kn": "{crop_name} ಬೆಳೆಯಲ್ಲಿ ನೀವು ಯಾವ ಲಕ್ಷಣಗಳನ್ನು ಗಮನಿಸಿದ್ದೀರಿ? (ಉದಾ: ಎಲೆ ಹಳದಿಯಾಗುವುದು, ಮುದುಡುವಿಕೆ, ಮಚ್ಚೆಗಳು)",
            "ml": "{crop_name} വിളയിൽ എന്തൊക്കെ ലക്ഷണങ്ങളാണ് കാണുന്നത്? (ഉദാ: ഇല മഞ്ഞളിക്കൽ, വാട്ടം, പുള്ളികൾ)",
            "mr": "{crop_name} वर आपल्याला कोणती लक्षणे दिसत आहेत? (उदा: पाने पिवळी पडणे, चट्टे, करपा)",
            "en": "What specific symptoms are visible on your {crop_name}? (e.g. yellowing leaves, leaf curling, spots, or wilting)",
        }
    }
}

def get_slot_prompt(workflow: str, slot: str, language: str, context: Optional[Dict[str, Any]] = None) -> str:
    wf = SLOT_PROMPTS.get(workflow, {})
    slot_dict = wf.get(slot, {})
    prompt_template = slot_dict.get(language) or slot_dict.get("en", "Please provide more details.")
    if context:
        return prompt_template.format(**context)
    return prompt_template


def get_agronomic_domain_response(query: str, language: str = "en") -> Optional[str]:
    """
    Provides authoritative, practical agricultural domain knowledge fallback
    when live AI (Gemini) is unconfigured or unavailable.
    """
    q = query.lower()
    lang = language[:2].lower() if language else "en"
    if lang not in ["te", "en", "hi", "ta", "kn", "ml", "mr"]:
        lang = "en"

    is_chilli = any(w in q for w in ["chilli", "chili", "mirchi", "మిర్చి", "मिर्च", "மிளகாய்", "ಮೆಣಸಿನಕಾಯಿ", "മുളക്", "मिरची"])
    is_cotton = any(w in q for w in ["cotton", "patti", "పత్తి", "कपास", "பருத்தி", "ಹತ್ತಿ", "പരുത്തി", "कापूस"])
    is_paddy = any(w in q for w in ["paddy", "rice", "వరి", "ధాన్యం", "धान", "चावल", "நெல்", "அரிசி", "ಭತ್ತ", "നെല്ല്", "भात"])

    is_harvesting = any(w in q for w in [
        "harvest", "harvesting", "when to harvest", "how to harvest", "picking", "sun drying",
        "post-harvest", "plucking", "dry chilli", "drying", "drying chilli",
        "కోత", "కోయడం", "కొయ్యాలి", "కోత కోయడం", "తీత", "తీయడం", "ఎండబెట్టడం", "ఆరబెట్టడం",
        "कटाई", "तोड़ाई", "चुनाई", "तुड़ाई", "काटना", "सुखाना",
        "அறுவடை", "பறித்தல்", "உலர்த்துதல்",
        "ಕೊಯ್ಲು", "ಕಟಾವು", "ಕಿಳುವುದು", "ಒಣಗಿಸುವುದು",
        "വിളവെടുപ്പ്", "പറിക്കൽ", "ഉണക്കൽ",
        "कापणी", "तोडणी", "सुकवणे"
    ])

    # 1. Chilli Harvesting & Post-Harvest Drying
    if is_chilli and is_harvesting:
        if lang == "te":
            return (
                "మిర్చి పంట కోత మరియు ఆరబెట్టే యాజమాన్య పద్ధతులు (Chilli Harvesting & Post-Harvest Guide):\n\n"
                "1. కోత సమయం & పరిపక్వత లక్షణాలు:\n"
                "• ఎండుమిర్చి కోసం: కాయలు పూర్తిగా ముదురు ఎరుపు రంగులోకి మారి గట్టిపడినప్పుడు మాత్రమే కోయాలి. పచ్చి లేదా పాక్షిక ఎరుపు కాయలను విడిగా ఉంచండి.\n"
                "• పచ్చిమిర్చి కోసం: కాయలు పూర్తి పరిమాణానికి వచ్చి ముదురు ఆకుపచ్చ రంగులో ఉన్నప్పుడు కోయాలి.\n\n"
                "2. కోతల వ్యవధి & పద్ధతి:\n"
                "• ప్రతి 10 నుండి 15 రోజుల వ్యవధిలో విడతల వారీగా కోత కోయాలి.\n"
                "• ఒక పైరులో సాధారణంగా 4 నుండి 6 కోతలు వస్తాయి.\n"
                "• కాయలను తొడిమతో సహా జాగ్రత్తగా తుంచాలి. కొమ్మలను లేదా పూతను లాగి విరవకూడదు.\n\n"
                "3. కోత కోసే సరైన సమయం:\n"
                "• ఉదయం పూట ఆకులపై మంచు ఆరిపోయిన తర్వాత మాత్రమే కోత మొదలుపెట్టాలి. తడి ఉన్నప్పుడు కోస్తే కాయలు కుళ్ళిపోయే ప్రమాదం ఉంది.\n\n"
                "4. ఎండబెట్టడం & అఫ్లాటాక్సిన్ నివారణ:\n"
                "• ప్రాథమిక శుద్ధి: రంగు మారిన, తెగులు సోకిన లేదా పురుగు పట్టిన కాయలను కోసిన వెంటనే వేరు చేయండి.\n"
                "• టార్పాలిన్లపై ఆరబెట్టడం: శుభ్రమైన ప్లాస్టిక్ టార్పాలిన్లు లేదా సిమెంట్ కళ్లాలపై కాయలను పలుచగా పరచి ఎండబెట్టాలి. ఎట్టిపరిస్థితుల్లోనూ దుమ్ము ధూళి ఉన్న మట్టి నేలపై ఎండబెట్టకూడదు.\n"
                "• తేమ శాతం: 10-14 రోజుల పాటు ఎండలో ఆరబెట్టి, తేమ శాతాన్ని 10-11% కి తగ్గించాలి (కాయను కదిపితే విత్తనాలు గలగల శబ్దం రావాలి). ఇది అఫ్లాటాక్సిన్ బూజు రాకుండా కాపాడుతుంది మరియు మంచి ఎరుపు రంగును నిలుపుతుంది.\n\n"
                "5. నిల్వ:\n"
                "• పూర్తిగా ఎండిన కాయలను శుభ్రమైన గోనె సంచులలో నింపి, నేలకు తగలకుండా చెక్క పలకలపై గాలి ఆడే పొడి గదిలో భద్రపరచండి."
            )
        elif lang == "hi":
            return (
                "मिर्च की तुड़ाई एवं सुखाने की उन्नत विधियां (Chilli Harvesting & Post-Harvest Guide):\n\n"
                "1. परिपक्वता के लक्षण:\n"
                "• सूखी लाल मिर्च: जब मिर्च पूरी तरह गहरी लाल और सख्त हो जाए, तभी तुड़ाई करें। आधी पकी या हरी मिर्च को अलग रखें।\n"
                "• हरी मिर्च: जब मिर्च पूर्ण आकार की और गहरे हरे रंग की हो जाए, तब तोड़ें।\n\n"
                "2. तुड़ाई का अंतराल एवं तरीका:\n"
                "• प्रत्येक 10 से 15 दिनों के अंतराल पर तुड़ाई करें। एक फसल में औसतन 4 से 6 तुड़ाई की जाती हैं।\n"
                "• मिर्च को डंठल सहित सावधानीपूर्वक तोड़ें। शाखाओं और फूलों को नुकसान न पहुंचाएं।\n\n"
                "3. तुड़ाई का सही समय:\n"
                "• सुबह ओस सूखने के बाद ही तुड़ाई करें। गीली अवस्था में तुड़ाई करने से फफूंद और सड़न का खतरा बढ़ जाता है।\n\n"
                "4. सुखाना एवं एफ्लाटॉक्सिन से बचाव:\n"
                "• छंटाई: कटी-फटी, रोगग्रस्त या दाग वाली मिर्च को तुरंत अलग कर लें।\n"
                "• तिरपाल पर सुखाना: साफ पॉलीथिन तिरपाल या पक्के फर्श पर मिर्च को पतली परत में फैलाकर सुखाएं। मिट्टी पर कभी न सुखाएं।\n"
                "• नमी स्तर: 10-14 दिनों तक धूप में सुखाकर नमी 10-11% तक लाएं (हिलाने पर बीज खड़कने लगें)। इससे एफ्लाटॉक्सिन फफूंद नहीं लगती और गहरा लाल रंग बना रहता है।\n\n"
                "5. सुरक्षित भंडारण:\n"
                "• सूखी मिर्च को साफ बोरियों में भरकर लकड़ी के तख्तों पर रखें, ताकि जमीन की नमी न लगे।"
            )
        elif lang == "ta":
            return (
                "மிளகாய் அறுவடை மற்றும் உலர்த்தும் மேலாண்மை (Chilli Harvesting Guide):\n\n"
                "1. முதிர்ச்சி அறிகுறிகள்: காய்ந்த மிளகாய்க்கு முழு சிவப்பு நிறமாக மாறி கடினமாகும் போது அறுவடை செய்யவும்.\n"
                "2. பறிக்கும் இடைவெளி: 10-15 நாட்கள் இடைவெளியில் 4-6 முறை காம்புடன் கவனமாக பறிக்கவும்.\n"
                "3. பறிக்கும் நேரம்: காலையில் பனி உலர்ந்த பிறகு பறிக்கவும்.\n"
                "4. உலர்த்துதல்: சுத்தமான தார்பாலினில் மெல்லிய அடுக்காக பரப்பி, ஈரப்பதம் 10-11% குறையும் வரை 10-14 நாட்கள் காயவைக்கவும். மணல் தரையில் உலர்த்த வேண்டாம்.\n"
                "5. சேமிப்பு: உலர்ந்த மிளகாயை ஈரப்பதமில்லாத இடத்தில் மரப்பலகை மீது சாக்குகளில் சேமிக்கவும்."
            )
        elif lang == "kn":
            return (
                "ಮೆಣಸಿನಕಾಯಿ ಕೊಯ್ಲು ಮತ್ತು ಒಣಗಿಸುವ ನಿರ್ವಹಣೆ (Chilli Harvesting Guide):\n\n"
                "1. ಕೊಯ್ಲಿನ ಹಂತ: ಒಣ ಮೆಣಸಿನಕಾಯಿಗೆ ಕಾಯಿಗಳು ಸಂಪೂರ್ಣ ಗಾಢ ಕೆಂಪು ಬಣ್ಣಕ್ಕೆ ತಿರುಗಿ ಗಟ್ಟಿಯಾದಾಗ ಕೊಯ್ಲು ಮಾಡಿ.\n"
                "2. ಕೊಯ್ಲಿನ ಅಂತರ: ಪ್ರತಿ 10-15 ದಿನಗಳಿಗೊಮ್ಮೆ ತೊಟ್ಟಿನೊಂದಿಗೆ ಕೀಳಿರಿ (ಒಟ್ಟು 4-6 ಕಟಾವು).\n"
                "3. ಸಮಯ: ಬೆಳಗಿನ ಮಂಜು ಒಣಗಿದ ನಂತರ ಕೊಯ್ಲು ಆರಂಭಿಸಿ.\n"
                "4. ಒಣಗಿಸುವುದು: ಸ್ವಚ್ಛವಾದ ಟಾರ್ಪಾಲಿನ್ ಮೇಲೆ ತೆಳುವಾಗಿ ಹರಡಿ 10-14 ದಿನ ಒಣಗಿಸಿ ತೇವಾಂಶ 10-11% ಗೆ ಇಳಿಸಿ. ಮಣ್ಣಿನಲ್ಲಿ ಒಣಗಿಸಬೇಡಿ.\n"
                "5. ಸಂಗ್ರಹಣೆ: ಒಣಗಿದ ಕಾಯಿಗಳನ್ನು ಗೋಣಿಚೀಲಗಳಲ್ಲಿ ತುಂಬಿ ತೇವಾಂಶವಿಲ್ಲದ ಕೊಠಡಿಯಲ್ಲಿ ಸಂಗ್ರಹಿಸಿ."
            )
        elif lang == "ml":
            return (
                "മുളക് വിളവെടുപ്പും ഉണക്കൽ രീതികളും (Chilli Harvesting Guide):\n\n"
                "1. പാകം: വറ്റൽമുളകിനായി കായ്കൾ പൂർണ്ണമായി ചുവപ്പ് നിറമാകുമ്പോൾ മാത്രം പറിക്കുക.\n"
                "2. ഇടവേള: 10-15 ദിവസത്തെ ഇടവേളകളിൽ 4-6 തവണ വിളവെടുക്കുക.\n"
                "3. സമയം: രാവിലെ മഞ്ഞുമാറിയ ശേഷം മാത്രം വിളവെടുക്കുക.\n"
                "4. ഉണക്കൽ: വൃത്തിയുള്ള ടാർപോളിനിൽ നിരത്തി ഈർപ്പം 10-11% ആകുന്നത് വരെ ഉണക്കുക. മണ്ണിലിട്ട് ഉണക്കരുത്.\n"
                "5. സൂക്ഷിപ്പ്: ഉണങ്ങിയ മുളക് ഈർപ്പമില്ലാത്ത സ്ഥലത്ത് മരപ്പലകകൾക്ക് മുകളിൽ സൂക്ഷിക്കുക."
            )
        elif lang == "mr":
            return (
                "मिरची तोडणी आणि वाळवण्याचे व्यवस्थापन (Chilli Harvesting Guide):\n\n"
                "1. परिपक्वता: वाळलेल्या लाल मिरचीसाठी मिरच्या पूर्णपणे लाल आणि कडक झाल्यावरच तोडाव्यात.\n"
                "2. कालावधी: दर 10 ते 15 दिवसांच्या अंतराने देठासह 4 ते 6 तोडण्या कराव्यात.\n"
                "3. वेळ: सकाळचे दव सुकल्यानंतरच तोडणी करावी.\n"
                "4. ताडपत्रीवर वाळवणे: स्वच्छ ताडपत्रीवर पातळ थरात वाळवून ओलावा 10-11% पर्यंत आणावा. मातीवर वाळवू नये.\n"
                "5. साठवणूक: स्वच्छ पोत्यात भरून कोरड्या जागी लाकडी फळ्यांवर साठवावे."
            )
        else:
            return (
                "Chilli Harvesting & Post-Harvest Drying Guide (మిర్చి కోత మరియు ఎండబెట్టే విధానం):\n\n"
                "1. Maturity Indicators:\n"
                "• Dry Red Chilli: Harvest when pods achieve a deep, uniform red colour and firm texture. Avoid mixing immature or semi-ripe green pods.\n"
                "• Green Chilli: Pick when fruits achieve maximum length and firm green skin, before any color transition starts.\n\n"
                "2. Picking Schedule & Intervals:\n"
                "• Perform pickings in regular flushes every 10 to 15 days.\n"
                "• A standard commercial crop yields 4 to 6 pickings over the season.\n"
                "• Harvest fruits along with their pedicel (stalk). Gently snap the stalk at the node; avoid tugging or tearing branches.\n\n"
                "3. Optimal Time of Day:\n"
                "• Pick strictly in the morning hours after the morning dew has fully dried off the canopy. Picking wet pods invites fungal decay and fruit rot.\n\n"
                "4. Post-Harvest Sun Drying & Aflatoxin Prevention:\n"
                "• Initial Sorting: Separate damaged, pest-punctured, or mouldy pods immediately after picking.\n"
                "• Clean Drying Surface: Spread the harvested pods in a thin, single layer on clean polyethylene tarpaulins or cemented yard floors. NEVER dry chillies directly on bare soil to prevent dust and fungal spores.\n"
                "• Target Moisture: Sun-dry for 10–14 days with regular gentle stirring until moisture drops to 10–11% (seeds inside should rattle cleanly). Proper drying prevents Aspergillus / aflatoxin contamination and preserves vibrant red pericarp colour.\n\n"
                "5. Safe Storage:\n"
                "• Pack fully dried chillies into clean gunny bags and store on wooden pallets in a cool, dry, well-ventilated space away from direct ground contact."
            )

    # 2. Cotton Picking & Handling
    if is_cotton and is_harvesting:
        if lang == "te":
            return (
                "పత్తి తీత మరియు నిల్వ యాజమాన్య పద్ధతులు (Cotton Picking Guide):\n\n"
                "1. తీత సమయం: పైరులో 50-60% కాయలు పూర్తిగా పగిలి తెల్లటి పత్తి విచ్చుకున్నప్పుడు మొదటి తీత మొదలుపెట్టాలి.\n"
                "2. సరైన సమయం: ఉదయం 9 గంటల తర్వాత మంచు ఆరిపోయిన తర్వాత మాత్రమే పత్తి తీయాలి. తడి పత్తి తీస్తే పసుపు రంగులోకి మారి బూజు పడుతుంది.\n"
                "3. శుభ్రత: ఎండిన ఆకులు, చెత్త లేదా ఎండు తొడిమలు పత్తిలో పడకుండా జాగ్రత్తగా తీయాలి.\n"
                "4. వర్గీకరణ: తెగులు సోకిన, రంగు మారిన లేదా గులాబీ రంగు పురుగు తిన్న పత్తిని మొదటి నాణ్యమైన పత్తితో కలపకుండా విడిగా ఉంచండి.\n"
                "5. నిల్వ: తీసిన పత్తిని నీడలో శుభ్రమైన టార్పాలిన్లపై 2-3 రోజులు ఆరబెట్టి, తేమ లేని పొడి గదిలో నిల్వ చేయండి."
            )
        elif lang == "hi":
            return (
                "कपास की चुनाई एवं रखरखाव के सुझाव (Cotton Picking Guide):\n\n"
                "1. चुनाई का समय: जब खेत में 50-60% टिंडे पूरी तरह खिल जाएं, तभी पहली चुनाई शुरू करें।\n"
                "2. सही समय: सुबह की ओस सूखने के बाद (सुबह 9 बजे के बाद) ही चुनाई करें। गीली कपास पीली पड़ जाती है।\n"
                "3. पत्तों से बचाव: सूखी पत्तियां, छिलके या खरपतवार कपास में न मिलने दें।\n"
                "4. छंटाई: कीटग्रस्त या दागदार कपास को उत्तम गुणवत्ता वाली सफेद कपास से अलग रखें।\n"
                "5. भंडारण: तोड़ी गई कपास को 2-3 दिन छायादार साफ फर्श पर सुखाएं और सूखे हवादार कमरे में रखें।"
            )
        else:
            return (
                "Cotton Picking & Handling Guidance (పత్తి తీత యాజమాన్యం):\n\n"
                "1. Picking Maturity: Begin the first picking only when 50–60% of bolls have fully burst open and the fluffy white lint is exposed.\n"
                "2. Time of Day: Pick cotton after 9:00 AM once morning dew has evaporated. Damp lint discolors to yellow and develops fungus during storage.\n"
                "3. Quality Picking: Pick clean, dry white bolls. Avoid pulling dried bracts, dry leaves, or weeds with the lint.\n"
                "4. Grading: Keep clean first-pick cotton strictly separate from pest-damaged (pink bollworm / stained) or stained second/third picks.\n"
                "5. Storage: Dry in the shade on clean tarpaulins for 2–3 days. Store in dry, well-ventilated gunny bags away from moisture."
            )

    # 3. Paddy Harvesting
    if is_paddy and is_harvesting:
        if lang == "te":
            return (
                "వరి కోత మరియు నూర్పిడి యాజమాన్య పద్ధతులు (Paddy Harvesting Guide):\n\n"
                "1. కోత సమయం: వెన్నుల్లోని 80-85% గింజలు బంగారు పసుపు రంగులోకి మారినప్పుడు కోత మొదలుపెట్టాలి.\n"
                "2. గింజ తేమ శాతం: కోత సమయంలో గింజల్లో తేమ 20-22% ఉండటం ఉత్తమం. ఆలస్యం చేస్తే గింజ రాలిపోవడం మరియు గింజలు విరగడం జరుగుతుంది.\n"
                "3. నూర్పిడి: కోసిన వెంటనే ఎక్కువ రోజులు కుప్ప వేయకుండా సమయానికి నూర్పిడి చేయండి.\n"
                "4. ఆరబెట్టడం & నిల్వ: నూర్చిన ధాన్యాన్ని శుభ్రమైన కళ్లాలపై ఆరబెట్టి తేమను 14% కి తగ్గించి భద్రపరచాలి."
            )
        else:
            return (
                "Paddy (Rice) Harvesting & Storage Guidance (వరి కోత యాజమాన్యం):\n\n"
                "1. Harvest Stage: Harvest when 80–85% of grains in the panicle have turned golden yellow.\n"
                "2. Moisture Level: Optimal grain moisture at harvest is 20–22%. Over-drying in the field leads to shattering losses and milling breakage.\n"
                "3. Threshing: Thresh promptly after harvest to avoid grain discoloration from moisture in stacked straw.\n"
                "4. Drying & Storage: Sun-dry clean grain on clean tarpaulins until moisture drops to 14% for safe storage."
            )

    # 4. General Harvesting Query
    if is_harvesting:
        if lang == "te":
            return (
                "సాధారణ పంటల కోత సూత్రాలు (Agronomic Harvesting Advice):\n\n"
                "1. పరిపక్వత సూచికలు: పంట నిర్దిష్ట పరిపక్వతకు వచ్చినప్పుడు మాత్రమే కోత చేపట్టండి.\n"
                "2. సమయం: ఉదయం మంచు ఆరిపోయిన తర్వాత ఎండలో కోయడం వల్ల బూజు తెగుళ్లు నివారించబడతాయి.\n"
                "3. ఎండబెట్టడం: ఎట్టిపరిస్థితుల్లోనూ మట్టి నేలపై కాకుండా శుభ్రమైన టార్పాలిన్లపై ఆరబెట్టండి.\n"
                "4. తేమ నియంత్రణ: నిల్వ చేసే ముందు సురక్షిత తేమ శాతానికి తీసుకురావడం అత్యంత ముఖ్యం.\n\n"
                "నిర్దిష్ట పంట వివరాల కోసం మీ పంట పేరును తెలపండి (ఉదా: మిర్చి కోత, పత్తి తీత, వరి కోత)."
            )
        else:
            return (
                "Agronomic Harvesting & Quality Preservation Principles:\n\n"
                "1. Maturity Timing: Harvest when crops reach standard physiological maturity (uniform color, proper moisture).\n"
                "2. Morning Timing: Harvest after morning canopy dew has dried to prevent mould contamination.\n"
                "3. Clean Drying: Always dry produce on clean plastic tarpaulins or cemented floors, never on bare dusty soil.\n"
                "4. Moisture Control: Bring produce down to safe storage moisture before bagging.\n\n"
                "For crop-specific guidance, please specify your crop (e.g., 'Chilli harvesting', 'Cotton picking', 'Paddy harvesting')."
            )

    return None

# ----------------- ASSISTANT ORCHESTRATOR -----------------

class AssistantOrchestrator:
    @staticmethod
    async def process_user_query(
        message: str,
        conversation_id: str,
        language: str = "en",
        farm_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        image_base64: Optional[str] = None
    ) -> ChatResponse:
        farm_ctx = farm_context or {}
        # Explicit farmer district (do not assume or claim Warangal if farmer never provided one)
        raw_dist = farm_ctx.get("district")
        msg_dist = extract_district(message)
        farmer_district = msg_dist or (raw_dist.strip() if raw_dist and raw_dist.strip() not in ["", "Warangal (Default)", "Default", "None"] else None)
        default_district = farmer_district
        default_state = farm_ctx.get("state") if farm_ctx.get("state") not in ["", "Default"] else None
        default_soil = farm_ctx.get("soil_type") if farm_ctx.get("soil_type") not in ["", "Default"] else None
        default_water = farm_ctx.get("water_source") if farm_ctx.get("water_source") not in ["", "Default"] else None

        # 1. Check for cancellation of ongoing workflow
        if is_cancel_intent(message):
            clear_conversation_session(conversation_id)
            cancellation_replies = {
                "te": "సరే, మీ మునుపటి అభ్యర్థనను రద్దు చేసాను. మీ వ్యవసాయంలో నేను ఇంకేమి సహాయం చేయగలను?",
                "hi": "ठीक है, मैंने पिछला अनुरोध रद्द कर दिया है। मैं आपकी खेती में और किस प्रकार मदद कर सकता हूँ?",
                "ta": "சரி, உங்கள் முந்தைய கோரிக்கையை ரத்து செய்துள்ளேன். உங்கள் விவசாயத்தில் வேறு எவ்வாறு உதவ முடியும்?",
                "kn": "ಸರಿ, ಹಿಂದಿನ ವಿನಂತಿಯನ್ನು ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ಕೃಷಿ ಸಂಬಂಧಿತ ಬೇರೆ ವಿಷಯದಲ್ಲಿ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
                "ml": "ശരി, മുൻ അഭ്യർത്ഥന റദ്ദാക്കി. കാർഷിക സംബന്ധമായ മറ്റ് എന്തെങ്കിലും സഹായം ആവശ്യമുണ്ടോ?",
                "mr": "ठीक आहे, मी मागील विनंती रद्द केली आहे. आपल्या शेतीसाठी मी आणखी कशी मदत करू शकतो?",
                "en": "Understood, I have cancelled that workflow. How else can I assist your farming today?"
            }
            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=cancellation_replies.get(language, cancellation_replies["en"]),
                language=language,
                intent="general",
                routed_feature=None,
                feature_data=None,
                suggested_actions=["Which crop suits black soil?", "Check chilli price"],
                audio_available=False,
                pending_workflow=None,
                collected_slots={}
            )

        if is_unsupported_forecast_request(message):
            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=UNSUPPORTED_FORECAST_REPLIES.get(language, UNSUPPORTED_FORECAST_REPLIES["en"]),
                language=language,
                intent="general",
                routed_feature="ask_kisan",
                feature_data=None,
                suggested_actions=["Which crop suits black soil?", "Check Chilli mandi prices"],
                audio_available=False,
                pending_workflow=None,
            )

        # 2. Check existing conversation session
        session = get_conversation_session(conversation_id)
        session_workflow = session.get("pending_workflow")
        collected_slots = session.get("collected_slots") or {}
        missing_slots = session.get("missing_slots") or []
        # Discard pending slot state from the retired forecast workflow.
        if session_workflow == "weather":
            clear_conversation_session(conversation_id)
            session_workflow = None
            collected_slots = {}
            missing_slots = []

        # A complete new market query is a new search, even if a previous
        # interrupted market flow is waiting for its commodity. Reset stale
        # location/commodity state so the explicit commodity in this message
        # drives the new search instead of being consumed as an old answer.
        if (
            session_workflow == "market_prices"
            and missing_slots
            and detect_intent(message) == "market_prices"
            and extract_commodity(message)
        ):
            clear_conversation_session(conversation_id)
            session_workflow = None
            collected_slots = {}
            missing_slots = []

        # A pending slot-fill flow must not consume a new, clearly different
        # farmer question as if it were the answer to the previous prompt.
        # Keep the conversation messages intact, but discard only the stale
        # workflow state before routing the new question normally.
        if session_workflow and missing_slots:
            newly_detected_intent = detect_intent(message)
            current_slot = missing_slots[0]
            slot_value_present = {
                "soil_type": extract_soil_type(message) is not None,
                "water_source": extract_water_source(message) is not None,
                "district": extract_district(message) is not None,
                "commodity": extract_commodity(message) is not None,
                "crop_name": extract_health_crop(message) is not None,
                "symptoms": newly_detected_intent == "crop_health",
            }.get(current_slot, False)
            if newly_detected_intent != "general" and not slot_value_present:
                clear_conversation_session(conversation_id)
                session_workflow = None
                collected_slots = {}
                missing_slots = []

        # ----------------- A. RESUME PENDING WORKFLOW -----------------
        if session_workflow and missing_slots:
            current_missing = missing_slots[0]

            # Try to extract the requested slot from the user's message
            if session_workflow == "market_prices":
                if current_missing == "commodity":
                    comm = extract_commodity(message) or message.strip().title()
                    collected_slots["commodity"] = comm
                    missing_slots.pop(0)
                elif current_missing == "district":
                    mandi = extract_mandi(message)
                    if mandi:
                        collected_slots["mandi"] = mandi
                    else:
                        dist = extract_district(message) or message.strip().title()
                        collected_slots["district"] = dist
                    missing_slots.pop(0)

            elif session_workflow == "crop_advisor":
                if current_missing == "district":
                    collected_slots["district"] = extract_district(message) or message.strip().title()
                    missing_slots.pop(0)
                elif current_missing == "soil_type":
                    soil = extract_soil_type(message) or (
                        "Black Cotton Soil" if "black" in message.lower() else "Red Sandy Loam"
                    )
                    collected_slots["soil_type"] = soil
                    missing_slots.pop(0)
                elif current_missing == "water_source":
                    water = extract_water_source(message) or (
                        "Good irrigation" if "good" in message.lower() or "bore" in message.lower() else "Rainfed / Dryland"
                    )
                    collected_slots["water_source"] = water
                    missing_slots.pop(0)

            elif session_workflow == "crop_health":
                if current_missing == "crop_name":
                    c_name = extract_health_crop(message) or message.strip().title()
                    collected_slots["crop_name"] = c_name
                    missing_slots.pop(0)
                elif current_missing == "symptoms":
                    collected_slots["symptoms"] = message.strip()
                    missing_slots.pop(0)
                if image_base64:
                    collected_slots["image_base64"] = image_base64

            # Check if there are still missing slots
            if missing_slots:
                next_missing = missing_slots[0]
                save_conversation_session(conversation_id, session_workflow, collected_slots, missing_slots)
                next_prompt = get_slot_prompt(session_workflow, next_missing, language, collected_slots)
                return ChatResponse(
                    conversation_id=conversation_id,
                    reply_text=next_prompt,
                    language=language,
                    intent=session_workflow,
                    routed_feature=session_workflow,
                    pending_workflow=session_workflow,
                    collected_slots=collected_slots,
                    next_slot=next_missing,
                    suggested_actions=["Cotton", "Chilli", "Paddy", "Tomato", "Cancel"] if session_workflow == "crop_health" else ["Cancel", "Good irrigation", "Rainfed"],
                    audio_available=False
                )
            else:
                # All slots collected! Finish workflow execution.
                clear_conversation_session(conversation_id)
                # Fall through to execution with collected_slots populated below.
                active_intent = session_workflow
        else:
            # Detect new intent (if an image is attached, treat it as crop health unless it is a market query)
            detected = detect_intent(message)
            if image_base64 and detected in ["general", "crop_health"]:
                active_intent = "crop_health"
            else:
                active_intent = detected

        # ----------------- B. EXECUTE OR INITIATE INTENT -----------------

        # 2. MARKET PRICES INTENT
        if active_intent == "market_prices":
            # Check what slots we already have
            comm = collected_slots.get("commodity") or extract_commodity(message)
            dist = collected_slots.get("district") or extract_district(message)
            requested_mandi = collected_slots.get("mandi") or extract_mandi(message)

            # If commodity is still missing, start slot collection
            if not comm:
                missing = ["commodity"] if dist else ["commodity", "district"]
                save_conversation_session(conversation_id, "market_prices", {"district": dist} if dist else {}, missing)
                prompt = get_slot_prompt("market_prices", "commodity", language)
                return ChatResponse(
                    conversation_id=conversation_id,
                    reply_text=prompt,
                    language=language,
                    intent="market_prices",
                    routed_feature="market_prices",
                    pending_workflow="market_prices",
                    collected_slots={"district": dist} if dist else {},
                    next_slot="commodity",
                    suggested_actions=["Chilli", "Cotton", "Tomato", "Paddy"],
                    audio_available=False
                )

            # If commodity is present but district is missing, ask for district
            if not dist and not requested_mandi:
                missing = ["district"]
                save_conversation_session(conversation_id, "market_prices", {"commodity": comm}, missing)
                prompt = get_slot_prompt("market_prices", "district", language, {"commodity": comm})
                return ChatResponse(
                    conversation_id=conversation_id,
                    reply_text=prompt,
                    language=language,
                    intent="market_prices",
                    routed_feature="market_prices",
                    pending_workflow="market_prices",
                    collected_slots={"commodity": comm},
                    next_slot="district",
                    suggested_actions=["Warangal", "Guntur", "Khammam", "Karimnagar"],
                    audio_available=False
                )

            # All required slots ready -> Execute market price discovery
            try:
                m_data = await MarketPriceService.get_market_prices(
                    commodity=comm,
                    district=dist if not requested_mandi else None,
                    mandi=requested_mandi,
                    state=default_state,
                    language=language,
                )
            except MarketProviderError as exc:
                feature_data = {"status": "unavailable", "code": exc.code, "message": exc.message}
                unavailable_messages = {
                    "en": f"Local illustrative {comm} references are available by district, but not for a specific mandi such as {requested_mandi or dist or 'that market'}. I will not invent or substitute a mandi price. Select a district reference in Market Prices.",
                    "te": f"స్థానిక ఉదాహరణ {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} సూచనలు జిల్లా వారీగా ఉన్నాయి; నిర్దిష్ట మండీకి కావు. మండీ ధరను కల్పించను లేదా ప్రత్యామ్నాయంగా చూపను. Market Pricesలో జిల్లా సూచనను ఎంచుకోండి.",
                    "hi": f"स्थानीय उदाहरण {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} संदर्भ जिला-आधारित हैं, किसी खास मंडी के नहीं। मैं मंडी भाव नहीं गढ़ूँगा या बदलूँगा। Market Prices में जिला संदर्भ चुनें।",
                    "ta": f"உள்ளூர் எடுத்துக்காட்டு {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} குறிப்புகள் மாவட்ட வாரியானவை; குறிப்பிட்ட சந்தைக்கானவை அல்ல. சந்தை விலையை உருவாக்கவோ மாற்றாகக் காட்டவோ மாட்டேன். Market Prices-ல் மாவட்டக் குறிப்பைத் தேர்ந்தெடுக்கவும்.",
                    "kn": f"ಸ್ಥಳೀಯ ಉದಾಹರಣೆಯ {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} ಉಲ್ಲೇಖಗಳು ಜಿಲ್ಲಾವಾರು ಮಾತ್ರ; ನಿರ್ದಿಷ್ಟ ಮಾರುಕಟ್ಟೆಗೆ ಅಲ್ಲ. ಮಾರುಕಟ್ಟೆ ದರವನ್ನು ಕಲ್ಪಿಸುವುದಿಲ್ಲ ಅಥವಾ ಬದಲಿಸುವುದಿಲ್ಲ. Market Prices ನಲ್ಲಿ ಜಿಲ್ಲಾ ಉಲ್ಲೇಖ ಆಯ್ಕೆಮಾಡಿ.",
                    "ml": f"പ്രാദേശിക ഉദാഹരണ {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} സൂചനകൾ ജില്ലാടിസ്ഥാനത്തിലുള്ളതാണ്; പ്രത്യേക വിപണിയുടേതല്ല. വിപണി വില കെട്ടിച്ചമയ്ക്കുകയോ പകരം കാണിക്കുകയോ ഇല്ല. Market Prices-ൽ ജില്ലാ സൂചന തിരഞ്ഞെടുക്കുക.",
                    "mr": f"स्थानिक उदाहरणार्थ {COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language, comm)} संदर्भ जिल्हानिहाय आहेत; विशिष्ट मंडीचे नाहीत. मी मंडीचा भाव बनवणार किंवा बदलणार नाही. Market Prices मध्ये जिल्हा संदर्भ निवडा.",
                }
                reply = unavailable_messages.get(language, unavailable_messages["en"])
            else:
                feature_data = m_data.model_dump()
                if m_data.records:
                    r0 = m_data.records[0]
                    reply = _market_record_reply(r0, language)
                else:
                    localized_commodity = COMMODITY_LOCALIZED_NAMES.get(comm, {}).get(language) or comm
                    requested_location = requested_mandi or dist or "the requested market"
                    no_match = {
                        "en": f"No local illustrative {localized_commodity} reference matches {requested_location}. No other district or market was substituted. Check the spelling or select another listed district.",
                        "te": f"{requested_location}కు స్థానిక ఉదాహరణ {localized_commodity} సూచన లేదు. వేరే జిల్లా లేదా మార్కెట్‌ను చూపలేదు. పేరును తనిఖీ చేయండి లేదా జాబితాలోని మరో జిల్లాను ఎంచుకోండి.",
                        "hi": f"{requested_location} के लिए स्थानीय उदाहरण {localized_commodity} संदर्भ नहीं मिला। कोई दूसरा जिला या बाजार नहीं दिखाया गया। नाम जांचें या सूची का दूसरा जिला चुनें।",
                        "ta": f"{requested_location}க்கு உள்ளூர் எடுத்துக்காட்டு {localized_commodity} குறிப்பு இல்லை. வேறு மாவட்டம் அல்லது சந்தை காட்டப்படவில்லை. பெயரைச் சரிபார்க்கவும் அல்லது பட்டியிலிருந்து வேறு மாவட்டத்தைத் தேர்ந்தெடுக்கவும்.",
                        "kn": f"{requested_location}ಗೆ ಸ್ಥಳೀಯ ಉದಾಹರಣೆಯ {localized_commodity} ಉಲ್ಲೇಖ ಸಿಗಲಿಲ್ಲ. ಬೇರೆ ಜಿಲ್ಲೆ ಅಥವಾ ಮಾರುಕಟ್ಟೆ ತೋರಿಸಿಲ್ಲ. ಹೆಸರನ್ನು ಪರಿಶೀಲಿಸಿ ಅಥವಾ ಪಟ್ಟಿಯ ಬೇರೆ ಜಿಲ್ಲೆಯನ್ನು ಆಯ್ಕೆಮಾಡಿ.",
                        "ml": f"{requested_location}യ്ക്ക് പ്രാദേശിക ഉദാഹരണ {localized_commodity} സൂചനയില്ല. മറ്റൊരു ജില്ലയോ വിപണിയോ കാണിച്ചിട്ടില്ല. പേര് പരിശോധിക്കുക അല്ലെങ്കിൽ പട്ടികയിലെ മറ്റൊരു ജില്ല തിരഞ്ഞെടുക്കുക.",
                        "mr": f"{requested_location} साठी स्थानिक उदाहरणार्थ {localized_commodity} संदर्भ नाही. दुसरा जिल्हा किंवा बाजार दाखवलेला नाही. नाव तपासा किंवा यादीतील दुसरा जिल्हा निवडा.",
                    }
                    reply = no_match.get(language, no_match["en"])

            clear_conversation_session(conversation_id)
            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=reply,
                language=language,
                intent="market_prices",
                routed_feature="market_prices",
                feature_data=feature_data,
                suggested_actions=[f"Check {comm} district reference", "Try another district"],
                audio_available=False,
                pending_workflow=None,
                collected_slots={"commodity": comm, **({"mandi": requested_mandi} if requested_mandi else {"district": dist})}
            )

        # 3. CROP ADVISOR INTENT
        elif active_intent == "crop_advisor":
            soil = collected_slots.get("soil_type") or extract_soil_type(message) or default_soil
            water = collected_slots.get("water_source") or extract_water_source(message) or default_water
            district = collected_slots.get("district") or farmer_district
            crop_slots = dict(collected_slots)
            if district:
                crop_slots["district"] = district
            if soil:
                crop_slots["soil_type"] = soil
            if water:
                crop_slots["water_source"] = water

            # Keep the crop workflow explicit and ordered. In particular, a
            # district answer belongs to this workflow and must never be
            # consumed by the market-price district/mandi slot.
            missing = [slot for slot, value in (
                ("district", district), ("soil_type", soil), ("water_source", water)
            ) if not value]
            if missing:
                next_slot = missing[0]
                save_conversation_session(conversation_id, "crop_advisor", crop_slots, missing)
                prompt = get_slot_prompt("crop_advisor", next_slot, language, crop_slots)
                suggested_actions = {
                    "district": ["Nellore", "Warangal", "Guntur"],
                    "soil_type": ["Black Cotton Soil", "Red Sandy Loam", "Alluvial Soil"],
                    "water_source": ["Good irrigation", "Moderate irrigation", "Rainfed / Dryland"],
                }[next_slot]
                return ChatResponse(
                    conversation_id=conversation_id,
                    reply_text=prompt,
                    language=language,
                    intent="crop_advisor",
                    routed_feature="crop_advisor",
                    pending_workflow="crop_advisor",
                    collected_slots=crop_slots,
                    next_slot=next_slot,
                    suggested_actions=suggested_actions,
                    audio_available=False
                )

            # All slots ready -> Execute Crop Advisor
            # Determine season: farmer-specified or confirmed > profile/context > current calendar season window
            def get_calendar_season() -> str:
                month = datetime.now().month
                if 6 <= month <= 10:
                    return "Kharif (Monsoon)"
                elif month in [11, 12, 1, 2]:
                    return "Rabi (Winter)"
                else:
                    return "Summer (Zaid)"

            extracted_season = extract_season(message)
            season = (
                collected_slots.get("growing_season")
                or extracted_season
                or (farm_ctx.get("growing_season") if farm_ctx else None)
                or get_calendar_season()
            )

            district_to_pass = district
            c_data = CropAdvisorService.get_recommendations(soil, water, season, district_to_pass, default_state)
            feature_data = c_data.model_dump()

            loc_context = f" in {farmer_district}" if farmer_district else ""

            if c_data.recommendations:
                top_crops = ", ".join([r.crop_name for r in c_data.recommendations])
                location_phrase = {
                    "te": f" {farmer_district} ప్రాంతంలో" if farmer_district else "",
                    "hi": f" {farmer_district} क्षेत्र में" if farmer_district else "",
                    "ta": f" {farmer_district} பகுதியில்" if farmer_district else "",
                    "kn": f" {farmer_district} ಜಿಲ್ಲೆಯಲ್ಲಿ" if farmer_district else "",
                    "ml": f" {farmer_district} പ്രദേശത്ത്" if farmer_district else "",
                    "mr": f" {farmer_district} परिसरात" if farmer_district else "",
                    "en": f" in {farmer_district}" if farmer_district else "",
                }
                place = location_phrase.get(language, location_phrase["en"])
                reply_templates = {
                    "te": f"మీ{place} {soil}, {water} నీటి పరిస్థితి, {season} కాలాన్ని బట్టి {top_crops} పంటలను పరిశీలించవచ్చు. ఇవి మీ పొలానికి ధృవీకరించిన సిఫార్సులు కావు. విత్తే సమయం, నేలలోని తేమ, విత్తనాల లభ్యతను స్థానిక KVK లేదా వ్యవసాయ అధికారితో నిర్ధారించండి. కావాలంటే ఈ పంటలను పోల్చి చెప్పగలను.",
                    "hi": f"आपके{place} {soil}, {water} की स्थिति और {season} मौसम के लिए {top_crops} पर विचार किया जा सकता है। ये आपके खेत के लिए सत्यापित सिफारिशें नहीं हैं। बुवाई का समय, मिट्टी की नमी और बीज की उपलब्धता स्थानीय KVK या कृषि अधिकारी से जाँचें। चाहें तो मैं इन विकल्पों की तुलना कर सकता हूँ।",
                    "ta": f"உங்கள்{place} {soil}, {water} நீர் நிலை, {season} பருவத்தைப் பொறுத்து {top_crops} பயிர்களைப் பரிசீலிக்கலாம். இவை உங்கள் நிலத்திற்குச் சரிபார்க்கப்பட்ட பரிந்துரைகள் அல்ல. விதைப்பு நேரம், மண்ணின் ஈரப்பதம், விதை கிடைப்பதை உள்ளூர் KVK அல்லது வேளாண் அலுவலரிடம் உறுதிப்படுத்துங்கள். விரும்பினால் இவற்றை ஒப்பிட்டுச் சொல்லலாம்.",
                    "kn": f"ನಿಮ್ಮ{place} {soil}, {water} ನೀರಿನ ಸ್ಥಿತಿ ಮತ್ತು {season} ಹಂಗಾಮಿಗೆ {top_crops} ಬೆಳೆಗಳನ್ನು ಪರಿಗಣಿಸಬಹುದು. ಇವು ನಿಮ್ಮ ಹೊಲಕ್ಕೆ ಪರಿಶೀಲಿತ ಶಿಫಾರಸುಗಳಲ್ಲ. ಬಿತ್ತನೆ ಸಮಯ, ಮಣ್ಣಿನ ತೇವಾಂಶ ಮತ್ತು ಬೀಜ ಲಭ್ಯತೆಯನ್ನು ಸ್ಥಳೀಯ KVK ಅಥವಾ ಕೃಷಿ ಅಧಿಕಾರಿಯಿಂದ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ. ಬೇಕಿದ್ದರೆ ಈ ಆಯ್ಕೆಗಳನ್ನು ಹೋಲಿಸಿ ಹೇಳುತ್ತೇನೆ.",
                    "ml": f"നിങ്ങളുടെ{place} {soil}, {water} ജലലഭ്യത, {season} കാലം എന്നിവ കണക്കിലെടുത്ത് {top_crops} പരിഗണിക്കാം. ഇവ നിങ്ങളുടെ വയലിനായി സ്ഥിരീകരിച്ച ശുപാർശകളല്ല. വിതയ്ക്കുന്ന സമയം, മണ്ണിലെ ഈർപ്പം, വിത്തിന്റെ ലഭ്യത എന്നിവ പ്രാദേശിക KVK അല്ലെങ്കിൽ കൃഷി ഉദ്യോഗസ്ഥനുമായി ഉറപ്പാക്കുക. വേണമെങ്കിൽ ഇവ താരതമ്യം ചെയ്ത് പറയാം.",
                    "mr": f"तुमच्या{place} {soil}, {water} पाण्याची उपलब्धता आणि {season} हंगामासाठी {top_crops} विचारात घेता येतील. या तुमच्या शेतासाठी पडताळलेल्या शिफारसी नाहीत. पेरणीची वेळ, जमिनीतील ओलावा आणि बियाण्यांची उपलब्धता स्थानिक KVK किंवा कृषी अधिकाऱ्यांकडून तपासा. हवे असल्यास मी या पर्यायांची तुलना करू शकतो.",
                    "en": f"For {soil}{place}, with {water.lower()} during {season}, {top_crops} are options to compare. These are general suggestions, not verified for your field. Check sowing time, remaining soil moisture and seed availability with your local KVK or agriculture officer. I can help compare these options if you’d like.",
                }
                reply = reply_templates.get(language, reply_templates["en"])
            else:
                # Honest localized empty state while source documents are being verified.
                unavailable_crop = {
                    "te": f"{soil} నేల, {water} నీటి సదుపాయం, {season} కాలానికి ధృవీకరించిన ప్రాంతీయ పంట సిఫార్సులు ప్రస్తుతం అందుబాటులో లేవు. ఆధారాలు లేని పంట సూచనలు ఇవ్వము. నేల పరీక్ష ఫలితాలతో మీ స్థానిక KVK లేదా వ్యవసాయ అధికారిని సంప్రదించండి.",
                    "hi": f"{soil}, {water} और {season} के लिए सत्यापित क्षेत्रीय फसल सिफारिशें उपलब्ध नहीं हैं। बिना प्रमाण के फसल नहीं सुझाएँगे। मिट्टी की जाँच के नतीजों के साथ स्थानीय KVK या कृषि अधिकारी से सलाह लें।",
                    "ta": f"{soil}, {water}, {season} ஆகியவற்றுக்கு சரிபார்க்கப்பட்ட பிராந்திய பயிர் பரிந்துரைகள் இல்லை. ஆதாரமற்ற ஆலோசனை வழங்கமாட்டோம். மண் பரிசோதனை முடிவுகளுடன் உள்ளூர் KVK-ஐ அணுகவும்.",
                    "kn": f"{soil}, {water}, {season} ಗಾಗಿ ಪರಿಶೀಲಿಸಿದ ಪ್ರಾದೇಶಿಕ ಬೆಳೆ ಶಿಫಾರಸುಗಳು ಲಭ್ಯವಿಲ್ಲ. ಆಧಾರವಿಲ್ಲದ ಸಲಹೆ ನೀಡುವುದಿಲ್ಲ. ಮಣ್ಣಿನ ಪರೀಕ್ಷಾ ಫಲಿತಾಂಶಗಳೊಂದಿಗೆ ಸ್ಥಳೀಯ KVK ಸಂಪರ್ಕಿಸಿ.",
                    "ml": f"{soil}, {water}, {season} എന്നിവയ്ക്ക് പരിശോധിച്ച പ്രാദേശിക വിള ശുപാർശകൾ ലഭ്യമല്ല. തെളിവില്ലാത്ത നിർദ്ദേശങ്ങൾ നൽകില്ല. മണ്ണ് പരിശോധനാ ഫലങ്ങളുമായി പ്രാദേശിക KVK-യെ സമീപിക്കുക.",
                    "mr": f"{soil}, {water}, {season} साठी पडताळलेल्या प्रादेशिक पीक शिफारसी उपलब्ध नाहीत. पुराव्याशिवाय पीक सुचवणार नाही. माती परीक्षणासह स्थानिक KVK चा सल्ला घ्या.",
                    "en": f"Verified crop recommendations are unavailable for {soil} with {water} during {season}{loc_context}. Kisan Hita will not guess crop suitability. Please consult your local Krishi Vigyan Kendra (KVK) or Mandal Agriculture Officer with your soil-test results.",
                }
                reply = unavailable_crop.get(language, unavailable_crop["en"])

            clear_conversation_session(conversation_id)
            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=reply,
                language=language,
                intent="crop_advisor",
                routed_feature="crop_advisor",
                feature_data=feature_data,
                suggested_actions=["Open CHOOSE CROP Module", "Check Market Price"],
                audio_available=False,
                pending_workflow=None,
                collected_slots={"district": district, "soil_type": soil, "water_source": water, "growing_season": season}
            )

        # 4. CROP HEALTH INTENT
        elif active_intent == "crop_health":
            c_name = collected_slots.get("crop_name") or extract_health_crop(message)
            symptoms = collected_slots.get("symptoms") or (message if message.strip().title() != c_name else "")
            if not symptoms and c_name:
                symptoms = f"Reported distress on {c_name}"

            # If crop name is missing, ask for crop
            if not c_name:
                missing = ["crop_name"]
                slots_to_save = {"symptoms": symptoms}
                active_img = image_base64 or collected_slots.get("image_base64")
                if active_img:
                    slots_to_save["image_base64"] = active_img
                save_conversation_session(conversation_id, "crop_health", slots_to_save, missing)
                prompt = get_slot_prompt("crop_health", "crop_name", language)
                return ChatResponse(
                    conversation_id=conversation_id,
                    reply_text=prompt,
                    language=language,
                    intent="crop_health",
                    routed_feature="crop_health",
                    pending_workflow="crop_health",
                    collected_slots=slots_to_save,
                    next_slot="crop_name",
                    suggested_actions=["Cotton", "Chilli", "Paddy", "Tomato", "Cancel"],
                    audio_available=False
                )

            # Collect context from farmer without inventing defaults
            active_img = image_base64 or collected_slots.get("image_base64")
            onset = collected_slots.get("onset_days") or (farm_ctx.get("onset_days") if farm_ctx else None)
            spread = collected_slots.get("affected_spread") or (farm_ctx.get("affected_spread") if farm_ctx else None)

            # Execute asynchronous crop health evaluation with verified image if provided
            h_data = await CropHealthService.evaluate_crop_health_async(
                crop_name=c_name,
                symptoms=symptoms or "Visible plant distress",
                onset_days=onset,
                affected_spread=spread,
                image_base64=active_img,
                language=language
            )
            feature_data = h_data.model_dump()

            # Without a photo, ask Gemini for contextual text guidance, never
            # for visual observations. Retain the deterministic assessment as
            # a safe fallback and as the source of structured feature data.
            reply = format_assistant_crop_health_reply(h_data, language)
            if not active_img:
                context_query = (
                    f"The farmer is growing {c_name}. Their question/report was: {symptoms or 'general pest information'}. "
                    "Answer the actual question with practical, general crop information. If they asked about pests, name the common important pests for this crop and describe distinguishing signs and where to inspect. "
                    "Do not claim any pest is present or that you saw the field. Give inspection guidance, then ask one focused question about what they observe. Do not request a photo unless it would materially help."
                )
                contextual_reply = None
                if GeminiAIService.is_configured():
                    contextual_reply = await GeminiAIService.generate_agricultural_response(
                        query=context_query,
                        language=language,
                        farm_context=farm_context,
                        conversation_history=conversation_history,
                    )
                if (contextual_reply and response_matches_language_script(contextual_reply, language)
                        and not _looks_like_diagnostic_template_response(contextual_reply)):
                    reply = contextual_reply
                else:
                    reply = _cotton_pest_information_fallback(symptoms, language) or reply

            clear_conversation_session(conversation_id)
            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=reply,
                language=language,
                intent="crop_health",
                routed_feature="crop_health",
                feature_data=feature_data,
                suggested_actions=["Open CHECK CROP Module", "Contact KVK (1800-180-1551)"],
                audio_available=False,
                pending_workflow=None,
                collected_slots={"crop_name": c_name, "symptoms": symptoms}
            )

        # 5. GENERAL INQUIRY / AI ASSISTANT REASONING
        else:
            routed_feature = "ask_kisan"
            cotton_pest_education = _is_cotton_pest_education(message)
            assistant_query = message
            if cotton_pest_education:
                assistant_query = (
                    f"Farmer asks for general education: {message}\n"
                    "Explain common cotton pests (aphids, jassids, whiteflies, thrips and bollworms), the typical damage each causes, "
                    "how and where to inspect, distinguishing signs, and practical non-chemical monitoring/prevention. "
                    "Answer conversationally with useful guidance first and one natural follow-up question. This is not a field diagnosis: "
                    "do not ask for onset, affected area or a photograph, do not output a diagnostic report template, and do not claim any pest is present."
                )

            # Attempt authentic Google Gemini AI generation if configured
            gemini_reply = await GeminiAIService.generate_agricultural_response(
                query=assistant_query,
                language=language,
                farm_context=farm_context,
                conversation_history=conversation_history
            )

            if (gemini_reply and response_matches_language_script(gemini_reply, language)
                    and not (cotton_pest_education and _looks_like_diagnostic_template_response(gemini_reply))):
                reply = gemini_reply
            else:
                if gemini_reply:
                    logger.warning(
                        "Discarding assistant response whose script does not match requested language %s",
                        language,
                    )
                if cotton_pest_education:
                    reply = _cotton_pest_education_fallback(language)
                else:
                    agronomic_reply = get_agronomic_domain_response(message, language)
                    if agronomic_reply and response_matches_language_script(agronomic_reply, language):
                        reply = agronomic_reply
                    else:
                        reply = _localized_unavailable_reply(language)

            m_lower = message.lower()
            if any(w in m_lower for w in ["chilli", "chili", "mirchi", "మిర్చి", "मिर्च"]):
                sug_actions = ["Check Chilli Mandi Price", "Chilli Leaf Curl & Pests"]
            elif any(w in m_lower for w in ["cotton", "patti", "పత్తి", "कपास"]):
                sug_actions = ["Check Cotton Mandi Price", "Cotton Pest Management"]
            elif any(w in m_lower for w in ["paddy", "rice", "వరి", "धान"]):
                sug_actions = ["Check Paddy Mandi Price", "Paddy Storage Advice"]
            else:
                sug_actions = ["Which crop suits black soil?", "Check Chilli mandi prices", "My leaves are turning yellow"]

            return ChatResponse(
                conversation_id=conversation_id,
                reply_text=reply,
                language=language,
                intent="general",
                routed_feature=routed_feature,
                feature_data=None,
                suggested_actions=sug_actions,
                audio_available=False,
                pending_workflow=None,
                collected_slots={}
            )

"""app/i18n.py – minimal English/Hindi labels for the main shell (hero, tabs, sidebar).

Inner pages and AI answers stay in English; this only covers top-level labels.
  t(key, lang) -> str    (falls back to English)
"""

STRINGS = {
    "en": {
        "tag": "The money coach that stops UPI scams, budgets from your bank SMS — and <b>never says a number it can't prove</b>.",
        "chip1": "🚨 Scam check in seconds", "chip2": "🆘 Scammed? Golden-hour plan",
        "chip3": "💰 Budget from SMS", "chip4": "🎯 Goals &amp; tax", "chip5": "🔒 Works offline · data stays with you",
        "tab_scam": "🛡️ Scam Shield", "tab_budget": "💰 Smart Budget", "tab_goals": "🎯 Goals & Tax",
        "tab_chat": "💬 Ask Artha", "tab_about": "📖 About",
        "status": "⚙️ System status", "privacy": "🔒 Your privacy", "demo": "🎬 Demo story",
        "clear": "🗑️ Clear all my data", "lang": "Language / भाषा",
        "disclaimer": "⚖️ Educational tool. Not financial advice.",
    },
    "hi": {
        "tag": "आपका मनी कोच — UPI स्कैम रोकता है, बैंक SMS से बजट बनाता है, और <b>कभी ऐसा आँकड़ा नहीं बताता जो साबित न हो सके</b>।",
        "chip1": "🚨 सेकंडों में स्कैम जाँच", "chip2": "🆘 ठगे गए? गोल्डन-आवर प्लान",
        "chip3": "💰 SMS से बजट", "chip4": "🎯 लक्ष्य और टैक्स", "chip5": "🔒 ऑफ़लाइन भी चलता है · डेटा आपके पास",
        "tab_scam": "🛡️ स्कैम शील्ड", "tab_budget": "💰 स्मार्ट बजट", "tab_goals": "🎯 लक्ष्य और टैक्स",
        "tab_chat": "💬 अर्थ से पूछें", "tab_about": "📖 जानकारी",
        "status": "⚙️ सिस्टम स्थिति", "privacy": "🔒 आपकी गोपनीयता", "demo": "🎬 डेमो कहानी",
        "clear": "🗑️ मेरा सारा डेटा मिटाएँ", "lang": "Language / भाषा",
        "disclaimer": "⚖️ शैक्षिक टूल। वित्तीय सलाह नहीं।",
    },
}


def t(key: str, lang: str = "en") -> str:
    return STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"][key]

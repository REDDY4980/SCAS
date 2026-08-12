/// Supported UI languages.
enum AppLanguage { en, kn, hi, te }

extension AppLanguageX on AppLanguage {
  String get code => switch (this) {
        AppLanguage.en => 'en',
        AppLanguage.kn => 'kn',
        AppLanguage.hi => 'hi',
        AppLanguage.te => 'te',
      };

  /// Name shown in-language (matches reference design's language picker).
  String get nativeName => switch (this) {
        AppLanguage.en => 'English',
        AppLanguage.kn => 'ಕನ್ನಡ',
        AppLanguage.hi => 'हिंदी',
        AppLanguage.te => 'తెలుగు',
      };

  static AppLanguage fromCode(String? code) {
    return AppLanguage.values.firstWhere((l) => l.code == code, orElse: () => AppLanguage.en);
  }
}

/// App-wide UI translation dictionary.
///
/// Covers static UI chrome (buttons, labels, headers, form fields)
/// across every screen. Does NOT cover AI-generated content (crop
/// recommendation explanations, fertilizer reasoning) — that text is
/// generated live by the backend in English; translating it would
/// require backend changes and is out of scope here. Screens that show
/// AI-generated text display a small note when the UI language isn't
/// English, so this boundary is never silently confusing to a user.
///
/// Translations are a best-effort AI translation, not yet reviewed by a
/// native speaker — recommend review before real farmer-facing use,
/// especially for agricultural/technical terms.
class AppStrings {
  final AppLanguage language;
  const AppStrings(this.language);

  static const Map<String, Map<String, String>> _dict = {
    // Splash
    'appTagline': {
      'en': 'AI-Powered Insights for Smarter Farming',
      'kn': 'ಸ್ಮಾರ್ಟ್ ಕೃಷಿಗಾಗಿ AI ಆಧಾರಿತ ಒಳನೋಟಗಳು',
      'hi': 'स्मार्ट खेती के लिए AI-संचालित जानकारी',
      'te': 'తెలివైన వ్యవసాయం కోసం AI ఆధారిత అంతర్దృష్టులు',
    },
    'getStarted': {'en': 'Get Started', 'kn': 'ಪ್ರಾರಂಭಿಸಿ', 'hi': 'शुरू करें', 'te': 'ప్రారంభించండి'},

    // Login
    'login': {'en': 'Login', 'kn': 'ಲಾಗಿನ್', 'hi': 'लॉगिन', 'te': 'లాగిన్'},
    'welcomeBack': {'en': 'Welcome Back', 'kn': 'ಮತ್ತೆ ಸ್ವಾಗತ', 'hi': 'वापसी पर स्वागत है', 'te': 'తిరిగి స్వాగతం'},
    'loginSubtitle': {
      'en': 'Login to manage your farm and advisories',
      'kn': 'ನಿಮ್ಮ ಫಾರ್ಮ್ ಮತ್ತು ಸಲಹೆಗಳನ್ನು ನಿರ್ವಹಿಸಲು ಲಾಗಿನ್ ಮಾಡಿ',
      'hi': 'अपने खेत और सलाह प्रबंधित करने के लिए लॉगिन करें',
      'te': 'మీ వ్యవసాయ క్షేత్రం మరియు సలహాలను నిర్వహించడానికి లాగిన్ చేయండి',
    },
    'emailOrMobile': {
      'en': 'Email or Mobile Number',
      'kn': 'ಇಮೇಲ್ ಅಥವಾ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ',
      'hi': 'ईमेल या मोबाइल नंबर',
      'te': 'ఇమెయిల్ లేదా మొబైల్ నంబర్',
    },
    'password': {'en': 'Password', 'kn': 'ಪಾಸ್‌ವರ್ಡ್', 'hi': 'पासवर्ड', 'te': 'పాస్‌వర్డ్'},
    'forgotPassword': {
      'en': 'Forgot Password?',
      'kn': 'ಪಾಸ್‌ವರ್ಡ್ ಮರೆತಿರಾ?',
      'hi': 'पासवर्ड भूल गए?',
      'te': 'పాస్‌వర్డ్ మర్చిపోయారా?',
    },
    'createAccount': {'en': 'Create Account', 'kn': 'ಖಾತೆ ರಚಿಸಿ', 'hi': 'खाता बनाएं', 'te': 'ఖాతా సృష్టించండి'},
    'signUp': {'en': 'Sign Up', 'kn': 'ಸೈನ್ ಅಪ್', 'hi': 'साइन अप करें', 'te': 'సైన్ అప్'},

    // Register
    'joinTitle': {'en': 'Join SCAS', 'kn': 'SCAS ಸೇರಿ', 'hi': 'SCAS से जुड़ें', 'te': 'SCASలో చేరండి'},
    'joinSubtitle': {
      'en': 'Create an account to get AI-powered farming advice',
      'kn': 'AI ಆಧಾರಿತ ಕೃಷಿ ಸಲಹೆ ಪಡೆಯಲು ಖಾತೆ ರಚಿಸಿ',
      'hi': 'AI-संचालित खेती सलाह पाने के लिए खाता बनाएं',
      'te': 'AI ఆధారిత వ్యవసాయ సలహా పొందడానికి ఖాతా సృష్టించండి',
    },
    'fullName': {'en': 'Full Name', 'kn': 'ಪೂರ್ಣ ಹೆಸರು', 'hi': 'पूरा नाम', 'te': 'పూర్తి పేరు'},
    'email': {'en': 'Email', 'kn': 'ಇಮೇಲ್', 'hi': 'ईमेल', 'te': 'ఇమెయిల్'},
    'phoneNumber': {'en': 'Phone Number', 'kn': 'ಫೋನ್ ಸಂಖ್ಯೆ', 'hi': 'फ़ोन नंबर', 'te': 'ఫోన్ నంబర్'},
    'passwordHelper': {
      'en': 'At least 8 characters, with a letter and a number',
      'kn': 'ಕನಿಷ್ಠ 8 ಅಕ್ಷರಗಳು, ಒಂದು ಅಕ್ಷರ ಮತ್ತು ಒಂದು ಸಂಖ್ಯೆಯೊಂದಿಗೆ',
      'hi': 'कम से कम 8 अक्षर, एक अक्षर और एक संख्या के साथ',
      'te': 'కనీసం 8 అక్షరాలు, ఒక అక్షరం మరియు ఒక సంఖ్యతో',
    },

    // Dashboard
    'goodMorning': {'en': 'Good Morning', 'kn': 'ಶುಭೋದಯ', 'hi': 'सुप्रभात', 'te': 'శుభోదయం'},
    'goodAfternoon': {'en': 'Good Afternoon', 'kn': 'ಶುಭ ಮಧ್ಯಾಹ್ನ', 'hi': 'शुभ दोपहर', 'te': 'శుభ మధ్యాహ్నం'},
    'goodEvening': {'en': 'Good Evening', 'kn': 'ಶುಭ ಸಂಜೆ', 'hi': 'शुभ संध्या', 'te': 'శుభ సాయంత్రం'},
    'quickActions': {'en': 'Quick Actions', 'kn': 'ತ್ವರಿತ ಕ್ರಿಯೆಗಳು', 'hi': 'त्वरित कार्य', 'te': 'త్వరిత చర్యలు'},
    'farmOverview': {'en': 'Farm Overview', 'kn': 'ಫಾರ್ಮ್ ಅವಲೋಕನ', 'hi': 'खेत का अवलोकन', 'te': 'వ్యవసాయ క్షేత్రం సమీక్ష'},
    'soilTest': {'en': 'Soil Test', 'kn': 'ಮಣ್ಣಿನ ಪರೀಕ್ಷೆ', 'hi': 'मिट्टी परीक्षण', 'te': 'నేల పరీక్ష'},
    'crops': {'en': 'Crops', 'kn': 'ಬೆಳೆಗಳು', 'hi': 'फसलें', 'te': 'పంటలు'},
    'fertilizer': {'en': 'Fertilizer', 'kn': 'ರಸಗೊಬ್ಬರ', 'hi': 'उर्वरक', 'te': 'ఎరువు'},
    'diseaseScan': {'en': 'Disease Scan', 'kn': 'ರೋಗ ಸ್ಕ್ಯಾನ್', 'hi': 'रोग स्कैन', 'te': 'వ్యాధి స్కాన్'},
    'market': {'en': 'Market', 'kn': 'ಮಾರುಕಟ್ಟೆ', 'hi': 'बाज़ार', 'te': 'మార్కెట్'},
    'weather': {'en': 'Weather', 'kn': 'ಹವಾಮಾನ', 'hi': 'मौसम', 'te': 'వాతావరణం'},
    'aiAdvisor': {'en': 'AI Advisor', 'kn': 'AI ಸಲಹೆಗಾರ', 'hi': 'AI सलाहकार', 'te': 'AI సలహాదారు'},
    'history': {'en': 'History', 'kn': 'ಇತಿಹಾಸ', 'hi': 'इतिहास', 'te': 'చరిత్ర'},
    'home': {'en': 'home', 'kn': 'ಮುಖಪುಟ', 'hi': 'होम', 'te': 'హోమ్'},
    'analyzeSoilReport': {
      'en': 'Analyze Soil Report',
      'kn': 'ಮಣ್ಣಿನ ವರದಿ ವಿಶ್ಲೇಷಿಸಿ',
      'hi': 'मिट्टी रिपोर्ट का विश्लेषण करें',
      'te': 'నేల నివేదికను విశ్లేషించండి',
    },
    'viewDetails': {'en': 'View Details', 'kn': 'ವಿವರಗಳನ್ನು ನೋಡಿ', 'hi': 'विवरण देखें', 'te': 'వివరాలు చూడండి'},
    'addFarm': {'en': 'Add a farm', 'kn': 'ಫಾರ್ಮ್ ಸೇರಿಸಿ', 'hi': 'खेत जोड़ें', 'te': 'వ్యవసాయ క్షేత్రం జోడించండి'},
    'noFarmsYet': {
      'en': 'No farms yet. Add your first farm to get started.',
      'kn': 'ಇನ್ನೂ ಯಾವುದೇ ಫಾರ್ಮ್ ಇಲ್ಲ. ಪ್ರಾರಂಭಿಸಲು ನಿಮ್ಮ ಮೊದಲ ಫಾರ್ಮ್ ಸೇರಿಸಿ.',
      'hi': 'अभी तक कोई खेत नहीं है। शुरू करने के लिए अपना पहला खेत जोड़ें।',
      'te': 'ఇంకా వ్యవసాయ క్షేత్రాలు లేవు. ప్రారంభించడానికి మీ మొదటి క్షేత్రాన్ని జోడించండి.',
    },
    'aiConfidence': {'en': 'AI Confidence', 'kn': 'AI ವಿಶ್ವಾಸ', 'hi': 'AI विश्वास', 'te': 'AI నమ్మకం'},
    'land': {'en': 'Land', 'kn': 'ಭೂಮಿ', 'hi': 'भूमि', 'te': 'భూమి'},
    'noAnalysisYet': {
      'en': 'No analysis yet',
      'kn': 'ಇನ್ನೂ ವಿಶ್ಲೇಷಣೆ ಇಲ್ಲ',
      'hi': 'अभी तक कोई विश्लेषण नहीं',
      'te': 'ఇంకా విశ్లేషణ లేదు',
    },
    'uploadFirstRecommendation': {
      'en': 'Upload a soil report to get your first AI recommendation.',
      'kn': 'ನಿಮ್ಮ ಮೊದಲ AI ಶಿಫಾರಸು ಪಡೆಯಲು ಮಣ್ಣಿನ ವರದಿಯನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ.',
      'hi': 'अपनी पहली AI सिफारिश पाने के लिए मिट्टी की रिपोर्ट अपलोड करें।',
      'te': 'మీ మొదటి AI సిఫార్సు పొందడానికి నేల నివేదికను అప్‌లోడ్ చేయండి.',
    },
    'aiTextEnglishNote': {
      'en': '',
      'kn': 'AI ವಿವರಣೆ ಪ್ರಸ್ತುತ ಇಂಗ್ಲಿಷ್‌ನಲ್ಲಿ ಮಾತ್ರ ಲಭ್ಯವಿದೆ.',
      'hi': 'AI विवरण फ़िलहाल केवल अंग्रेज़ी में उपलब्ध है।',
      'te': 'AI వివరణ ప్రస్తుతం ఆంగ్లంలో మాత్రమే అందుబాటులో ఉంది.',
    },

    // Upload
    'soilAnalysisOcr': {
      'en': 'Soil Analysis OCR',
      'kn': 'ಮಣ್ಣಿನ ವಿಶ್ಲೇಷಣೆ OCR',
      'hi': 'मिट्टी विश्लेषण OCR',
      'te': 'నేల విశ్లేషణ OCR',
    },
    'tapOrDrag': {
      'en': 'Tap or Drag Soil Report Here',
      'kn': 'ಮಣ್ಣಿನ ವರದಿಯನ್ನು ಇಲ್ಲಿ ಟ್ಯಾಪ್ ಮಾಡಿ ಅಥವಾ ಎಳೆಯಿರಿ',
      'hi': 'यहां मिट्टी रिपोर्ट टैप करें या खींचें',
      'te': 'నేల నివేదికను ఇక్కడ నొక్కండి లేదా లాగండి',
    },
    'uploadOptions': {'en': 'Upload Options', 'kn': 'ಅಪ್‌ಲೋಡ್ ಆಯ್ಕೆಗಳು', 'hi': 'अपलोड विकल्प', 'te': 'అప్‌లోడ్ ఎంపికలు'},
    'pdfDocument': {'en': 'PDF\nDocument', 'kn': 'PDF\nಡಾಕ್ಯುಮೆಂಟ್', 'hi': 'PDF\nदस्तावेज़', 'te': 'PDF\nపత్రం'},
    'photoGallery': {'en': 'Photo\nGallery', 'kn': 'ಫೋಟೋ\nಗ್ಯಾಲರಿ', 'hi': 'फ़ोटो\nगैलरी', 'te': 'ఫోటో\nగ్యాలరీ'},
    'cameraCapture': {'en': 'Camera\nCapture', 'kn': 'ಕ್ಯಾಮೆರಾ\nಸೆರೆಹಿಡಿಯಿರಿ', 'hi': 'कैमरा\nकैप्चर', 'te': 'కెమెరా\nక్యాప్చర్'},

    // Profile drawer
    'farmerProfile': {'en': 'Farmer Profile', 'kn': 'ರೈತ ಪ್ರೊಫೈಲ್', 'hi': 'किसान प्रोफ़ाइल', 'te': 'రైతు ప్రొఫైల్'},
    'logout': {'en': 'Logout', 'kn': 'ಲಾಗ್ ಔಟ್', 'hi': 'लॉग आउट', 'te': 'లాగ్ అవుట్'},
    'comingSoon': {'en': '(soon)', 'kn': '(ಶೀಘ್ರದಲ್ಲಿ)', 'hi': '(जल्द ही)', 'te': '(త్వరలో)'},

    // AI Analysis / soil results
    'extractedHealthStatus': {
      'en': 'Extracted Health Status',
      'kn': 'ಹೊರತೆಗೆದ ಆರೋಗ್ಯ ಸ್ಥಿತಿ',
      'hi': 'निकाली गई स्वास्थ्य स्थिति',
      'te': 'సేకరించిన ఆరోగ్య స్థితి',
    },
    'nutrientValues': {
      'en': 'Nutrient Values (NPK & pH)',
      'kn': 'ಪೋಷಕಾಂಶ ಮೌಲ್ಯಗಳು (NPK ಮತ್ತು pH)',
      'hi': 'पोषक तत्व मान (NPK और pH)',
      'te': 'పోషక విలువలు (NPK & pH)',
    },
    'fertilizerGuide': {'en': 'Fertilizer Guide', 'kn': 'ರಸಗೊಬ್ಬರ ಮಾರ್ಗದರ್ಶಿ', 'hi': 'उर्वरक गाइड', 'te': 'ఎరువు గైడ్'},
    'recommendedCrops': {
      'en': 'Recommended Crops',
      'kn': 'ಶಿಫಾರಸು ಮಾಡಿದ ಬೆಳೆಗಳು',
      'hi': 'अनुशंसित फसलें',
      'te': 'సిఫార్సు చేసిన పంటలు',
    },
    'analyzingYourSoil': {
      'en': 'Analyzing Your Soil',
      'kn': 'ನಿಮ್ಮ ಮಣ್ಣನ್ನು ವಿಶ್ಲೇಷಿಸಲಾಗುತ್ತಿದೆ',
      'hi': 'आपकी मिट्टी का विश्लेषण हो रहा है',
      'te': 'మీ నేలను విశ్లేషిస్తోంది',
    },
    'saveAndContinue': {
      'en': 'Save and Continue',
      'kn': 'ಉಳಿಸಿ ಮತ್ತು ಮುಂದುವರಿಸಿ',
      'hi': 'सहेजें और जारी रखें',
      'te': 'సేవ్ చేసి కొనసాగించండి',
    },
  };

  String t(String key) => _dict[key]?[language.code] ?? _dict[key]?['en'] ?? key;
}

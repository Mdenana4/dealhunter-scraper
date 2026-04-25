class AppConstants {
  // Backend API — update to your deployed URL
  static const String apiBaseUrl = 'https://dealhunter-scraper.onrender.com';

  // Membership tier IDs
  static const String tierFree    = 'free';
  static const String tierBasic   = 'basic';
  static const String tierPremium = 'premium';
  static const String tierVip     = 'vip';

  // Tier prices (EGP/month)
  static const Map<String, double> tierMonthlyPrice = {
    'free':    0,
    'basic':   49,
    'premium': 99,
    'vip':     199,
  };

  // Daily notification limits per tier
  static const Map<String, int> tierDailyNotifications = {
    'free':    10,
    'basic':   50,
    'premium': 200,
    'vip':     999999,
  };

  // Price history days per tier
  static const Map<String, int> tierHistoryDays = {
    'free':    30,
    'basic':   60,
    'premium': 180,
    'vip':     3650, // ~10 years = "lifetime"
  };

  // Max saved deals per tier
  static const Map<String, int> tierSavedDeals = {
    'free':    10,
    'basic':   50,
    'premium': 999999,
    'vip':     999999,
  };

  // Minimum discount % to show in Deals tab
  static const double minDiscountPct = 40.0;

  // Verification confidence thresholds
  static const int confidenceGenuine   = 70;
  static const int confidenceUncertain = 50;

  // Supported marketplaces
  static const List<String> marketplaces = [
    'amazon_eg', 'amazon_ae', 'amazon_sa',
    'noon_eg',   'noon_ae',   'noon_sa',
    'jumia_eg',
  ];

  // Display names for marketplaces
  static const Map<String, String> marketplaceNames = {
    'amazon_eg': 'Amazon Egypt',
    'amazon_ae': 'Amazon UAE',
    'amazon_sa': 'Amazon KSA',
    'noon_eg':   'Noon Egypt',
    'noon_ae':   'Noon UAE',
    'noon_sa':   'Noon KSA',
    'jumia_eg':  'Jumia Egypt',
  };

  // Marketplace logo asset paths
  static const Map<String, String> marketplaceLogos = {
    'amazon_eg': 'assets/icons/amazon.png',
    'amazon_ae': 'assets/icons/amazon.png',
    'amazon_sa': 'assets/icons/amazon.png',
    'noon_eg':   'assets/icons/noon.png',
    'noon_ae':   'assets/icons/noon.png',
    'noon_sa':   'assets/icons/noon.png',
    'jumia_eg':  'assets/icons/jumia.png',
  };

  // Currency per marketplace
  static const Map<String, String> marketplaceCurrency = {
    'amazon_eg': 'EGP',
    'amazon_ae': 'AED',
    'amazon_sa': 'SAR',
    'noon_eg':   'EGP',
    'noon_ae':   'AED',
    'noon_sa':   'SAR',
    'jumia_eg':  'EGP',
  };

  // FCM Topics
  static const String fcmTopicDeals   = 'deals';
  static const String fcmTopicAdmin   = 'admin_alerts';

  // Quiet hours (notifications suppressed)
  static const int quietHourStart = 23; // 11 PM
  static const int quietHourEnd   = 7;  // 7 AM

  // Supported locales
  static const List<String> supportedLocales = ['en', 'ar'];
}

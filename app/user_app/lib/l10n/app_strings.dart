import 'package:flutter/material.dart';
import '../providers/app_providers.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class S {
  static const Map<String, Map<String, String>> _t = {
    'en': {
      // Bottom nav
      'nav_deals': 'Deals',
      'nav_search': 'Search',
      'nav_saved': 'Saved',
      'nav_membership': 'Membership',
      'nav_settings': 'Settings',

      // Country filter
      'country_all': 'All Countries',
      'country_eg': '🇪🇬 Egypt',
      'country_ae': '🇦🇪 UAE',
      'country_sa': '🇸🇦 Saudi Arabia',

      // Source filter
      'source_all': 'All Stores',
      'source_amazon': '📦 Amazon',
      'source_noon': '🟡 Noon',
      'source_jumia': '🛒 Jumia',

      // Categories — all 23 agreed categories
      'cat_all': 'All',
      'cat_electronics': 'Electronics',
      'cat_smartphones': 'Phones',
      'cat_laptops': 'Laptops',
      'cat_headphones': 'Headphones',
      'cat_tvs': 'TVs',
      'cat_cameras': 'Cameras',
      'cat_gaming': 'Gaming',
      'cat_mens_fashion': "Men's Fashion",
      'cat_womens_fashion': "Women's Fashion",
      'cat_shoes': 'Shoes',
      'cat_watches': 'Watches',
      'cat_bags': 'Bags',
      'cat_home_kitchen': 'Home & Kitchen',
      'cat_furniture': 'Furniture',
      'cat_beauty': 'Beauty',
      'cat_skincare': 'Skincare',
      'cat_perfume': 'Perfume',
      'cat_sports': 'Sports',
      'cat_baby': 'Baby',
      'cat_books': 'Books',
      'cat_automotive': 'Automotive',
      'cat_pets': 'Pets',
      'cat_grocery': 'Grocery',

      // Deals screen
      'no_deals': 'No deals found',
      'refresh': 'Refresh',
      'retry': 'Retry',

      // Search screen
      'search_hint': 'Search deals…',
      'search_premium_title': 'Search is a Premium feature',
      'search_premium_body': 'Upgrade to Basic or higher to search across all stores.',
      'upgrade_now': 'Upgrade Now',
      'type_to_search': 'Type to search',
      'no_results': 'No results for',

      // Saved screen
      'saved_title': 'Saved',
      'tab_deals': 'Deals',
      'tab_alerts': 'Alerts',
      'no_saved': 'No saved deals yet',
      'no_saved_hint': 'Tap the bookmark icon on any deal to save it.',
      'removed_from_saved': 'Removed from saved',

      // Alerts screen
      'no_alerts': 'No price alerts',
      'no_alerts_hint': 'Open any deal and tap "Set Alert"\nto get notified when the price drops.',
      'failed_alerts': 'Failed to load alerts',
      'remove_alert': 'Remove alert?',
      'remove_alert_body': 'You will no longer receive notifications for this price drop.',
      'cancel': 'Cancel',
      'remove': 'Remove',
      'alert_target': 'Alert when price ≤',
      'alert_pct': 'Alert on ≥',
      'alert_pct_suffix': '% price drop',
      'any_price_drop': 'Any price drop',
      'set_on': 'Set on',
      'last_triggered': 'Last triggered:',

      // Settings screen
      'settings_title': 'Settings',
      'region_language': 'Region & Language',
      'country': 'Country',
      'language': 'Language',
      'select_language': 'Select Language',
      'select_country': 'Select Country',
      'lang_en': 'English',
      'lang_ar': 'العربية',
      'notifications_section': 'Notifications',
      'price_drop_alerts': 'Price drop alerts',
      'price_drop_subtitle': 'Get notified when deals drop in price',
      'referral_section': 'Referral',
      'your_referral_code': 'Your referral code',
      'enter_referral': 'Enter referral code',
      'apply': 'Apply',
      'about_section': 'About',
      'version': 'Version',
      'sign_out': 'Sign Out',
      'sign_out_confirm': 'Are you sure you want to sign out?',
      'code_copied': 'Code copied',
      'lang_changed_en': 'Language changed to English',
      'lang_changed_ar': 'تم تغيير اللغة إلى العربية',

      // Membership screen
      'membership_title': 'Membership',
      'current_plan': 'Current Plan',
      'monthly': 'Monthly',
      'six_months': '6 Months',
      'yearly': 'Yearly',
      'save_10': 'Save 10% vs monthly',
      'save_25': 'Save 25% vs monthly',
      'upgrade_to': 'Upgrade to',
      'current_plan_btn': 'Current Plan',
      'downgrade': 'Downgrade',
      'popular': 'Popular',
      'free_plan_includes': 'Free Plan includes:',
      'free_feat_1': 'Browse all deals',
      'free_feat_2': '30-day price history',
      'free_feat_3': 'Save up to 10 deals',
      'free_feat_4': 'Basic fraud detection',
      'active_since': 'Active since',
      'payment_coming': 'Payment coming soon.\nWe will notify you when payment is enabled.',
      'ok': 'OK',

      // Deal detail
      'open_store': 'Open in Store',
      'set_alert': 'Set Alert',
      'save_deal': 'Save',
      'unsave_deal': 'Saved',
      'price_history': 'Price History',
      'verdict_genuine': 'Genuine Deal',
      'verdict_fake': 'Fake Discount',
      'verdict_suspicious': 'Suspicious',
      'verdict_unverified': 'Unverified',
      'loading': 'Loading…',
    },
    'ar': {
      // Bottom nav
      'nav_deals': 'العروض',
      'nav_search': 'بحث',
      'nav_saved': 'المحفوظات',
      'nav_membership': 'الاشتراك',
      'nav_settings': 'الإعدادات',

      // Country filter
      'country_all': 'كل الدول',
      'country_eg': '🇪🇬 مصر',
      'country_ae': '🇦🇪 الإمارات',
      'country_sa': '🇸🇦 السعودية',

      // Source filter
      'source_all': 'كل المتاجر',
      'source_amazon': '📦 أمازون',
      'source_noon': '🟡 نون',
      'source_jumia': '🛒 جوميا',

      // Categories — all 23 agreed categories
      'cat_all': 'الكل',
      'cat_electronics': 'إلكترونيات',
      'cat_smartphones': 'هواتف',
      'cat_laptops': 'لابتوب',
      'cat_headphones': 'سماعات',
      'cat_tvs': 'تلفزيونات',
      'cat_cameras': 'كاميرات',
      'cat_gaming': 'ألعاب فيديو',
      'cat_mens_fashion': 'أزياء رجالي',
      'cat_womens_fashion': 'أزياء نسائي',
      'cat_shoes': 'أحذية',
      'cat_watches': 'ساعات',
      'cat_bags': 'حقائب',
      'cat_home_kitchen': 'منزل ومطبخ',
      'cat_furniture': 'أثاث',
      'cat_beauty': 'الجمال',
      'cat_skincare': 'العناية بالبشرة',
      'cat_perfume': 'عطور',
      'cat_sports': 'رياضة',
      'cat_baby': 'أطفال',
      'cat_books': 'كتب',
      'cat_automotive': 'سيارات',
      'cat_pets': 'حيوانات أليفة',
      'cat_grocery': 'بقالة',

      // Deals screen
      'no_deals': 'لا توجد عروض',
      'refresh': 'تحديث',
      'retry': 'إعادة المحاولة',

      // Search screen
      'search_hint': 'ابحث عن العروض...',
      'search_premium_title': 'البحث ميزة مدفوعة',
      'search_premium_body': 'قم بالترقية إلى Basic أو أعلى للبحث في جميع المتاجر.',
      'upgrade_now': 'ترقية الآن',
      'type_to_search': 'اكتب للبحث',
      'no_results': 'لا توجد نتائج لـ',

      // Saved screen
      'saved_title': 'المحفوظات',
      'tab_deals': 'العروض',
      'tab_alerts': 'التنبيهات',
      'no_saved': 'لا توجد عروض محفوظة',
      'no_saved_hint': 'اضغط على أيقونة الإشارة المرجعية لحفظ العرض.',
      'removed_from_saved': 'تمت الإزالة من المحفوظات',

      // Alerts screen
      'no_alerts': 'لا توجد تنبيهات أسعار',
      'no_alerts_hint': 'افتح أي عرض واضغط على "تعيين تنبيه"\nلتلقي إشعار عند انخفاض السعر.',
      'failed_alerts': 'فشل تحميل التنبيهات',
      'remove_alert': 'إزالة التنبيه؟',
      'remove_alert_body': 'لن تتلقى بعد الآن إشعارات لهذا الانخفاض.',
      'cancel': 'إلغاء',
      'remove': 'إزالة',
      'alert_target': 'تنبيه عند السعر ≤',
      'alert_pct': 'تنبيه عند انخفاض',
      'alert_pct_suffix': '% من السعر',
      'any_price_drop': 'أي انخفاض في السعر',
      'set_on': 'تم الضبط في',
      'last_triggered': 'آخر تفعيل:',

      // Settings screen
      'settings_title': 'الإعدادات',
      'region_language': 'المنطقة واللغة',
      'country': 'البلد',
      'language': 'اللغة',
      'select_language': 'اختر اللغة',
      'select_country': 'اختر البلد',
      'lang_en': 'English',
      'lang_ar': 'العربية',
      'notifications_section': 'الإشعارات',
      'price_drop_alerts': 'تنبيهات انخفاض السعر',
      'price_drop_subtitle': 'احصل على إشعار عند انخفاض أسعار العروض',
      'referral_section': 'الإحالة',
      'your_referral_code': 'كود الإحالة الخاص بك',
      'enter_referral': 'أدخل كود الإحالة',
      'apply': 'تطبيق',
      'about_section': 'حول التطبيق',
      'version': 'الإصدار',
      'sign_out': 'تسجيل الخروج',
      'sign_out_confirm': 'هل أنت متأكد أنك تريد تسجيل الخروج؟',
      'code_copied': 'تم نسخ الكود',
      'lang_changed_en': 'Language changed to English',
      'lang_changed_ar': 'تم تغيير اللغة إلى العربية',

      // Membership screen
      'membership_title': 'الاشتراك',
      'current_plan': 'الخطة الحالية',
      'monthly': 'شهري',
      'six_months': '6 أشهر',
      'yearly': 'سنوي',
      'save_10': 'وفّر 10% مقارنة بالشهري',
      'save_25': 'وفّر 25% مقارنة بالشهري',
      'upgrade_to': 'الترقية إلى',
      'current_plan_btn': 'خطتك الحالية',
      'downgrade': 'تخفيض الخطة',
      'popular': 'الأكثر شيوعاً',
      'free_plan_includes': 'الخطة المجانية تشمل:',
      'free_feat_1': 'تصفح جميع العروض',
      'free_feat_2': 'سجل الأسعار لمدة 30 يومًا',
      'free_feat_3': 'حفظ حتى 10 عروض',
      'free_feat_4': 'كشف الاحتيال الأساسي',
      'active_since': 'نشط منذ',
      'payment_coming': 'الدفع قريباً.\nسنعلمك عند تفعيل خيارات الدفع.',
      'ok': 'حسناً',

      // Deal detail
      'open_store': 'فتح في المتجر',
      'set_alert': 'تعيين تنبيه',
      'save_deal': 'حفظ',
      'unsave_deal': 'محفوظ',
      'price_history': 'سجل الأسعار',
      'verdict_genuine': 'خصم حقيقي',
      'verdict_fake': 'خصم وهمي',
      'verdict_suspicious': 'مشبوه',
      'verdict_unverified': 'غير مُتحقق',
      'loading': 'جار التحميل...',
    },
  };

  static String of(BuildContext context, String key) {
    final lang = Localizations.localeOf(context).languageCode;
    return _t[lang]?[key] ?? _t['en']?[key] ?? key;
  }
}

// Convenience extension
extension SContext on BuildContext {
  String s(String key) => S.of(this, key);
}

// Riverpod version (use when BuildContext isn't available)
String sRef(WidgetRef ref, String key) {
  final lang = ref.watch(localeProvider).languageCode;
  return S._t[lang]?[key] ?? S._t['en']?[key] ?? key;
}

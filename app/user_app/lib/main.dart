import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'config/router.dart';
import 'providers/app_providers.dart';

// Must be a top-level function — called when the app is in background/terminated.
@pragma('vm:entry-point')
Future<void> _backgroundMessageHandler(RemoteMessage _) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_backgroundMessageHandler);
  final prefs = await SharedPreferences.getInstance();
  final langCode = prefs.getString('language') ?? 'en';
  runApp(ProviderScope(
    overrides: [
      localeProvider.overrideWith((ref) => Locale(langCode)),
    ],
    child: const DealHunterApp(),
  ));
}

class DealHunterApp extends ConsumerStatefulWidget {
  const DealHunterApp({super.key});

  @override
  ConsumerState<DealHunterApp> createState() => _DealHunterAppState();
}

class _DealHunterAppState extends ConsumerState<DealHunterApp> {
  @override
  void initState() {
    super.initState();
    _initFCM();
  }

  Future<void> _initFCM() async {
    final messaging = FirebaseMessaging.instance;

    // Save token on refresh
    messaging.onTokenRefresh.listen(_saveFcmToken);

    // Try to get initial token (may be null if not granted yet)
    final token = await messaging.getToken();
    if (token != null) await _saveFcmToken(token);

    // App launched from a notification (cold start)
    final initial = await messaging.getInitialMessage();
    if (initial != null) _openDeal(initial);

    // App brought to foreground from notification
    FirebaseMessaging.onMessageOpenedApp.listen(_openDeal);

    // Foreground notification — show in-app banner
    FirebaseMessaging.onMessage.listen(_showInAppBanner);
  }

  Future<void> _saveFcmToken(String token) async {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) return;
    await FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .set({'fcm_token': token}, SetOptions(merge: true));
  }

  void _openDeal(RemoteMessage message) {
    final dealId = message.data['deal_id'] as String?;
    if (dealId != null) appRouter.go('/home/deal/$dealId');
  }

  void _showInAppBanner(RemoteMessage message) {
    final n = message.notification;
    if (n == null) return;
    final ctx = appRouter.routerDelegate.navigatorKey.currentContext;
    if (ctx == null) return;
    ScaffoldMessenger.of(ctx).showSnackBar(
      SnackBar(
        content: Text('${n.title ?? 'Deal Alert'}: ${n.body ?? ''}'),
        action: SnackBarAction(
          label: 'View',
          onPressed: () {
            final dealId = message.data['deal_id'] as String?;
            if (dealId != null) appRouter.go('/home/deal/$dealId');
          },
        ),
        duration: const Duration(seconds: 5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final locale = ref.watch(localeProvider);
    return MaterialApp.router(
      title: 'DealHunter',
      debugShowCheckedModeBanner: false,
      locale: locale,
      supportedLocales: const [Locale('en'), Locale('ar')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0A0F),
      ),
      themeMode: ThemeMode.dark,
      darkTheme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0A0F),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFF6B00),
          secondary: Color(0xFF6C00FF),
          surface: Color(0xFF141420),
          background: Color(0xFF0A0A0F),
          onPrimary: Colors.white,
          onSecondary: Colors.white,
          onSurface: Colors.white,
          onBackground: Colors.white,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF0A0A0F),
          elevation: 0,
          iconTheme: IconThemeData(color: Colors.white),
          titleTextStyle: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
        ),
        cardTheme: CardTheme(
          color: const Color(0xFF141420),
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: Color(0xFF0A0A0F),
          selectedItemColor: Color(0xFFFF6B00),
          unselectedItemColor: Color(0x66FFFFFF),
        ),
      ),
      routerConfig: appRouter,
    );
  }
}

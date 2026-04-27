import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'config/router.dart';

// Must be a top-level function — called when the app is in background/terminated.
@pragma('vm:entry-point')
Future<void> _backgroundMessageHandler(RemoteMessage _) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_backgroundMessageHandler);
  runApp(const ProviderScope(child: DealHunterApp()));
}

class DealHunterApp extends StatefulWidget {
  const DealHunterApp({super.key});

  @override
  State<DealHunterApp> createState() => _DealHunterAppState();
}

class _DealHunterAppState extends State<DealHunterApp> {
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
    return MaterialApp.router(
      title: 'DealHunter',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF1565C0),
        brightness: Brightness.light,
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF1565C0),
        brightness: Brightness.dark,
      ),
      routerConfig: appRouter,
    );
  }
}

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'config/router.dart';

// Must be top-level — runs in an isolate when the app is terminated.
@pragma('vm:entry-point')
Future<void> _backgroundMessageHandler(RemoteMessage _) async {
  await Firebase.initializeApp();
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_backgroundMessageHandler);

  await FirebaseMessaging.instance.requestPermission(
    alert: true,
    badge: true,
    sound: true,
    announcement: false,
  );

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
    // Save FCM token whenever it refreshes (login, reinstall, etc.)
    FirebaseMessaging.instance.onTokenRefresh.listen(_saveFcmToken);
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) _saveFcmToken(token);

    // Notification tapped while app was in background
    FirebaseMessaging.onMessageOpenedApp.listen(_openDeal);

    // App cold-started via a tapped notification
    final initial = await FirebaseMessaging.instance.getInitialMessage();
    if (initial != null) {
      // Give the router a frame to mount before navigating
      WidgetsBinding.instance.addPostFrameCallback((_) => _openDeal(initial));
    }

    // App is in foreground — show an in-app snack instead of a system popup
    FirebaseMessaging.onMessage.listen(_showInAppBanner);
  }

  void _saveFcmToken(String token) {
    final uid = FirebaseAuth.instance.currentUser?.uid;
    if (uid == null) return;
    FirebaseFirestore.instance
        .collection('users')
        .doc(uid)
        .set({'fcm_token': token}, SetOptions(merge: true));
  }

  void _openDeal(RemoteMessage message) {
    final dealId = message.data['deal_id'] as String?;
    if (dealId != null && dealId.isNotEmpty) {
      appRouter.go('/home/deal/$dealId');
    }
  }

  void _showInAppBanner(RemoteMessage message) {
    final ctx =
        appRouter.routerDelegate.navigatorKey.currentContext;
    if (ctx == null) return;
    final n = message.notification;
    final dealId = message.data['deal_id'] as String?;
    ScaffoldMessenger.of(ctx).showSnackBar(
      SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 6),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (n?.title != null)
              Text(n!.title!,
                  style: const TextStyle(fontWeight: FontWeight.bold)),
            if (n?.body != null)
              Text(n!.body!,
                  maxLines: 2, overflow: TextOverflow.ellipsis),
          ],
        ),
        action: dealId != null
            ? SnackBarAction(
                label: 'View',
                onPressed: () => appRouter.go('/home/deal/$dealId'),
              )
            : null,
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

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter/material.dart';

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Background message handled by the OS — no app context available
}

class NotificationService {
  static final NotificationService _instance = NotificationService._();
  factory NotificationService() => _instance;
  NotificationService._();

  final FirebaseMessaging _fcm = FirebaseMessaging.instance;
  final FlutterLocalNotificationsPlugin _local = FlutterLocalNotificationsPlugin();

  static const _channelDeals = AndroidNotificationChannel(
    'deals',
    'Deal Alerts',
    description: 'Verified deals and price drops',
    importance: Importance.high,
    playSound: true,
  );

  static const _channelPriceAlerts = AndroidNotificationChannel(
    'price_alerts',
    'Price Alerts',
    description: 'Price drop alerts for tracked products',
    importance: Importance.high,
    playSound: true,
  );

  Future<void> initialize(GlobalKey<NavigatorState> navigatorKey) async {
    FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

    // Request permission
    await _fcm.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    // Set up local notifications display
    const initSettingsAndroid = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettingsIOS = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    await _local.initialize(
      const InitializationSettings(
        android: initSettingsAndroid,
        iOS: initSettingsIOS,
      ),
      onDidReceiveNotificationResponse: (details) {
        _handleNotificationTap(details.payload, navigatorKey);
      },
    );

    // Create channels (Android)
    final androidPlugin = _local.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidPlugin?.createNotificationChannel(_channelDeals);
    await androidPlugin?.createNotificationChannel(_channelPriceAlerts);

    // Handle foreground FCM messages
    FirebaseMessaging.onMessage.listen((message) {
      _showLocalNotification(message);
    });

    // Handle notification tap when app was in background
    FirebaseMessaging.onMessageOpenedApp.listen((message) {
      _routeFromMessage(message, navigatorKey);
    });

    // Handle notification tap when app was terminated
    final initial = await _fcm.getInitialMessage();
    if (initial != null) {
      Future.delayed(const Duration(seconds: 1), () {
        _routeFromMessage(initial, navigatorKey);
      });
    }
  }

  Future<String?> getToken() => _fcm.getToken();

  Future<void> subscribeToTopic(String topic) =>
      _fcm.subscribeToTopic(topic);

  Future<void> unsubscribeFromTopic(String topic) =>
      _fcm.unsubscribeFromTopic(topic);

  Future<void> subscribeToUserTopic(String userId) =>
      subscribeToTopic('user_$userId');

  void _showLocalNotification(RemoteMessage message) {
    final notification = message.notification;
    if (notification == null) return;

    final data = message.data;
    final isAlert = data['type'] == 'price_alert';
    final channel = isAlert ? _channelPriceAlerts : _channelDeals;

    _local.show(
      message.hashCode,
      notification.title,
      notification.body,
      NotificationDetails(
        android: AndroidNotificationDetails(
          channel.id,
          channel.name,
          channelDescription: channel.description,
          importance: channel.importance,
          playSound: true,
          icon: '@mipmap/ic_launcher',
          largeIcon: notification.android?.imageUrl != null
              ? DrawableResourceAndroidBitmap(notification.android!.imageUrl!)
              : null,
          styleInformation: notification.body != null
              ? BigTextStyleInformation(notification.body!)
              : null,
        ),
        iOS: const DarwinNotificationDetails(
          presentAlert: true,
          presentBadge: true,
          presentSound: true,
        ),
      ),
      payload: data['deeplink'] ?? data['product_doc_id'],
    );
  }

  void _handleNotificationTap(String? payload, GlobalKey<NavigatorState> nav) {
    if (payload == null) return;
    // Navigate to deal detail if we have a product ID
    if (payload.startsWith('app://deals/')) {
      final id = payload.replaceFirst('app://deals/', '');
      nav.currentState?.pushNamed('/deal/$id');
    }
  }

  void _routeFromMessage(RemoteMessage message, GlobalKey<NavigatorState> nav) {
    final data = message.data;
    final type = data['type'];
    if (type == 'price_alert' || type == 'deal_notification') {
      final id = data['product_doc_id'] ?? data['deal_id'];
      if (id != null) {
        nav.currentState?.pushNamed('/deal/$id');
      }
    }
  }
}

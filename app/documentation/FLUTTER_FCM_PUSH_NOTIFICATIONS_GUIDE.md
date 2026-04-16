# DealHunter Mobile App - Firebase Cloud Messaging (FCM) Setup

**Status:** Ready to Implement  
**Platforms:** iOS + Android  
**Framework:** Flutter  
**Date:** 2026-04-16

---

## TABLE OF CONTENTS
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup Instructions](#setup-instructions)
4. [Implementation Code](#implementation-code)
5. [Testing & Verification](#testing--verification)
6. [Troubleshooting](#troubleshooting)

---

## OVERVIEW

### What is FCM?

Firebase Cloud Messaging (FCM) enables sending push notifications to users' mobile devices:
- **Server → Device:** Backend sends messages via FCM to specific users/topics
- **Server → Multiple Devices:** Send to user segment (all premium users, specific groups, etc.)
- **In-App Notifications:** Show notification UI within the app
- **Background Notifications:** Handle notifications even when app is closed

### Notification Types

```
┌─────────────────────────────────────────────────────────┐
│ NOTIFICATION (user-visible badge, sound, vibration)    │
│                                                         │
│ Example: "🎉 New deal: iPhone 15 Pro - 20% off!"      │
│ Shows in notification center even if app is closed      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ DATA MESSAGE (silent, processed by app)                 │
│                                                         │
│ Example: { type: "deal_alert", deal_id: "123" }       │
│ App receives in background and processes               │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ HYBRID (notification + data)                            │
│                                                         │
│ Shows notification in center + sends data to app       │
│ Recommended approach                                    │
└─────────────────────────────────────────────────────────┘
```

---

## ARCHITECTURE

### FCM Flow

```
┌──────────────────┐
│  Admin App       │ (sends notification via API)
│  (admin-app/)    │
└────────┬─────────┘
         │
         ↓
┌──────────────────────────────────────┐
│  Backend Server (server.py)           │
│  POST /api/v1/admin/notifications     │
│  └─ Validates admin permission       │
│  └─ Sends to FCM API                 │
└────────┬─────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────┐
│  Firebase Cloud Messaging (FCM)      │
│  (cloud service hosted by Google)    │
│  └─ Queues message                   │
│  └─ Routes to device APNs/GCM        │
└────────┬─────────────────────────────┘
         │
    ┌────┴────┐
    ↓         ↓
┌────────┐  ┌────────┐
│ iOS    │  │Android │
│App     │  │App     │
│(FCM)   │  │(FCM)   │
└────┬───┘  └───┬────┘
     ↓          ↓
  [Notification Center] ← User sees banner/badge
     ↓          ↓
  [In-App Notification] ← App processes if user is active
```

### Device Registration Flow

```
┌─────────────────┐
│  App Starts     │
└────────┬────────┘
         ↓
┌────────────────────────────────┐
│ Request Notification Permission│
│ (iOS) Accept / Don't Allow      │
└────────┬───────────────────────┘
         ↓
┌────────────────────────────────┐
│ Get FCM Registration Token      │
│ (unique per app install)        │
└────────┬───────────────────────┘
         ↓
┌────────────────────────────────┐
│ Save Token to Firestore:        │
│ users/{user_id}/fcm_tokens: []  │
│ (supports multiple devices)     │
└────────┬───────────────────────┘
         ↓
┌────────────────────────────────┐
│ Ready to Receive Notifications  │
│ (admin can send from admin app) │
└────────────────────────────────┘
```

---

## SETUP INSTRUCTIONS

### STEP 1: Enable FCM in Firebase Console

1. Go to Firebase Console (console.firebase.google.com)
2. Select project: `dealhunter-egypt-70d29`
3. Navigate to **Messaging** (left sidebar)
4. Click **"Create first campaign"** (or "New campaign")

### STEP 2: iOS Setup (Apple Push Notifications)

**2.1: Create APNs Certificate**

1. Go to Apple Developer (developer.apple.com)
2. Login with Apple account
3. Navigate to **Certificates, Identifiers & Profiles**
4. Click **Certificates** → **+ (Add)**
5. Select **"Apple Push Notification service SSL (Sandbox & Production)"**
6. Select your App ID (e.g., com.dealhunter)
7. Upload Certificate Signing Request (CSR) from Mac:
   ```bash
   # On Mac, use Keychain Access:
   # Keychain Access → Request a Certificate from a Certificate Authority
   # Save CSR file
   ```
8. Download certificate (.cer file)
9. Open in Keychain Access → Export as .p8 key file

**2.2: Upload to Firebase**

1. In Firebase Console → Project Settings → Cloud Messaging
2. Click **Upload APNs Authentication Key** (under Apple app configuration)
3. Upload the .p8 file
4. Enter Key ID, Team ID from Apple Developer account
5. Save

**2.3: Update iOS Project**

In Xcode:
1. Select Runner → Build Phases → Link Binary With Libraries
2. Add **UserNotifications.framework** and **UserNotificationsUI.framework**

### STEP 3: Android Setup (Google Cloud Messaging)

**3.1: Get Server API Key**

1. In Firebase Console → Project Settings → Cloud Messaging
2. Look for **Server API Key** under Firebase Cloud Messaging
3. Copy the key (e.g., `AAAA...xyz`)

**3.2: Update Android Project**

Android automatically uses the `google-services.json` file included in the Flutter app.

### STEP 4: Update pubspec.yaml

Add FCM dependency to both user and admin apps:

```yaml
dependencies:
  firebase_messaging: ^14.7.0
  flutter_local_notifications: ^16.3.0  # For local notifications
```

Run:
```bash
flutter pub get
```

---

## IMPLEMENTATION CODE

### 1. FCM Service (Shared)

**File:** `lib/services/fcm_service.dart`

```dart
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

class FCMService {
  static final FirebaseMessaging _messaging = FirebaseMessaging.instance;
  static final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();
  
  static Future<void> initialize() async {
    // Request notification permission (iOS only, Android auto-approved)
    await _messaging.requestPermission(
      alert: true,
      announcement: false,
      badge: true,
      carPlay: false,
      criticalAlert: false,
      provisional: false,
      sound: true,
    );

    // Initialize local notifications
    const AndroidInitializationSettings androidInitSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    
    const DarwinInitializationSettings iosInitSettings =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    final InitializationSettings initSettings = InitializationSettings(
      android: androidInitSettings,
      iOS: iosInitSettings,
    );

    await _localNotifications.initialize(initSettings);

    // Get FCM token and save to Firestore
    final token = await _messaging.getToken();
    if (token != null) {
      await _saveFCMToken(token);
    }

    // Listen for token refresh
    _messaging.onTokenRefresh.listen((newToken) {
      _saveFCMToken(newToken);
    });

    // Handle notifications when app is in foreground
    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      _handleForegroundNotification(message);
    });

    // Handle notification taps when app is in background
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      _handleNotificationTap(message);
    });

    // Handle initial notification (app launched via notification)
    final initialMessage = await _messaging.getInitialMessage();
    if (initialMessage != null) {
      _handleNotificationTap(initialMessage);
    }
  }

  static Future<void> _saveFCMToken(String token) async {
    try {
      final userId = _getCurrentUserId(); // Get from auth
      if (userId != null) {
        await FirebaseFirestore.instance
            .collection('users')
            .doc(userId)
            .update({
          'fcm_tokens': FieldValue.arrayUnion([token]),
          'last_token_update': Timestamp.now(),
        });
        print('✅ FCM token saved for user: $userId');
      }
    } catch (e) {
      print('❌ Error saving FCM token: $e');
    }
  }

  static Future<void> _handleForegroundNotification(
    RemoteMessage message,
  ) async {
    final notification = message.notification;
    final data = message.data;

    if (notification != null) {
      // Show local notification banner
      await _localNotifications.show(
        notification.hashCode,
        notification.title,
        notification.body,
        NotificationDetails(
          android: AndroidNotificationDetails(
            'deal_alerts',
            'Deal Alerts',
            channelDescription: 'Notifications about new deals',
            importance: Importance.max,
            priority: Priority.high,
            showWhen: true,
          ),
          iOS: const DarwinNotificationDetails(
            presentAlert: true,
            presentBadge: true,
            presentSound: true,
          ),
        ),
      );

      // Handle data (e.g., navigate to deal, update UI)
      if (data.containsKey('deal_id')) {
        print('📱 Deal notification: ${data['deal_id']}');
      }
    }
  }

  static Future<void> _handleNotificationTap(RemoteMessage message) async {
    final data = message.data;

    // Handle different notification types
    if (data.containsKey('type')) {
      final type = data['type'];
      
      switch (type) {
        case 'deal_alert':
          // Navigate to deal details
          print('🔗 Navigate to deal: ${data['deal_id']}');
          // context.go('/deals/${data['deal_id']}');
          break;
        
        case 'membership_alert':
          // Navigate to membership screen
          print('🔗 Navigate to membership');
          // context.go('/membership');
          break;
        
        case 'referral_reward':
          // Navigate to referrals
          print('🔗 Navigate to referrals');
          // context.go('/referrals');
          break;
        
        default:
          print('Unknown notification type: $type');
      }
    }
  }

  static String? _getCurrentUserId() {
    // TODO: Get from auth provider/Firebase Auth
    return FirebaseAuth.instance.currentUser?.uid;
  }

  static Future<void> unsubscribeFromTopic(String topic) async {
    try {
      await _messaging.unsubscribeFromTopic(topic);
      print('✅ Unsubscribed from topic: $topic');
    } catch (e) {
      print('❌ Error unsubscribing from topic: $e');
    }
  }

  static Future<void> subscribeToTopic(String topic) async {
    try {
      await _messaging.subscribeToTopic(topic);
      print('✅ Subscribed to topic: $topic');
    } catch (e) {
      print('❌ Error subscribing to topic: $e');
    }
  }
}
```

### 2. Notification Preferences (User-Facing)

**File:** `lib/screens/settings/notification_preferences_screen.dart`

```dart
class NotificationPreferencesScreen extends ConsumerStatefulWidget {
  const NotificationPreferencesScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<NotificationPreferencesScreen> createState() =>
      _NotificationPreferencesScreenState();
}

class _NotificationPreferencesScreenState
    extends ConsumerState<NotificationPreferencesScreen> {
  bool _dealsEnabled = true;
  bool _groupAlertsEnabled = true;
  bool _referralAlertsEnabled = true;
  bool _membershipAlertsEnabled = true;
  bool _soundEnabled = true;
  bool _badgeEnabled = true;

  @override
  void initState() {
    super.initState();
    _loadPreferences();
  }

  Future<void> _loadPreferences() async {
    // Load saved preferences from Firestore or SharedPreferences
    final userId = FirebaseAuth.instance.currentUser?.uid;
    if (userId != null) {
      final doc = await FirebaseFirestore.instance
          .collection('users')
          .doc(userId)
          .get();
      
      final prefs = doc.data()?['notification_preferences'] ?? {};
      
      setState(() {
        _dealsEnabled = prefs['deals'] ?? true;
        _groupAlertsEnabled = prefs['group_alerts'] ?? true;
        _referralAlertsEnabled = prefs['referral_alerts'] ?? true;
        _membershipAlertsEnabled = prefs['membership_alerts'] ?? true;
        _soundEnabled = prefs['sound'] ?? true;
        _badgeEnabled = prefs['badge'] ?? true;
      });
    }
  }

  Future<void> _savePreference(String key, bool value) async {
    try {
      final userId = FirebaseAuth.instance.currentUser?.uid;
      if (userId != null) {
        await FirebaseFirestore.instance
            .collection('users')
            .doc(userId)
            .update({
          'notification_preferences.$key': value,
        });

        // Subscribe/unsubscribe from topics
        if (key == 'deals') {
          if (value) {
            await FCMService.subscribeToTopic('deal_alerts');
          } else {
            await FCMService.unsubscribeFromTopic('deal_alerts');
          }
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error saving preference: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Notification Settings')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Notification Types',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),

            // Deal alerts
            SwitchListTile(
              title: const Text('New Deal Alerts'),
              subtitle: const Text('Get notified about new deals matching your interests'),
              value: _dealsEnabled,
              onChanged: (value) {
                setState(() => _dealsEnabled = value);
                _savePreference('deals', value);
              },
            ),

            // Group alerts
            SwitchListTile(
              title: const Text('Group Notifications'),
              subtitle: const Text('Alerts about group activities and deals'),
              value: _groupAlertsEnabled,
              onChanged: (value) {
                setState(() => _groupAlertsEnabled = value);
                _savePreference('group_alerts', value);
              },
            ),

            // Referral alerts
            SwitchListTile(
              title: const Text('Referral Rewards'),
              subtitle: const Text('When someone signs up with your referral code'),
              value: _referralAlertsEnabled,
              onChanged: (value) {
                setState(() => _referralAlertsEnabled = value);
                _savePreference('referral_alerts', value);
              },
            ),

            // Membership alerts
            SwitchListTile(
              title: const Text('Membership Updates'),
              subtitle: const Text('Subscription renewals and tier changes'),
              value: _membershipAlertsEnabled,
              onChanged: (value) {
                setState(() => _membershipAlertsEnabled = value);
                _savePreference('membership_alerts', value);
              },
            ),

            const SizedBox(height: 32),

            Text(
              'Notification Settings',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),

            // Sound
            SwitchListTile(
              title: const Text('Sound'),
              subtitle: const Text('Play sound for notifications'),
              value: _soundEnabled,
              onChanged: (value) {
                setState(() => _soundEnabled = value);
                _savePreference('sound', value);
              },
            ),

            // Badge
            SwitchListTile(
              title: const Text('Badge'),
              subtitle: const Text('Show notification badges on app icon'),
              value: _badgeEnabled,
              onChanged: (value) {
                setState(() => _badgeEnabled = value);
                _savePreference('badge', value);
              },
            ),

            const SizedBox(height: 32),

            // Info box
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                border: Border.all(color: Colors.blue.shade200),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.info, color: Colors.blue.shade700),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'You will always receive critical notifications (membership expiry, account security) regardless of these settings.',
                      style: TextStyle(color: Colors.blue.shade700, fontSize: 12),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

### 3. Backend FCM Sending (server.py)

**Add to server.py:**

```python
from firebase_admin import messaging

@bp.post('/admin/notifications/send')
@token_required
@admin_required(required_permission='notifications')
def send_notification(current_admin):
    """Send push notification to users via FCM"""
    data = request.get_json()
    
    try:
        title = data.get('title')
        message = data.get('message')
        target_type = data.get('target_type')  # 'all', 'tier', 'group', 'custom'
        target_id = data.get('target_id')  # tier name, group id, or list of user ids
        
        if not title or not message:
            return jsonify({'error': 'Title and message required'}), 400
        
        # Get recipient FCM tokens based on target
        tokens = []
        
        if target_type == 'all':
            # Send to all users
            users = db.collection('users').stream()
            for user in users:
                user_tokens = user.get('fcm_tokens', [])
                tokens.extend(user_tokens)
        
        elif target_type == 'tier':
            # Send to users with specific tier
            users = db.collection('users').where('tier', '==', target_id).stream()
            for user in users:
                user_tokens = user.get('fcm_tokens', [])
                tokens.extend(user_tokens)
        
        elif target_type == 'group':
            # Send to users in specific group
            group = db.collection('user_groups').document(target_id).get()
            if group.exists:
                members = group.get('members', [])
                for member in members:
                    user = db.collection('users').document(member['email']).get()
                    user_tokens = user.get('fcm_tokens', [])
                    tokens.extend(user_tokens)
        
        elif target_type == 'custom':
            # Send to specific user ids
            user_ids = data.get('user_ids', [])
            for user_id in user_ids:
                user = db.collection('users').document(user_id).get()
                if user.exists:
                    user_tokens = user.get('fcm_tokens', [])
                    tokens.extend(user_tokens)
        
        else:
            return jsonify({'error': 'Invalid target_type'}), 400
        
        if not tokens:
            return jsonify({'error': 'No recipients found'}), 404
        
        # Send multicast message (up to 500 tokens per call)
        sent_count = 0
        opened_count = 0
        failed_count = 0
        
        for i in range(0, len(tokens), 500):
            batch = tokens[i:i+500]
            
            message_obj = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=message[:240],  # FCM limit
                ),
                data={
                    'type': 'notification',
                    'sent_at': datetime.utcnow().isoformat(),
                    'sent_by': current_admin['email'],
                },
                tokens=batch,
            )
            
            response = messaging.send_multicast(message_obj)
            sent_count += response.success_count
            failed_count += response.failure_count
        
        # Log notification
        notification_doc = {
            'title': title,
            'message': message,
            'target_type': target_type,
            'sent_count': sent_count,
            'opened_count': 0,  # Updated when users open
            'failed_count': failed_count,
            'sent_at': datetime.utcnow(),
            'sent_by': current_admin['email'],
        }
        
        notification_id = db.collection('notifications').add(notification_doc)[1].id
        
        return jsonify({
            'success': True,
            'notification_id': notification_id,
            'sent_count': sent_count,
            'failed_count': failed_count,
        }), 200
    
    except Exception as e:
        print(f'❌ Error sending notification: {e}')
        return jsonify({'error': str(e)}), 500
```

### 4. Initialization in App

**File:** `lib/main.dart` (User App)

```dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  // Initialize Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  
  // Initialize FCM
  await FCMService.initialize();
  
  runApp(const DealHunterApp());
}
```

---

## TESTING & VERIFICATION

### Test 1: Request Notification Permission

**Steps:**
1. Run app on iOS device
2. Permission popup appears: "Allow notifications?"
3. Tap "Allow"
4. Check: FCM token saved in Firestore (`users/{user_id}/fcm_tokens`)

**Expected Result:**
```
✅ FCM token saved for user: abc123
```

### Test 2: Send Test Notification (Firebase Console)

**Steps:**
1. Firebase Console → Messaging → "Create first campaign"
2. Fill in:
   - Title: "Test Deal"
   - Body: "iPhone 15 Pro - 20% off"
   - Target: Users who open app
3. Click "Send test message"
4. Select your device from dropdown
5. Click "Test"

**Expected Result:**
- Notification appears in notification center
- Sound plays (if enabled)
- Badge shows on app icon

### Test 3: Send from Admin App

**Steps:**
1. Login to admin app as owner
2. Go to Notifications screen
3. Fill:
   - Title: "New Deal Alert"
   - Message: "Great discount on Samsung TV"
   - Target: All Users
4. Click "Send"

**Expected Result:**
- All users' devices receive notification
- Admin app shows "Sent 5,000"
- Admin logs notification in Firestore

### Test 4: Handle Notification Tap

**Steps:**
1. When notification arrives, tap it
2. App opens (or comes to foreground)
3. App navigates to relevant screen (e.g., deal details if deal_id in data)

**Expected Result:**
- App handles `_handleNotificationTap` logic
- Correct screen opens

### Test 5: Foreground Notification

**Steps:**
1. Keep app open in foreground
2. Send notification from admin app
3. Banner should appear at top of screen (in-app notification)

**Expected Result:**
- Notification banner shows in app
- User can tap to open deal
- No system notification center entry (just in-app)

### Test 6: Background Notification

**Steps:**
1. Close app or send to background
2. Send notification from admin app
3. Check notification center

**Expected Result:**
- Notification appears in system notification center
- Tapping opens app and navigates correctly

---

## FIRESTORE SCHEMA UPDATES

Add these fields to `users` collection:

```javascript
users/{userId}
├── ... existing fields ...
├── fcm_tokens (array) [new]
│   ├── "abc123def456..." // Device 1
│   └── "xyz789uvw012..." // Device 2 (if logged in on multiple devices)
├── last_token_update (timestamp) [new]
├── notification_preferences (object) [new]
│   ├── deals (boolean)
│   ├── group_alerts (boolean)
│   ├── referral_alerts (boolean)
│   ├── membership_alerts (boolean)
│   ├── sound (boolean)
│   └── badge (boolean)
└── notifications_opened (array) [new]
    └── { notification_id, opened_at }
```

Add new collection: `notifications`

```javascript
notifications/{notification_id}
├── title (string)
├── message (string)
├── target_type (string) — 'all', 'tier', 'group', 'custom'
├── sent_count (number)
├── opened_count (number)
├── failed_count (number)
├── sent_at (timestamp)
├── sent_by (string) — admin email
└── data (object) — any custom data
```

---

## NOTIFICATION TYPES (Examples)

### Deal Alert Notification

```json
{
  "title": "🎉 Hot Deal Available!",
  "body": "Samsung Galaxy S24 - 15% OFF | EGP 5,999",
  "data": {
    "type": "deal_alert",
    "deal_id": "deal-123",
    "category": "electronics"
  }
}
```

**App receives → Navigate to:** `/deals/deal-123`

### Referral Reward

```json
{
  "title": "💰 Referral Reward!",
  "body": "Ahmed signed up with your code - Get 1 month free Premium!",
  "data": {
    "type": "referral_reward",
    "reward_type": "premium_1month"
  }
}
```

**App receives → Navigate to:** `/referrals`

### Group Activity

```json
{
  "title": "👥 Group Update",
  "body": "Your group found 5 new deals today",
  "data": {
    "type": "group_alert",
    "group_id": "group-456"
  }
}
```

**App receives → Navigate to:** `/groups/group-456`

### Membership Renewal Reminder

```json
{
  "title": "⏰ Membership Expiring Soon",
  "body": "Your Premium membership expires in 3 days. Renew now to keep benefits!",
  "data": {
    "type": "membership_alert",
    "action": "renew"
  }
}
```

**App receives → Navigate to:** `/membership`

---

## TOPICS-BASED SUBSCRIPTIONS (Advanced)

Instead of sending to individual tokens, subscribe users to topics:

```dart
// Subscribe user to deal alerts when they join
FCMService.subscribeToTopic('deal_alerts');

// Subscribe to tier-specific topic
FCMService.subscribeToTopic('tier_premium');

// Subscribe to group
FCMService.subscribeToTopic('group_${groupId}');
```

**Benefits:**
- No need to manage individual tokens
- Automatic scaling (Firebase handles it)
- Simple targeting (send to `topic:deal_alerts`)

**Backend:**

```python
message_obj = messaging.Message(
    notification=messaging.Notification(...),
    topic='deal_alerts',  # Send to all subscribed users
)
messaging.send(message_obj)
```

---

## TROUBLESHOOTING

### Issue: No Notifications Received

**Causes & Solutions:**
1. **FCM token not saved**
   - Check Firestore: `users/{userId}/fcm_tokens`
   - Ensure user is authenticated

2. **App not initialized**
   - Call `FCMService.initialize()` in main.dart
   - Check for errors in console

3. **Invalid tokens**
   - Remove old/invalid tokens
   - Refresh token: `FirebaseMessaging.instance.getToken()`

4. **Permissions not granted (iOS)**
   - User tapped "Don't Allow"
   - Go to Settings → App → Notifications → Allow

### Issue: Notifications in Wrong Language

**Solution:**
- Firebase automatically uses device language
- For custom language, send in `data` only (not notification)

### Issue: No Sound on Android

**Solution:**
Add notification channel:

```dart
const AndroidNotificationChannel channel = AndroidNotificationChannel(
  'deal_alerts',
  'Deal Alerts',
  description: 'Notifications about new deals',
  importance: Importance.max,
  enableVibration: true,
  enableLights: true,
  sound: RawResourceSound('notification_sound'),
);

await _localNotifications
    .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>()
    ?.createNotificationChannel(channel);
```

### Issue: Duplicate Notifications

**Solution:**
- Each notification has unique ID (based on hash)
- Don't send same message twice
- Check deduplication logic

---

## MONITORING & ANALYTICS

### Check Notification Delivery

**Firebase Console:**
1. Messaging → Recent campaigns
2. Click campaign
3. See: Sent, Opened, Failed counts

### Track in Firestore

When user opens notification:

```python
@bp.post('/user/notifications/{notification_id}/opened')
@token_required
def mark_notification_opened(current_user, notification_id):
    """Track when user opens notification"""
    db.collection('notifications').document(notification_id).update({
        'opened_count': FieldValue.increment(1),
    })
    
    user_id = current_user.get('uid')
    db.collection('users').document(user_id).update({
        'notifications_opened': FieldValue.arrayUnion([{
            'notification_id': notification_id,
            'opened_at': datetime.utcnow(),
        }]),
    })
```

---

## NEXT STEPS

1. **Enable FCM in Firebase Console** (if not already enabled)
2. **Setup iOS APNs certificate** (can skip Android for now)
3. **Add firebase_messaging dependency** to pubspec.yaml
4. **Copy FCMService code** to lib/services/fcm_service.dart
5. **Initialize in main.dart** (call FCMService.initialize())
6. **Add notification preferences screen** to settings
7. **Test on real iOS and Android devices**
8. **Verify notifications in admin app**
9. **Monitor delivery in Firebase Console**

---

## SUMMARY

**FCM enables:**
- ✅ Push notifications to all users
- ✅ Targeted notifications (by tier, group, user)
- ✅ In-app notification banners
- ✅ Deep linking (open specific screens)
- ✅ Background message handling
- ✅ Topic-based subscriptions

**Setup complexity:** Medium (iOS APNs required)

**Testing:** Fully testable on real devices

---

**Push notifications are a critical feature for user engagement!** 🚀

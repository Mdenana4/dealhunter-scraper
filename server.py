# DealHunter Egypt - Web Server + API Server
# Keeps Render alive + runs scraper in background + handles admin auth/team management

import threading
import os
import time
import json
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import schedule
from flask import Flask, request, jsonify, send_file
from functools import wraps
import firebase_admin
from firebase_admin import credentials, auth, firestore

# Initialize Flask
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Initialize Firebase Admin SDK
db = None
try:
    # Check if app already initialized
    try:
        firebase_admin.get_app()
        db = firestore.client()
        print("✓ Firebase Admin SDK already initialized")
    except ValueError:
        # App not initialized yet, initialize it
        print("  Initializing Firebase Admin SDK...")

        # Try environment variable with JSON content first
        firebase_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if firebase_json:
            print(f"  Found FIREBASE_CREDENTIALS_JSON environment variable")
            try:
                cred_dict = json.loads(firebase_json)
                print(f"  ✓ Successfully parsed JSON credentials")
                firebase_admin.initialize_app(credentials.Certificate(cred_dict))
                db = firestore.client()
                print(f"✓ Firebase Admin SDK initialized with FIREBASE_CREDENTIALS_JSON")
            except json.JSONDecodeError as e:
                print(f"  ✗ Failed to parse JSON: {e}")
                raise
            except Exception as e:
                print(f"  ✗ Failed to initialize: {e}")
                raise
        # Try file path
        elif os.path.exists('./firebase-credentials.json'):
            print(f"  Found firebase-credentials.json file")
            firebase_admin.initialize_app(
                credentials.Certificate('./firebase-credentials.json')
            )
            db = firestore.client()
            print(f"✓ Firebase Admin SDK initialized with file")
        # Try FIREBASE_CREDENTIALS_PATH env var
        elif os.environ.get('FIREBASE_CREDENTIALS_PATH'):
            print(f"  Found FIREBASE_CREDENTIALS_PATH environment variable")
            firebase_admin.initialize_app(
                credentials.Certificate(os.environ.get('FIREBASE_CREDENTIALS_PATH'))
            )
            db = firestore.client()
            print(f"✓ Firebase Admin SDK initialized with FIREBASE_CREDENTIALS_PATH")
        else:
            print(f"  Trying ApplicationDefault credentials...")
            firebase_admin.initialize_app(credentials.ApplicationDefault())
            db = firestore.client()
            print(f"✓ Firebase Admin SDK initialized with ApplicationDefault")

except Exception as e:
    print(f"⚠ Firebase Admin SDK initialization failed: {e}")
    db = None


# ============ AUTHENTICATION HELPERS ============

def verify_id_token(id_token):
    """Verify Firebase ID token and return user data"""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        return None


def require_auth(f):
    """Decorator to require valid auth token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401

        decoded = verify_id_token(token)
        if not decoded:
            return jsonify({'error': 'Invalid token'}), 401

        request.current_user = decoded
        return f(*args, **kwargs)
    return decorated_function


def require_admin(f):
    """Decorator to require valid admin with ownership"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Missing authorization token'}), 401

        decoded = verify_id_token(token)
        if not decoded:
            return jsonify({'error': 'Invalid token'}), 401

        try:
            admin_doc = db.collection('admin_users').document(decoded['email']).get()
            if not admin_doc.exists:
                return jsonify({'error': 'Not authorized as admin'}), 403

            admin_data = admin_doc.to_dict()
            if admin_data.get('role') != 'owner':
                return jsonify({'error': 'Owner role required'}), 403

            request.current_user = decoded
            request.current_admin = admin_data
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({'error': f'Auth check failed: {str(e)}'}), 500

    return decorated_function


def check_permission(required_permission):
    """Decorator to check if admin has specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return jsonify({'error': 'Missing authorization token'}), 401

            decoded = verify_id_token(token)
            if not decoded:
                return jsonify({'error': 'Invalid token'}), 401

            try:
                admin_doc = db.collection('admin_users').document(decoded['email']).get()
                if not admin_doc.exists:
                    return jsonify({'error': 'Not authorized as admin'}), 403

                admin_data = admin_doc.to_dict()

                # Owner role has all permissions
                if admin_data.get('role') == 'owner':
                    request.current_user = decoded
                    request.current_admin = admin_data
                    return f(*args, **kwargs)

                # Check if required permission in permissions array
                permissions = admin_data.get('permissions', [])
                if required_permission not in permissions:
                    return jsonify({'error': f'Permission "{required_permission}" required'}), 403

                request.current_user = decoded
                request.current_admin = admin_data
                return f(*args, **kwargs)
            except Exception as e:
                return jsonify({'error': f'Auth check failed: {str(e)}'}), 500

        return decorated_function
    return decorator


# ============ STATIC FILES ============

@app.route('/user')
def user_dashboard():
    """Serve user dashboard"""
    try:
        # Try multiple possible paths
        paths = [
            'user-dashboard.html',
            './user-dashboard.html',
            os.path.join(os.path.dirname(__file__), 'user-dashboard.html')
        ]

        for path in paths:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return f.read(), 200, {'Content-Type': 'text/html'}

        print(f"ERROR: user-dashboard.html not found in paths: {paths}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Files in current dir: {os.listdir('.')[:10]}")
        return jsonify({'error': 'User dashboard not found', 'cwd': os.getcwd()}), 404
    except Exception as e:
        print(f"ERROR serving dashboard: {e}")
        return jsonify({'error': str(e)}), 500


# ============ AUTHENTICATION ENDPOINTS ============

@app.route('/auth/login', methods=['POST'])
def login():
    """Login with email/password (handled by Firebase client SDK)
    This endpoint is mainly for backend verification"""
    try:
        data = request.get_json()
        id_token = data.get('id_token')

        if not id_token:
            return jsonify({'error': 'id_token required'}), 400

        decoded = verify_id_token(id_token)
        if not decoded:
            return jsonify({'error': 'Invalid token'}), 401

        # Check if user exists in admin_users
        admin_doc = db.collection('admin_users').document(decoded['email']).get()
        if not admin_doc.exists:
            return jsonify({'error': 'User not registered as admin'}), 403

        admin_data = admin_doc.to_dict()

        # Update last_login
        db.collection('admin_users').document(decoded['email']).update({
            'last_login': datetime.datetime.now(datetime.timezone.utc)
        })

        return jsonify({
            'success': True,
            'admin': {
                'email': decoded['email'],
                'name': admin_data.get('name'),
                'role': admin_data.get('role'),
                'permissions': admin_data.get('permissions', []),
                'status': admin_data.get('status')
            }
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/auth/me', methods=['GET'])
@require_auth
def get_current_user():
    """Get current admin's info"""
    try:
        admin_doc = db.collection('admin_users').document(request.current_user['email']).get()
        if not admin_doc.exists:
            return jsonify({'error': 'Admin not found'}), 404

        admin_data = admin_doc.to_dict()
        return jsonify({
            'email': request.current_user['email'],
            'name': admin_data.get('name'),
            'role': admin_data.get('role'),
            'permissions': admin_data.get('permissions', []),
            'status': admin_data.get('status'),
            'last_login': admin_data.get('last_login')
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ TEAM MANAGEMENT ENDPOINTS ============

@app.route('/admin/team', methods=['GET'])
@require_admin
def get_team():
    """Get all admin users"""
    try:
        team_docs = db.collection('admin_users').stream()
        team = []
        for doc in team_docs:
            data = doc.to_dict()
            team.append({
                'email': doc.id,
                'name': data.get('name'),
                'role': data.get('role'),
                'permissions': data.get('permissions', []),
                'status': data.get('status'),
                'last_login': data.get('last_login'),
                'added_at': data.get('added_at'),
                'added_by': data.get('added_by')
            })
        return jsonify({'team': team}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/team', methods=['POST'])
@require_admin
def add_team_member():
    """Add new team member"""
    try:
        data = request.get_json()
        email = data.get('email', '').lower().strip()
        name = data.get('name', '').strip()
        role = data.get('role', 'viewer')
        permissions = data.get('permissions', [])
        status = data.get('status', 'active')
        notes = data.get('notes', '')

        if not email or not name:
            return jsonify({'error': 'email and name required'}), 400

        if role not in ['owner', 'editor', 'viewer']:
            return jsonify({'error': 'Invalid role'}), 400

        # Owner role always has all permissions
        if role == 'owner':
            permissions = ['sources', 'deals', 'users', 'notifications', 'checker', 'competitors', 'scraper_control']

        # Check if user already exists
        existing = db.collection('admin_users').document(email).get()
        if existing.exists:
            return jsonify({'error': 'User already exists'}), 400

        db.collection('admin_users').document(email).set({
            'email': email,
            'name': name,
            'role': role,
            'permissions': permissions,
            'status': status,
            'notes': notes,
            'added_at': datetime.datetime.now(datetime.timezone.utc),
            'added_by': request.current_user['email'],
            'last_login': None
        })

        return jsonify({'success': True, 'message': f'Added {name}'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/team/<email>', methods=['PUT'])
@require_admin
def update_team_member(email):
    """Update team member"""
    try:
        email = email.lower().strip()
        data = request.get_json()

        admin_doc = db.collection('admin_users').document(email).get()
        if not admin_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        admin_data = admin_doc.to_dict()

        # Update fields
        updates = {}
        if 'name' in data:
            updates['name'] = data['name'].strip()
        if 'role' in data:
            role = data['role']
            if role not in ['owner', 'editor', 'viewer']:
                return jsonify({'error': 'Invalid role'}), 400
            updates['role'] = role

            # Owner role always has all permissions
            if role == 'owner':
                updates['permissions'] = ['sources', 'deals', 'users', 'notifications', 'checker', 'competitors', 'scraper_control']
            elif 'permissions' in data:
                updates['permissions'] = data['permissions']
        elif 'permissions' in data and admin_data.get('role') != 'owner':
            updates['permissions'] = data['permissions']

        if 'status' in data:
            updates['status'] = data['status']
        if 'notes' in data:
            updates['notes'] = data['notes']

        if not updates:
            return jsonify({'error': 'No fields to update'}), 400

        db.collection('admin_users').document(email).update(updates)

        return jsonify({'success': True, 'message': f'Updated {email}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/team/<email>', methods=['DELETE'])
@require_admin
def remove_team_member(email):
    """Remove team member"""
    try:
        email = email.lower().strip()

        # Don't allow removing the only owner
        team_docs = list(db.collection('admin_users').where('role', '==', 'owner').stream())
        if len(team_docs) == 1 and team_docs[0].id == email:
            return jsonify({'error': 'Cannot remove the only owner'}), 400

        db.collection('admin_users').document(email).delete()
        return jsonify({'success': True, 'message': f'Removed {email}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ PERMISSION CHECKING ENDPOINT ============

@app.route('/admin/check-permission/<resource>', methods=['GET'])
@require_auth
def check_permission_endpoint(resource):
    """Check if current admin can access a resource"""
    try:
        admin_doc = db.collection('admin_users').document(request.current_user['email']).get()
        if not admin_doc.exists:
            return jsonify({'allowed': False, 'reason': 'Not registered as admin'}), 403

        admin_data = admin_doc.to_dict()

        # Owner role has all permissions
        if admin_data.get('role') == 'owner':
            return jsonify({'allowed': True, 'reason': 'Owner role'}), 200

        # Check permissions array
        permissions = admin_data.get('permissions', [])
        if resource in permissions:
            return jsonify({'allowed': True, 'reason': f'Has {resource} permission'}), 200
        else:
            return jsonify({'allowed': False, 'reason': f'Missing {resource} permission'}), 403
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ STRIPE CONFIGURATION ============
import stripe

STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    print("✓ Stripe API key configured")
else:
    print("⚠ STRIPE_SECRET_KEY not set")


# ============ PHASE 5: USER MANAGEMENT ENDPOINTS ============

@app.route('/api/v1/users', methods=['POST'])
def create_user():
    """Create new user on signup"""
    try:
        data = request.get_json()
        id_token = data.get('id_token')

        if not id_token:
            return jsonify({'error': 'id_token required'}), 400

        decoded = verify_id_token(id_token)
        if not decoded:
            return jsonify({'error': 'Invalid token'}), 401

        email = decoded.get('email')
        user_data = {
            'id': decoded.get('uid'),
            'email': email,
            'name': data.get('name', ''),
            'phone': data.get('phone', ''),
            'tier': 'free',
            'subscription_active': False,
            'stripe_customer_id': None,
            'stripe_subscription_id': None,
            'subscription_start_date': None,
            'subscription_renewal_date': None,
            'trial_ends_at': None,
            'daily_deal_limit': 50,
            'deals_shared_today': 0,
            'last_reset_date': datetime.date.today().isoformat(),
            'referral_code': generate_referral_code(),
            'referred_by_uid': data.get('referred_by_uid'),
            'created_at': datetime.datetime.now(datetime.timezone.utc),
            'updated_at': datetime.datetime.now(datetime.timezone.utc),
            'metadata': {
                'language': 'en',
                'notifications_enabled': True,
                'marketing_consent': False,
                'last_login': datetime.datetime.now(datetime.timezone.utc)
            }
        }

        db.collection('users').document(email).set(user_data)

        return jsonify({
            'success': True,
            'user': {
                'uid': decoded.get('uid'),
                'email': email,
                'tier': 'free',
                'referral_code': user_data['referral_code'],
                'daily_deal_limit': 50,
                'created_at': user_data['created_at'].isoformat()
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<uid>', methods=['GET'])
@require_auth
def get_user(uid):
    """Get user profile"""
    try:
        # Get user from email (uid is actually the user's UID, but we use email as doc ID)
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        return jsonify(user_data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<uid>', methods=['PUT'])
@require_auth
def update_user(uid):
    """Update user profile"""
    try:
        user_email = request.current_user.get('email')
        data = request.get_json()

        updates = {}
        if 'name' in data:
            updates['name'] = data['name']
        if 'phone' in data:
            updates['phone'] = data['phone']
        if 'language' in data:
            updates['metadata.language'] = data['language']
        if 'notifications_enabled' in data:
            updates['metadata.notifications_enabled'] = data['notifications_enabled']

        updates['updated_at'] = datetime.datetime.now(datetime.timezone.utc)

        db.collection('users').document(user_email).update(updates)

        user_doc = db.collection('users').document(user_email).get()
        return jsonify({'success': True, 'user': user_doc.to_dict()}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<uid>/referral-stats', methods=['GET'])
@require_auth
def get_referral_stats(uid):
    """Get referral program stats"""
    try:
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        referral_code = user_doc.to_dict().get('referral_code')

        # Get all referrals from this user
        referrals_snap = db.collection('referrals').where('referrer_id', '==', user_email).stream()
        referrals = [doc.to_dict() for doc in referrals_snap]

        activated = sum(1 for r in referrals if r.get('status') in ['activated', 'redeemed', 'expired'])
        redeemed = sum(1 for r in referrals if r.get('status') == 'redeemed')
        pending = sum(1 for r in referrals if r.get('status') == 'pending')

        return jsonify({
            'referral_code': referral_code,
            'total_referrals': len(referrals),
            'activated_referrals': activated,
            'redeemed_referrals': redeemed,
            'pending_rewards': pending,
            'referral_history': [
                {
                    'referee_email': r.get('referee_email'),
                    'status': r.get('status'),
                    'reward_type': r.get('reward_type'),
                    'redeemed_at': r.get('redeemed_at')
                }
                for r in referrals
            ]
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/users/<uid>', methods=['DELETE'])
@require_auth
def delete_user(uid):
    """Deactivate/delete account"""
    try:
        user_email = request.current_user.get('email')

        # Soft delete - mark as inactive
        db.collection('users').document(user_email).update({
            'status': 'deleted',
            'updated_at': datetime.datetime.now(datetime.timezone.utc)
        })

        return jsonify({'success': True, 'message': 'Account deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ PHASE 5: SUBSCRIPTION ENDPOINTS ============

@app.route('/api/v1/subscriptions/checkout', methods=['POST'])
@require_auth
def create_checkout_session():
    """Create Stripe checkout session"""
    try:
        data = request.get_json()
        tier = data.get('tier')  # 'premium' or 'vip'
        user_email = request.current_user.get('email')

        if tier not in ['premium', 'vip']:
            return jsonify({'error': 'Invalid tier'}), 400

        user_doc = db.collection('users').document(user_email).get()
        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        stripe_customer_id = user_data.get('stripe_customer_id')

        # Create Stripe customer if not exists
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={'firebase_uid': user_data.get('id')}
            )
            stripe_customer_id = customer.id
            db.collection('users').document(user_email).update({
                'stripe_customer_id': stripe_customer_id
            })

        # Tier pricing (in cents, EGP)
        pricing = {
            'premium': {'amount': 500, 'product_name': 'Premium Monthly'},
            'vip': {'amount': 1000, 'product_name': 'VIP Monthly'}
        }

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': pricing[tier]['product_name'],
                        'metadata': {'tier': tier}
                    },
                    'unit_amount': pricing[tier]['amount'],
                    'recurring': {'interval': 'month', 'interval_count': 1}
                },
                'quantity': 1
            }],
            success_url=data.get('success_url', 'app://subscription-success'),
            cancel_url=data.get('cancel_url', 'app://subscription-cancel'),
            metadata={'user_email': user_email, 'tier': tier}
        )

        return jsonify({
            'success': True,
            'checkout_session_id': session.id,
            'checkout_url': session.url
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/subscriptions/current', methods=['GET'])
@require_auth
def get_current_subscription():
    """Get current subscription"""
    try:
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        sub_id = user_data.get('stripe_subscription_id')

        if not sub_id:
            return jsonify({
                'subscription_id': None,
                'tier': user_data.get('tier'),
                'status': 'none'
            }), 200

        sub_doc = db.collection('subscriptions').document(sub_id).get()
        if not sub_doc.exists:
            return jsonify({'error': 'Subscription not found'}), 404

        sub_data = sub_doc.to_dict()
        return jsonify({
            'subscription_id': sub_id,
            'tier': sub_data.get('product_name').split()[0].lower(),
            'status': sub_data.get('status'),
            'current_period_end': sub_data.get('current_period_end'),
            'monthly_amount_egp': sub_data.get('price_amount', 0) / 100,
            'auto_renew': not sub_data.get('cancel_at_period_end', False),
            'cancel_at_period_end': sub_data.get('cancel_at_period_end', False)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/subscriptions/cancel', methods=['POST'])
@require_auth
def cancel_subscription():
    """Cancel subscription (at period end)"""
    try:
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        sub_id = user_data.get('stripe_subscription_id')

        if not sub_id:
            return jsonify({'error': 'No active subscription'}), 400

        # Cancel at period end
        stripe.Subscription.modify(
            sub_id,
            cancel_at_period_end=True
        )

        sub_doc = db.collection('subscriptions').document(sub_id).get()
        final_date = sub_doc.to_dict().get('current_period_end')

        return jsonify({
            'success': True,
            'message': f'Subscription will cancel on {final_date}',
            'final_date': final_date
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ PHASE 5: USER GROUPS ENDPOINTS ============

@app.route('/api/v1/groups', methods=['POST'])
@require_auth
def create_group():
    """Create new group (Premium+ tier only)"""
    try:
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        if user_data.get('tier') not in ['premium', 'vip']:
            return jsonify({'error': 'Premium+ tier required'}), 403

        data = request.get_json()
        group_id = db.collection('user_groups').document().id

        group_data = {
            'id': group_id,
            'name': data.get('name'),
            'description': data.get('description', ''),
            'owner_id': user_email,
            'members': [{
                'uid': user_email,
                'joined_at': datetime.datetime.now(datetime.timezone.utc),
                'role': 'owner'
            }],
            'member_count': 1,
            'deals_shared_today': 0,
            'daily_share_limit': data.get('daily_share_limit', 10),
            'is_public': data.get('is_public', True),
            'visibility': data.get('visibility', 'public'),
            'created_at': datetime.datetime.now(datetime.timezone.utc),
            'updated_at': datetime.datetime.now(datetime.timezone.utc)
        }

        db.collection('user_groups').document(group_id).set(group_data)

        return jsonify({
            'success': True,
            'group': {
                'id': group_id,
                'name': group_data['name'],
                'owner_id': user_email,
                'member_count': 1,
                'created_at': group_data['created_at'].isoformat()
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/groups/<group_id>', methods=['GET'])
@require_auth
def get_group(group_id):
    """Get group details"""
    try:
        user_email = request.current_user.get('email')
        group_doc = db.collection('user_groups').document(group_id).get()

        if not group_doc.exists:
            return jsonify({'error': 'Group not found'}), 404

        group_data = group_doc.to_dict()
        member_uids = [m.get('uid') for m in group_data.get('members', [])]
        user_is_member = user_email in member_uids

        return jsonify({
            'id': group_id,
            'name': group_data.get('name'),
            'description': group_data.get('description'),
            'owner_id': group_data.get('owner_id'),
            'member_count': group_data.get('member_count'),
            'is_public': group_data.get('is_public'),
            'daily_share_limit': group_data.get('daily_share_limit'),
            'deals_shared_today': group_data.get('deals_shared_today', 0),
            'user_is_member': user_is_member,
            'user_role': 'owner' if group_data.get('owner_id') == user_email else 'member',
            'created_at': group_data.get('created_at').isoformat() if group_data.get('created_at') else None
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/groups/<group_id>/members', methods=['POST'])
@require_auth
def manage_group_members(group_id):
    """Join or invite member to group"""
    try:
        user_email = request.current_user.get('email')
        data = request.get_json()
        action = data.get('action')

        group_doc = db.collection('user_groups').document(group_id).get()
        if not group_doc.exists:
            return jsonify({'error': 'Group not found'}), 404

        group_data = group_doc.to_dict()
        members = group_data.get('members', [])
        member_uids = [m.get('uid') for m in members]

        if action == 'join':
            if user_email in member_uids:
                return jsonify({'error': 'Already a member'}), 400

            members.append({
                'uid': user_email,
                'joined_at': datetime.datetime.now(datetime.timezone.utc),
                'role': 'member'
            })

            db.collection('user_groups').document(group_id).update({
                'members': members,
                'member_count': len(members),
                'updated_at': datetime.datetime.now(datetime.timezone.utc)
            })

            return jsonify({'success': True, 'message': 'Joined group successfully'}), 200

        elif action == 'invite':
            invite_user_id = data.get('invite_user_id')
            if invite_user_id in member_uids:
                return jsonify({'error': 'User already in group'}), 400

            members.append({
                'uid': invite_user_id,
                'joined_at': datetime.datetime.now(datetime.timezone.utc),
                'role': 'member'
            })

            db.collection('user_groups').document(group_id).update({
                'members': members,
                'member_count': len(members),
                'updated_at': datetime.datetime.now(datetime.timezone.utc)
            })

            return jsonify({'success': True, 'message': 'User invited successfully'}), 200

        else:
            return jsonify({'error': 'Invalid action'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/groups/<group_id>/members/<user_id>', methods=['DELETE'])
@require_auth
def remove_group_member(group_id, user_id):
    """Remove member from group"""
    try:
        user_email = request.current_user.get('email')
        group_doc = db.collection('user_groups').document(group_id).get()

        if not group_doc.exists:
            return jsonify({'error': 'Group not found'}), 404

        group_data = group_doc.to_dict()

        # Only owner or the user themselves can remove
        if group_data.get('owner_id') != user_email and user_email != user_id:
            return jsonify({'error': 'Not authorized'}), 403

        members = group_data.get('members', [])
        members = [m for m in members if m.get('uid') != user_id]

        db.collection('user_groups').document(group_id).update({
            'members': members,
            'member_count': len(members),
            'updated_at': datetime.datetime.now(datetime.timezone.utc)
        })

        return jsonify({'success': True, 'message': 'User removed from group'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ PHASE 5: DEAL GIFTING ENDPOINTS ============

@app.route('/api/v1/deals/<deal_id>/gift', methods=['POST'])
@require_auth
def gift_deal(deal_id):
    """Send deal as gift (Premium+ only)"""
    try:
        user_email = request.current_user.get('email')
        user_doc = db.collection('users').document(user_email).get()

        if not user_doc.exists:
            return jsonify({'error': 'User not found'}), 404

        user_data = user_doc.to_dict()
        if user_data.get('tier') not in ['premium', 'vip']:
            return jsonify({'error': 'Premium+ tier required'}), 403

        data = request.get_json()
        to_user_id = data.get('to_user_id')
        message = data.get('message', '')

        # Get deal data
        deal_doc = db.collection('deals').document(deal_id).get()
        if not deal_doc.exists:
            return jsonify({'error': 'Deal not found'}), 404

        deal_data = deal_doc.to_dict()
        gift_id = db.collection('deal_gifts').document().id

        gift_data = {
            'id': gift_id,
            'from_user_id': user_email,
            'to_user_id': to_user_id,
            'deal_id': deal_id,
            'message': message[:200] if message else '',
            'status': 'sent',
            'expires_at': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30),
            'viewed_at': None,
            'claimed_at': None,
            'created_at': datetime.datetime.now(datetime.timezone.utc),
            'metadata': {
                'deal_title': deal_data.get('title', ''),
                'deal_discount_percent': deal_data.get('discount_percent', 0),
                'deal_current_price': deal_data.get('current_price', 0)
            }
        }

        db.collection('deal_gifts').document(gift_id).set(gift_data)

        return jsonify({
            'success': True,
            'gift': {
                'gift_id': gift_id,
                'to_user_id': to_user_id,
                'deal_id': deal_id,
                'message': message,
                'status': 'sent',
                'expires_at': gift_data['expires_at'].isoformat(),
                'created_at': gift_data['created_at'].isoformat()
            }
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/gifts/received', methods=['GET'])
@require_auth
def get_received_gifts():
    """List received gifts"""
    try:
        user_email = request.current_user.get('email')
        gifts_snap = db.collection('deal_gifts').where('to_user_id', '==', user_email).stream()
        gifts = []

        for doc in gifts_snap:
            gift_data = doc.to_dict()
            gifts.append({
                'gift_id': gift_data.get('id'),
                'from_user_id': gift_data.get('from_user_id'),
                'from_user_name': gift_data.get('from_user_name', 'User'),
                'deal_id': gift_data.get('deal_id'),
                'deal_title': gift_data.get('metadata', {}).get('deal_title'),
                'deal_current_price': gift_data.get('metadata', {}).get('deal_current_price'),
                'message': gift_data.get('message'),
                'status': gift_data.get('status'),
                'expires_at': gift_data.get('expires_at').isoformat() if gift_data.get('expires_at') else None,
                'created_at': gift_data.get('created_at').isoformat() if gift_data.get('created_at') else None
            })

        unredeemed = sum(1 for g in gifts if g.get('status') != 'claimed')
        return jsonify({'gifts': gifts, 'total_unredeemed': unredeemed}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ PHASE 5: REFERRAL SYSTEM ENDPOINTS ============

@app.route('/api/v1/referrals/activate', methods=['POST'])
def activate_referral():
    """Activate referral code on signup (Public)"""
    try:
        data = request.get_json()
        referral_code = data.get('referral_code')
        new_user_id = data.get('new_user_id')

        if not referral_code or not new_user_id:
            return jsonify({'error': 'referral_code and new_user_id required'}), 400

        # Find referral record
        ref_snap = db.collection('referrals').where('referral_code', '==', referral_code).limit(1).stream()
        ref_docs = list(ref_snap)

        if not ref_docs:
            return jsonify({'error': 'Invalid referral code'}), 400

        ref_doc = ref_docs[0].to_dict()
        referrer_id = ref_doc.get('referrer_id')

        # Update referral record
        db.collection('referrals').document(ref_docs[0].id).update({
            'referee_id': new_user_id,
            'status': 'activated',
            'activated_at': datetime.datetime.now(datetime.timezone.utc)
        })

        # Give referrer 1 week premium
        referrer_user = db.collection('users').document(referrer_id).get()
        if referrer_user.exists:
            db.collection('users').document(referrer_id).update({
                'tier': 'premium',
                'subscription_active': True,
                'subscription_renewal_date': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
            })

        return jsonify({
            'success': True,
            'message': 'Referral activated',
            'reward': '7-day premium trial'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/v1/referrals/check-code', methods=['GET'])
def check_referral_code():
    """Validate referral code before signup (Public)"""
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': 'code parameter required'}), 400

        ref_snap = db.collection('referrals').where('referral_code', '==', code).limit(1).stream()
        ref_docs = list(ref_snap)

        if not ref_docs:
            return jsonify({'valid': False}), 200

        ref_data = ref_docs[0].to_dict()

        # Check if expired
        expires_at = ref_data.get('expires_at')
        if expires_at and datetime.datetime.now(datetime.timezone.utc) > expires_at:
            return jsonify({'valid': False, 'reason': 'Code expired'}), 200

        # Get referrer name
        referrer_doc = db.collection('users').document(ref_data.get('referrer_id')).get()
        referrer_name = referrer_doc.to_dict().get('name', 'User') if referrer_doc.exists else 'User'

        return jsonify({
            'valid': True,
            'referrer_name': referrer_name,
            'reward_description': 'Get 1 week of Premium'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ HELPER FUNCTIONS ============

def generate_referral_code():
    """Generate unique referral code"""
    import random
    import string
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"DEAL{code}"


# ============ STRIPE WEBHOOK HANDLER ============

@app.route('/webhooks/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data(as_text=True)
        sig_header = request.headers.get('stripe-signature')

        print(f"[Webhook] Received POST request")
        print(f"[Webhook] Signature header: {sig_header[:20] if sig_header else 'MISSING'}...")
        print(f"[Webhook] STRIPE_WEBHOOK_SECRET configured: {bool(STRIPE_WEBHOOK_SECRET)}")

        if not STRIPE_WEBHOOK_SECRET:
            print(f"[Webhook] ERROR: Webhook secret not configured!")
            return jsonify({'error': 'Webhook secret not configured'}), 500

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            print(f"[Webhook] ✓ Signature verified")
        except stripe.error.SignatureVerificationError as e:
            print(f"[Webhook] ✗ Signature verification failed: {e}")
            return jsonify({'error': 'Invalid signature'}), 400

        event_type = event['type']
        print(f"[Webhook] Event type: {event_type}")

        if event_type == 'customer.created':
            handle_customer_created(event['data']['object'])

        elif event_type == 'customer.subscription.created':
            handle_subscription_created(event['data']['object'])

        elif event_type == 'customer.subscription.updated':
            handle_subscription_updated(event['data']['object'])

        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(event['data']['object'])

        elif event_type == 'charge.succeeded':
            handle_charge_succeeded(event['data']['object'])

        elif event_type == 'charge.failed':
            handle_charge_failed(event['data']['object'])

        print(f"[Webhook] Logging event...")
        # Log webhook
        log_webhook(event['id'], event_type, 'success', 200, event)
        print(f"[Webhook] ✓ Event logged successfully")

        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"[Webhook] ✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        log_webhook(None, event_type if 'event_type' in locals() else 'unknown', 'failed', 500, str(e))
        return jsonify({'error': str(e)}), 500


def handle_customer_created(customer):
    """Handle Stripe customer.created event"""
    try:
        email = customer.get('email')
        if email:
            user_doc = db.collection('users').document(email).get()
            if user_doc.exists:
                db.collection('users').document(email).update({
                    'stripe_customer_id': customer['id']
                })
    except Exception as e:
        print(f"Error handling customer.created: {e}")


def handle_subscription_created(subscription):
    """Handle Stripe subscription.created event"""
    try:
        customer_id = subscription.get('customer')
        user_email = subscription.get('metadata', {}).get('user_email')

        # Get product/tier name
        line_items = subscription.get('items', {}).get('data', [])
        product_name = 'Unknown'
        price_amount = 0

        if line_items:
            product_id = line_items[0].get('price', {}).get('product')
            price_amount = line_items[0].get('price', {}).get('unit_amount', 0)

            if product_id:
                product = stripe.Product.retrieve(product_id)
                product_name = product.get('name', 'Unknown')

        # Extract tier from product name
        tier = 'premium' if 'premium' in product_name.lower() else 'vip'

        # Create subscription record
        sub_data = {
            'id': subscription['id'],
            'user_id': user_email,
            'stripe_customer_id': customer_id,
            'product_id': line_items[0].get('price', {}).get('product') if line_items else None,
            'product_name': product_name,
            'price_amount': price_amount,
            'currency': 'egp',
            'status': subscription.get('status'),
            'billing_cycle_anchor': datetime.datetime.fromtimestamp(subscription.get('billing_cycle_anchor')),
            'current_period_start': datetime.datetime.fromtimestamp(subscription.get('current_period_start')),
            'current_period_end': datetime.datetime.fromtimestamp(subscription.get('current_period_end')),
            'cancel_at_period_end': subscription.get('cancel_at_period_end', False),
            'created_at': datetime.datetime.now(datetime.timezone.utc),
            'updated_at': datetime.datetime.now(datetime.timezone.utc)
        }

        db.collection('subscriptions').document(subscription['id']).set(sub_data)

        # Update user
        if user_email:
            limit_map = {'premium': 500, 'vip': 99999}
            db.collection('users').document(user_email).update({
                'stripe_subscription_id': subscription['id'],
                'subscription_active': True,
                'tier': tier,
                'subscription_start_date': sub_data['current_period_start'],
                'subscription_renewal_date': sub_data['current_period_end'],
                'daily_deal_limit': limit_map.get(tier, 500)
            })
    except Exception as e:
        print(f"Error handling subscription.created: {e}")


def handle_subscription_updated(subscription):
    """Handle Stripe subscription.updated event"""
    try:
        sub_id = subscription['id']

        sub_doc = db.collection('subscriptions').document(sub_id).get()
        if sub_doc.exists:
            db.collection('subscriptions').document(sub_id).update({
                'status': subscription.get('status'),
                'cancel_at_period_end': subscription.get('cancel_at_period_end', False),
                'current_period_end': datetime.datetime.fromtimestamp(subscription.get('current_period_end')),
                'updated_at': datetime.datetime.now(datetime.timezone.utc)
            })
    except Exception as e:
        print(f"Error handling subscription.updated: {e}")


def handle_subscription_deleted(subscription):
    """Handle Stripe subscription.deleted event"""
    try:
        sub_id = subscription['id']
        user_email = subscription.get('metadata', {}).get('user_email')

        # Mark as canceled
        db.collection('subscriptions').document(sub_id).update({
            'status': 'canceled',
            'updated_at': datetime.datetime.now(datetime.timezone.utc)
        })

        # Downgrade user to free
        if user_email:
            db.collection('users').document(user_email).update({
                'subscription_active': False,
                'tier': 'free',
                'daily_deal_limit': 50,
                'stripe_subscription_id': None
            })
    except Exception as e:
        print(f"Error handling subscription.deleted: {e}")


def handle_charge_succeeded(charge):
    """Handle Stripe charge.succeeded event"""
    try:
        # Log successful charge
        pass
    except Exception as e:
        print(f"Error handling charge.succeeded: {e}")


def handle_charge_failed(charge):
    """Handle Stripe charge.failed event"""
    try:
        # Log failed charge, mark subscription as past_due
        pass
    except Exception as e:
        print(f"Error handling charge.failed: {e}")


def log_webhook(event_id, event_type, status, response_code, payload):
    """Log webhook event for auditing"""
    if not db:
        print(f"Warning: Firebase not initialized, cannot log webhook event: {event_type}")
        return

    try:
        log_id = db.collection('webhooks_log').document().id
        db.collection('webhooks_log').document(log_id).set({
            'event_id': event_id,
            'event_type': event_type,
            'status': status,
            'response_code': response_code,
            'created_at': datetime.datetime.now(datetime.timezone.utc)
        })
        print(f"✓ Webhook logged: {event_type}")
    except Exception as e:
        print(f"Error logging webhook: {e}")


# ============ HEALTH CHECK ENDPOINT ============

@app.route('/', methods=['GET', 'POST', 'HEAD'])
def health_check():
    """Keep Render alive"""
    return 'DealHunter Scraper is running!', 200


# ============ BACKGROUND SCRAPER ============

def run_scheduler():
    from scraper import run_scraper, INTERVAL
    print("Scheduler started — running first scrape now...")
    run_scraper()
    schedule.every(INTERVAL).minutes.do(run_scraper)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    print("DealHunter Egypt Starting...")
    scraper_thread = threading.Thread(target=run_scheduler, daemon=True)
    scraper_thread.start()

    port = int(os.environ.get("PORT", 10000))
    print(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

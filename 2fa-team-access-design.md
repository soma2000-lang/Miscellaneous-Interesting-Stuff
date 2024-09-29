# 2FA Design for Team Access

## 1. Overview

This design outlines a flexible 2FA system that can be integrated into existing team access management systems. It provides multiple 2FA options to cater to different team preferences and security requirements.

## 2. 2FA Methods

### 2.1 Time-Based One-Time Password (TOTP)

- Use TOTP algorithm (RFC 6238)
- Compatible with apps like Google Authenticator, Authy

```python
import pyotp

def generate_totp_secret():
    return pyotp.random_base32()

def verify_totp(secret, token):
    totp = pyotp.TOTP(secret)
    return totp.verify(token)

# Usage
secret = generate_totp_secret()
# Store secret securely for the user

# During verification
user_token = "123456"  # Token entered by user
is_valid = verify_totp(secret, user_token)
```

### 2.2 SMS-Based OTP

- Send a short-lived OTP via SMS
- Implement rate limiting to prevent abuse

```python
import random
import redis
from twilio.rest import Client

redis_client = redis.Redis(host='localhost', port=6379, db=0)
twilio_client = Client('your_account_sid', 'your_auth_token')

def send_sms_otp(phone_number):
    otp = str(random.randint(100000, 999999))
    redis_client.setex(f"sms_otp:{phone_number}", 300, otp)  # 5-minute expiry
    
    twilio_client.messages.create(
        body=f"Your OTP is: {otp}",
        from_='your_twilio_number',
        to=phone_number
    )

def verify_sms_otp(phone_number, otp):
    stored_otp = redis_client.get(f"sms_otp:{phone_number}")
    if stored_otp and stored_otp.decode() == otp:
        redis_client.delete(f"sms_otp:{phone_number}")
        return True
    return False
```

### 2.3 Email-Based OTP

- Send OTP via email
- Useful for users without mobile devices or in areas with poor cellular coverage

```python
import smtplib
from email.mime.text import MIMEText
import random
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def send_email_otp(email):
    otp = str(random.randint(100000, 999999))
    redis_client.setex(f"email_otp:{email}", 600, otp)  # 10-minute expiry
    
    msg = MIMEText(f"Your OTP is: {otp}")
    msg['Subject'] = "Your 2FA Code"
    msg['From'] = "noreply@yourcompany.com"
    msg['To'] = email
    
    s = smtplib.SMTP('localhost')
    s.send_message(msg)
    s.quit()

def verify_email_otp(email, otp):
    stored_otp = redis_client.get(f"email_otp:{email}")
    if stored_otp and stored_otp.decode() == otp:
        redis_client.delete(f"email_otp:{email}")
        return True
    return False
```

### 2.4 Push Notification-Based Approval

- Send push notifications to a company mobile app for approval
- Provide a more user-friendly 2FA experience

```python
import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("path/to/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

def send_push_notification(device_token, login_attempt_id):
    message = messaging.Message(
        data={
            'login_attempt_id': login_attempt_id,
            'action': 'approve_login'
        },
        token=device_token,
    )
    response = messaging.send(message)
    return response

# In your approval handling endpoint
def handle_push_approval(login_attempt_id, approved):
    # Verify the login attempt is still valid and not expired
    # Update the login status based on the approval
    pass
```

## 3. User Enrollment

1. During initial setup or security settings update:
   - Allow users to choose their preferred 2FA method
   - For TOTP, generate and display QR code for easy app setup
   - For other methods, verify the contact information (phone/email)

2. Require immediate verification of the chosen 2FA method

```python
def enroll_user_2fa(user_id, method, contact_info=None):
    if method == 'totp':
        secret = generate_totp_secret()
        # Store secret securely associated with user_id
        qr_code = pyotp.totp.TOTP(secret).provisioning_uri(name=user_id, issuer_name="YourCompany")
        return qr_code
    elif method == 'sms':
        # Verify phone number
        send_sms_otp(contact_info)
    elif method == 'email':
        # Verify email
        send_email_otp(contact_info)
    elif method == 'push':
        # Register device token
        pass
    
    # Store user's chosen method
    store_user_2fa_preference(user_id, method, contact_info)
```

## 4. Authentication Flow

1. User enters username and password
2. If credentials are valid, initiate 2FA based on user's preferred method
3. Verify 2FA input
4. Grant access upon successful 2FA verification

```python
def login(username, password):
    user = validate_credentials(username, password)
    if not user:
        return "Invalid credentials"
    
    method = get_user_2fa_method(user.id)
    if method == 'totp':
        return "Please enter your TOTP code"
    elif method == 'sms':
        send_sms_otp(user.phone)
        return "OTP sent to your phone"
    elif method == 'email':
        send_email_otp(user.email)
        return "OTP sent to your email"
    elif method == 'push':
        send_push_notification(user.device_token, generate_login_attempt_id())
        return "Approval request sent to your device"

def verify_2fa(user_id, method, token):
    if method == 'totp':
        secret = get_user_totp_secret(user_id)
        return verify_totp(secret, token)
    elif method == 'sms':
        phone = get_user_phone(user_id)
        return verify_sms_otp(phone, token)
    elif method == 'email':
        email = get_user_email(user_id)
        return verify_email_otp(email, token)
    elif method == 'push':
        # This would be handled asynchronously via the push notification response
        pass
```

## 5. Security Considerations

1. **Backup Codes**: Generate and provide backup codes for account recovery

```python
import secrets

def generate_backup_codes(user_id, num_codes=8):
    codes = [secrets.token_hex(4) for _ in range(num_codes)]
    # Store hashed versions of these codes associated with the user
    store_backup_codes(user_id, [hash_code(code) for code in codes])
    return codes

def verify_backup_code(user_id, entered_code):
    stored_codes = get_stored_backup_codes(user_id)
    for stored_code in stored_codes:
        if verify_hash(entered_code, stored_code):
            remove_used_backup_code(user_id, stored_code)
            return True
    return False
```

2. **Rate Limiting**: Implement rate limiting on 2FA attempts to prevent brute force attacks

3. **Secure Storage**: Store 2FA secrets and user preferences securely (encrypted at rest)

4. **Audit Logging**: Log all 2FA-related events for security analysis

```python
import logging

logging.basicConfig(filename='2fa_events.log', level=logging.INFO)

def log_2fa_event(user_id, event_type, details):
    logging.info(f"User {user_id}: {event_type} - {details}")

# Usage
log_2fa_event(user.id, "2FA_ATTEMPT", f"Method: {method}, Success: {success}")
```

5. **Session Management**: Implement secure session handling after successful 2FA

## 6. User Experience Considerations

1. Allow users to change their 2FA method
2. Provide clear instructions for each 2FA method
3. Implement a grace period for new devices or locations before requiring 2FA
4. Offer remember-this-device option for trusted devices

## 7. Implementation Strategy

1. Choose a secure way to store 2FA secrets (e.g., encrypted database fields)
2. Implement each 2FA method one by one, starting with TOTP
3. Integrate 2FA into the existing authentication flow
4. Develop user interfaces for 2FA enrollment and verification
5. Implement backup and recovery mechanisms
6. Conduct thorough security testing and auditing
7. Gradually roll out to teams, starting with IT and security teams
8. Provide user training and documentation


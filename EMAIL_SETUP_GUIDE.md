# Email Notification Feature - Setup Guide

## Overview

The email notification feature automatically sends welcome emails to students when their accounts are created. This includes:
- Student's full name
- BSU email/username (SR-Code)
- Temporary password
- Login instructions

## Implementation Details

### Files Created/Modified

1. **academics/email_service.py** (NEW)
   - `send_student_account_welcome_email()`: Main function to send emails
   - `send_student_account_welcome_email_async()`: Non-blocking wrapper
   - Handles errors gracefully without blocking student creation

2. **templates/academics/emails/student_welcome.html** (NEW)
   - Professional HTML email template
   - Contains security notices and login instructions
   - Responsive design

3. **config/settings.py** (MODIFIED)
   - Added email backend configuration
   - Supports both development (console) and production (SMTP)
   - Environment variable support for SMTP settings

4. **academics/views.py** (MODIFIED)
   - Imported email service
   - Added email sending after student account creation
   - Email sent after transaction completes to ensure data is committed

5. **academics/student_import_services.py** (MODIFIED)
   - Integrated email sending into bulk import process
   - Errors in email sending don't block the import
   - Logs any email failures for troubleshooting

## Configuration

### Development Environment (Console Backend)

The default configuration in development mode prints emails to the console instead of sending them. No additional setup is required.

### Production Environment (SMTP Backend)

Add the following environment variables to your `.env` file:

```bash
# Email Configuration
EMAIL_HOST=smtp.gmail.com              # Your SMTP server
EMAIL_PORT=587                         # SMTP port
EMAIL_USE_TLS=True                     # Use TLS encryption
EMAIL_HOST_USER=your-email@gmail.com   # SMTP username
EMAIL_HOST_PASSWORD=your-app-password  # SMTP password (use app-specific for Gmail)
DEFAULT_FROM_EMAIL=noreply@batstate-u.edu.ph  # Sender email
SITE_URL=https://yourdomain.com        # Your site URL (for email links)
```

### Gmail Configuration (Recommended)

1. Enable 2-Factor Authentication on your Gmail account
2. Generate an App Password:
   - Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   - Select "Mail" and "Other (custom name): Auto POS"
   - Copy the 16-character password
3. Use the app password as `EMAIL_HOST_PASSWORD` in your `.env` file

### Other SMTP Providers

For other email providers (SendGrid, Mailgun, AWS SES, etc.), adjust the following settings:

- `EMAIL_HOST`: Provider's SMTP host
- `EMAIL_PORT`: Provider's SMTP port (usually 587 or 465)
- `EMAIL_USE_TLS`: Use `True` for port 587, `False` for port 465 (use SSL instead)
- `EMAIL_HOST_USER`: Your account username
- `EMAIL_HOST_PASSWORD`: Your account password or API key

## How It Works

### Single Student Registration Flow

1. Admin fills out the student registration form
2. Form is validated in `academics/forms.py`
3. User and Student records are created inside a database transaction
4. After transaction commits, `send_student_account_welcome_email_async()` is called
5. Email is sent with credentials
6. If email sending fails, it's logged but doesn't affect student creation
7. Success page is displayed to admin

### Bulk Student Import Flow

1. Admin uploads a CSV/Excel file with student records
2. File is validated and previewed
3. Admin confirms the import
4. `save_student_import_rows()` creates all students
5. For each student created, an email is sent
6. Any email failures are logged but don't interrupt the import
7. Import summary is displayed

## Error Handling

The email service includes robust error handling:

- **Silent Failures**: Email errors don't block student creation
- **Logging**: All email operations are logged to Django's logger
- **Retryable**: Could be extended with Celery for automatic retry

### Monitoring Email Failures

Check Django logs for email-related errors:

```python
# In Django shell or management command
from django.core.logging import getLogger
logger = getLogger('academics.email_service')
```

## Testing

### Development Environment

Emails are printed to the console by default. You'll see output like:

```
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: 7bit
Subject: Welcome to Batangas State University - Auto POS System
From: noreply@autopos.test
To: 23-02639@g.batstate-u.edu.ph
Date: Wed, 22 May 2026 10:30:00 -0000
Message-ID: <...>

Hello JENNIE RUBY JANE KIM,
...
```

### Production Testing

1. Create a test user account in the admin panel
2. Check the student's email inbox for the welcome email
3. Verify all information is correct
4. Test the login with provided credentials

### Django Email Tests

Run the email tests:

```bash
python manage.py test academics.tests
```

## Future Enhancements

### 1. Async Email with Celery

For truly non-blocking email sending:

```python
from celery import shared_task

@shared_task
def send_welcome_email_task(user_id, sr_code, temporary_password):
    user = User.objects.get(id=user_id)
    send_student_account_welcome_email(user, sr_code, temporary_password)
```

Then in views:
```python
send_welcome_email_task.delay(student_user.id, sr_code, temporary_password)
```

### 2. Email Templates for Other Events

- Password reset notifications
- Course registration confirmations
- Grade submission notifications
- System maintenance alerts

### 3. Batch Email Resend

Create a management command to resend emails to students:

```bash
python manage.py resend_welcome_emails --year=2023 --status=regular
```

### 4. Email Delivery Tracking

Monitor email delivery with providers like SendGrid or Mailgun

### 5. Custom Email Styling

Allow admins to customize email templates through the admin panel

## Troubleshooting

### Emails Not Sending in Production

1. **Check Environment Variables**
   ```bash
   echo $EMAIL_HOST
   echo $EMAIL_HOST_USER
   ```

2. **Test SMTP Connection**
   ```bash
   python manage.py shell
   >>> from django.core.mail import send_mail
   >>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
   ```

3. **Check Django Logs**
   - Look for authentication errors
   - Check SMTP connection timeouts
   - Verify firewall/network access to SMTP server

4. **Verify Email Settings**
   - Confirm `DEFAULT_FROM_EMAIL` is a valid email
   - Check `EMAIL_HOST_USER` credentials
   - Verify `EMAIL_PORT` matches your provider

### Emails Going to Spam

1. **Add SPF Record**
   ```
   v=spf1 include:sendgrid.net ~all
   ```

2. **Add DKIM Signature**
   - Provided by your email provider

3. **Add DMARC Policy**
   ```
   v=DMARC1; p=quarantine; rua=mailto:admin@yourdomain.com
   ```

## Support

For issues or questions, contact:
- Django Documentation: https://docs.djangoproject.com/en/stable/topics/email/
- Your SMTP Provider's Support

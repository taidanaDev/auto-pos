# Email Feature - Quick Start Guide

## For Local Development

### 1. No Setup Required!
Emails will print to the console automatically.

### 2. Test It
1. Run development server: `python manage.py runserver`
2. Go to Admin Dashboard → Student Registration
3. Fill form and submit
4. Check console for email output

### 3. Verify Email Content
```
Content-Type: text/plain; charset="utf-8"
Subject: Welcome to Batangas State University - Auto POS System
From: noreply@autopos.test
To: 23-02639@g.batstate-u.edu.ph

Hello JENNIE RUBY JANE KIM,
Welcome to the Automated Program of Study (Auto POS) System!

Login Credentials:
SR-Code: 23-02639
Email/Username: 23-02639@g.batstate-u.edu.ph
Temporary Password: 23-02639kim
```

---

## For Production Deployment

### 1. Set Environment Variables

Create/update `.env` file:

```bash
# Email Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=noreply@batstate-u.edu.ph
SITE_URL=https://yourdomain.com
DEBUG=False
```

### 2. Get Gmail App Password

1. Go to https://myaccount.google.com/apppasswords
2. Select Mail + Other (custom name): Auto POS
3. Copy the 16-character password
4. Paste into `.env` as `EMAIL_HOST_PASSWORD`

### 3. Deploy & Test

```bash
# Test SMTP connection
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
# Should return 1

# Run tests
python manage.py test academics.tests_email
```

### 4. Monitor Production

Check logs for email errors:
```bash
tail -f logs/django.log | grep email
```

---

## Key Files

| File | Purpose |
|------|---------|
| `academics/email_service.py` | Email sending logic |
| `templates/academics/emails/student_welcome.html` | Email template |
| `config/settings.py` | Email backend config |
| `academics/views.py` | Manual registration integration |
| `academics/student_import_services.py` | Bulk import integration |
| `academics/tests_email.py` | Test suite |

---

## Testing

### Manual Test
1. Create student account manually
2. Check console (dev) or inbox (production)
3. Verify all 4 required fields present

### Automated Test
```bash
python manage.py test academics.tests_email -v 2
```

### Bulk Import Test
1. Prepare CSV: `sr_code, first_name, last_name, email, curriculum_code, section_code, status`
2. Upload via Admin Dashboard → Student Import
3. Verify each student received email

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No emails in development | Check console output in terminal |
| SMTP connection failed | Verify EMAIL_HOST, EMAIL_PORT, credentials |
| Emails in spam | Add SPF/DKIM records for domain |
| Template not found | Ensure file at `templates/academics/emails/student_welcome.html` |
| 401 Auth error | Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD |

---

## What Happens When...

### ✅ Student Created Successfully
- Email sent immediately (async)
- Student can log in with credentials
- Success page shows credentials

### ❌ Email Sending Fails
- Student account still created
- Error logged to Django logs
- Doesn't block registration

### 📤 Bulk Import
- Emails sent for each student
- Import completes even if some emails fail
- Summary shows created count

---

## Security Notes

⚠️ **Important:**
- Don't commit `.env` file (add to `.gitignore`)
- Use app passwords, not main Gmail password
- SMTP credentials are sensitive - store securely
- Template includes security warnings for students

---

## Support

See full documentation:
- Setup details: `EMAIL_SETUP_GUIDE.md`
- Implementation: `EMAIL_IMPLEMENTATION_SUMMARY.md`
- Tests: `academics/tests_email.py`

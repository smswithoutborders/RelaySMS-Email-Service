# RelaySMS-Email-Service

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
vi .env
```

**Required Configuration:**

- `API_KEY`: Your secure API key for authentication

**Optional Configuration:**

- `SIMPLELOGIN_API_KEY`: Required only if using SimpleLogin alias mode
- `SMTP_CREDS_FILE`: Path to SMTP credentials JSON file (default: smtp_creds.json)

### 3. Configure SMTP Credentials

```bash
# Copy example SMTP credentials file
cp smtp_creds.example.json smtp_creds.json

# Edit smtp_creds.json with your SMTP accounts
vi smtp_creds.json
```

**SMTP Credentials Format:**

```json
{
  "smtp_accounts": [
    {
      "from_email": "user1@example.com",
      "host": "smtp.gmail.com",
      "port": 587,
      "username": "user1@example.com",
      "password": "your-password-here",
      "enable_tls": true
    },
    {
      "from_email": "noreply@yourdomain.com",
      "host": "smtp.outlook.com",
      "port": 587,
      "username": "noreply@yourdomain.com",
      "password": "your-password-here",
      "enable_tls": true
    }
  ]
}
```

### 4. Start the Application

```bash
# Using the start script
./start.sh

# Or directly with uvicorn
uvicorn app:app --host 127.0.0.1 --port 8080
```

The API will be available at `http://127.0.0.1:8080`

## API Documentation

### Authentication

All endpoints require authentication via the `Authorization` header:

```
Authorization: Bearer your-api-key
```

### Send Email Endpoint

**POST** `/v1/send`

Send an email through SimpleLogin alias or direct SMTP.

#### Two Sending States

**State 1: SimpleLogin Alias Mode**

When `alias` object is provided, the service:

1. Extracts prefix and domain from `from_email` (e.g., `support@yourdomain.com` → prefix: `support`, domain: `yourdomain.com`)
2. Creates or retrieves the SimpleLogin alias using the mailbox
3. Creates a contact and gets the reverse alias
4. Sends email using SMTP credentials from `alias.mailbox`

```json
{
  "to_email": "recipient@example.com",
  "subject": "Welcome!",
  "body": "Hello, welcome to our service!",
  "from_email": "support@yourdomain.com",
  "alias": {
    "mailbox": "noreply@yourdomain.com"
  }
}
```

**State 2: Plain SMTP Mode**

When only `from_email` is provided (no `alias` object):

1. Looks up SMTP credentials for `from_email` in `smtp_creds.json`
2. Sends email directly to recipient

```json
{
  "to_email": "recipient@example.com",
  "subject": "Welcome!",
  "body": "Hello, welcome to our service!",
  "from_email": "user1@example.com"
}
```

#### Request Body Fields

| Field              | Type   | Required | Description                                    |
| ------------------ | ------ | -------- | ---------------------------------------------- |
| `to_email`         | string | Yes      | Recipient email address                        |
| `subject`          | string | Yes      | Email subject line                             |
| `body`             | string | Cond.    | Email body (required if no template)           |
| `template`         | string | Cond.    | Template name (required if no body)            |
| `substitutions`    | object | No       | Variables for template/subject rendering       |
| `from_name`        | string | No       | Sender display name                            |
| `from_email`       | string | Yes      | Sender email (for alias prefix/domain or SMTP) |
| `alias`            | object | No       | If provided, use SimpleLogin alias mode        |
| `alias.mailbox`    | string | Cond.    | Mailbox email (must have SMTP credentials)     |

**Response:**

```json
{
  "success": true,
  "message": "Email sent successfully at 2024-01-15 10:30:00"
}
```

#### Example Requests

**SimpleLogin Alias Mode:**

```bash
curl -X POST "http://127.0.0.1:8080/v1/send" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "customer@example.com",
    "subject": "Welcome!",
    "body": "Hello, welcome to our service!",
    "from_email": "support@yourdomain.com",
    "alias": {
      "mailbox": "noreply@yourdomain.com"
    }
  }'
```

**Plain SMTP Mode:**

```bash
curl -X POST "http://127.0.0.1:8080/v1/send" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "customer@example.com",
    "subject": "Account Update",
    "body": "Your account has been updated successfully.",
    "from_email": "user1@example.com"
  }'
```

**Using Templates:**

```bash
curl -X POST "http://127.0.0.1:8080/v1/send" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "customer@example.com",
    "subject": "Welcome {{ name }}!",
    "template": "welcome",
    "substitutions": {
      "name": "John Doe",
      "project_name": "MyApp"
    },
    "from_email": "support@yourdomain.com",
    "alias": {
      "mailbox": "noreply@yourdomain.com"
    }
  }'
```

### Email Templates

Place HTML email templates in the `email_templates/` directory. Use Jinja2 syntax for variable substitution:

```html
<!-- email_templates/welcome.html -->
<!DOCTYPE html>
<html>
<head>
    <title>Welcome</title>
</head>
<body>
    <h1>Welcome, {{ name }}!</h1>
    <p>Thank you for joining {{ project_name }}.</p>
</body>
</html>
```

## Configuration Details

### Environment Variables

| Variable                   | Default                          | Description                                   |
| -------------------------- | -------------------------------- | --------------------------------------------- |
| `HOST`                     | `127.0.0.1`                      | Server host address                           |
| `PORT`                     | `8080`                           | Server port                                   |
| `ENVIRONMENT`              | `development`                    | Environment mode (`development`/`production`) |
| `API_KEY`                  | -                                | **Required** API authentication key           |
| `SIMPLELOGIN_API_KEY`      | -                                | Optional - Required for alias mode            |
| `SIMPLELOGIN_API_BASE_URL` | `https://app.simplelogin.io/api` | SimpleLogin API base URL                      |
| `SMTP_CREDS_FILE`          | `smtp_creds.json`                | Path to SMTP credentials file                 |
| `EMAIL_TEMPLATE_DIR`       | `email_templates`                | Email templates directory                     |

## How It Works

### SimpleLogin Alias Mode Flow

1. Request received with `alias` object and `from_email`
2. Parse `from_email` to extract prefix and domain (e.g., `support@domain.com` → `support` @ `domain.com`)
3. Look up SMTP credentials for `alias.mailbox` in `smtp_creds.json`
4. Create or retrieve SimpleLogin alias: `prefix@domain`
5. Add recipient as contact to the alias
6. Get reverse alias for the contact
7. Send email to reverse alias using mailbox SMTP credentials
8. SimpleLogin forwards email to actual recipient from the alias

### Plain SMTP Mode Flow

1. Request received with only `from_email` (no `alias` object)
2. Look up SMTP credentials for `from_email` in `smtp_creds.json`
3. Send email directly to recipient using those credentials

## Error Handling

The service returns appropriate error messages:

- `Missing Authorization header` - No auth header provided
- `Invalid API key` - Incorrect API key
- `'from_email' is required when using 'alias'` - Missing from_email with alias
- `Either 'alias' or 'from_email' must be provided` - Missing both
- `No SMTP configuration found for <email>` - SMTP credentials not found
- `SimpleLogin API key not configured` - Trying to use alias without API key
- `Invalid from_email format` - from_email doesn't contain @
- `Missing required template variables: <vars>` - Template variables missing
- `Failed to send email. Please try again later.` - SMTP/connection errors

## License

This project is licensed under GPL-3.0-only. See the [LICENSE](LICENSE) file for details.

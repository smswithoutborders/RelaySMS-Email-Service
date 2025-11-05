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
- `SIMPLELOGIN_API_KEY`: Your SimpleLogin API key
- `SMTP_*`: Your SMTP server configuration

### 3. Start the Application

```bash
# Using the start script
./start.sh

# Or directly with uvicorn
uvicorn app:app --host 127.0.0.1 --port 8080
```

The API will be available at `http://127.0.0.1:8080`

## Configuration

### Environment Variables

| Variable                   | Default                          | Description                                   |
| -------------------------- | -------------------------------- | --------------------------------------------- |
| `HOST`                     | `127.0.0.1`                      | Server host address                           |
| `PORT`                     | `8080`                           | Server port                                   |
| `ENVIRONMENT`              | `development`                    | Environment mode (`development`/`production`) |
| `API_KEY`                  | -                                | **Required** API authentication key           |
| `SIMPLELOGIN_API_KEY`      | -                                | **Required** SimpleLogin API key              |
| `SIMPLELOGIN_API_BASE_URL` | `https://app.simplelogin.io/api` | SimpleLogin API base URL                      |
| `SMTP_SERVER`              | -                                | **Required** SMTP server hostname             |
| `SMTP_PORT`                | `587`                            | SMTP server port                              |
| `SMTP_USERNAME`            | -                                | **Required** SMTP username                    |
| `SMTP_PASSWORD`            | -                                | **Required** SMTP password                    |
| `SMTP_ENABLE_TLS`          | `true`                           | Enable TLS for SMTP                           |
| `EMAIL_TEMPLATE_DIR`       | `email_templates`                | Email templates directory                     |

## API Endpoints

### Authentication

All endpoints require authentication via the `Authorization` header:

```
Authorization: Bearer your-api-key
```

### Send Email

**POST** `/v1/send`

Send an email through a SimpleLogin alias.

**Request Body:**

```json
{
  "to_email": "recipient@example.com",
  "subject": "Email Subject",
  "body": "Email content (if not using template)",
  "template": "template_name",
  "substitutions": {
    "variable1": "value1",
    "variable2": "value2"
  },
  "alias_prefix": "custom-prefix",
  "alias_domain": "example.com",
  "sender_mailbox": "sender@yourdomain.com"
}
```

**Response:**

```json
{
  "success": true,
  "message": "Email sent successfully"
}
```

**Example using curl:**

```bash
curl -X POST "http://127.0.0.1:8080/v1/send" \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "to_email": "user@example.com",
    "subject": "Welcome!",
    "template": "welcome",
    "substitutions": {"name": "John Doe"},
    "alias_prefix": "welcome",
    "alias_domain": "yourdomain.com",
    "sender_mailbox": "noreply@yourdomain.com"
  }'
```

### Email Templates

Place HTML email templates in the `email_templates/` directory. Use Jinja2 syntax for variable substitution:

```html
<!-- email_templates/welcome.html -->
<h1>Welcome, {{ name }}!</h1>
<p>Thank you for joining us.</p>
```

## License

This project is licensed under GPL-3.0-only. See the [LICENSE](LICENSE) file for details.

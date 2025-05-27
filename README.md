# Orlando PD Active Calls Monitor

A Python script that monitors Orlando Police Department's active calls feed and sends notifications when calls match specific location criteria.

## Features

- 🚨 Real-time monitoring of Orlando PD active calls
- 🔍 Configurable location search (default: "FORELAND")
- 📱 Push notifications via [ntfy.sh](https://ntfy.sh)
- 📧 Email notifications via [Resend](https://resend.com)
- 🚫 Duplicate notification prevention
- ⚙️ Configurable polling intervals
- 📝 Comprehensive logging

## Setup

### Prerequisites
- Podman and podman-compose (or Docker and Docker Compose)
- Internet connection

### Installation

#### Option 1: Docker (Recommended)

1. Clone or download this repository
2. Copy the environment template:
```bash
cp env.example .env
```
3. Edit `.env` file with your ntfy.sh topic:
```bash
# Edit the NTFY_TOPIC value
NTFY_TOPIC=your-unique-topic-name
```

#### Option 2: Local Python Setup

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Container Usage (Recommended)

#### Basic Usage
```bash
# Using environment variables from .env file
podman-compose up
# OR with Docker
# docker-compose up

# Or specify topic directly
NTFY_TOPIC=your-topic podman-compose up
```

#### Advanced Usage
```bash
# Custom configuration
NTFY_TOPIC=police-alerts SEARCH_TERM="MAIN ST" POLL_INTERVAL=60 podman-compose up

# With multiple email recipients
EMAIL_TO=alerts@domain.com,security@company.com NTFY_TOPIC=police-alerts podman-compose up

# Run in background
podman-compose up -d

# View logs
podman-compose logs -f

# Stop the monitor
podman-compose down
```

#### Alternative: Direct Podman/Docker Commands
```bash
# Build the image
podman build -t orlando-pd-monitor .

# Run with basic configuration
podman run --rm orlando-pd-monitor --topic your-topic

# Run with custom configuration
podman run --rm orlando-pd-monitor --topic police-alerts --search "MAIN ST" --interval 60

# Run with multiple email recipients
podman run --rm orlando-pd-monitor --topic police-alerts --email-to "alerts@domain.com,security@company.com" --resend-api-key "your-key" --email-from "orlando-pd@domain.com"

# Run in background (detached)
podman run -d --name orlando-monitor orlando-pd-monitor --topic your-topic
```

### Local Python Usage

#### Basic Usage
```bash
python orlando_pd_monitor.py --topic your-unique-topic
```

#### Advanced Usage
```bash
# Custom search term and polling interval
python orlando_pd_monitor.py --topic police-alerts --search "MAIN ST" --interval 60

# Enable verbose logging
python orlando_pd_monitor.py --topic my-alerts --verbose
```

### Command Line Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--topic` | Yes | - | ntfy.sh topic name for notifications |
| `--search` | No | FORELAND | Location search term |
| `--interval` | No | 30 | Polling interval in seconds |
| `--verbose, -v` | No | False | Enable debug logging |
| `--resend-api-key` | No | - | Resend API key for email notifications |
| `--email-to` | No | - | Email address(es) to send notifications to (comma-separated) |
| `--email-from` | No | - | Email address to send notifications from |

## ntfy.sh Setup

1. Choose a unique topic name (e.g., `orlando-pd-alerts-abc123`)
2. Subscribe to notifications:
   - **Mobile**: Install ntfy app, subscribe to your topic
   - **Web**: Visit `https://ntfy.sh/your-topic-name`
   - **Desktop**: Use ntfy desktop app

⚠️ **Security Note**: Use a hard-to-guess topic name to prevent unauthorized access.

## Email Setup (Optional)

1. Sign up for a [Resend](https://resend.com) account
2. Get your API key from the Resend dashboard
3. Set up your sending domain in Resend
4. Configure the email settings in your `.env` file:
   ```bash
   RESEND_API_KEY=your-resend-api-key
   EMAIL_TO=alerts@yourdomain.com,security@yourdomain.com,team@company.com
   EMAIL_FROM=orlando-pd@yourdomain.com
   ```

⚠️ **Note**: All three email settings (API key, to, from) must be configured for email notifications to work.

## Data Source

This script monitors the official Orlando PD active calls XML feed:
`https://www1.cityoforlando.net/opd/activecalls/activecadpolice.xml`

## Example Output

When a matching call is found, you'll receive a notification like:
```
🚨 Orlando PD Alert: FORELAND
Type: General disturbance
Time: 5/27/2025 13:08
Location: 1234 FORELAND DRIVE
Incident: G1
```

## Troubleshooting

### Common Issues
- **No notifications**: Check your topic name and ntfy.sh subscription
- **Connection errors**: Verify internet connection and Orlando PD feed availability
- **Permission errors**: Ensure Python has network access

### Logs
Use `--verbose` flag to see detailed logging output for debugging.

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is for educational and personal use. Please respect Orlando PD's terms of service for their data feed. # orlando-pd-notifications

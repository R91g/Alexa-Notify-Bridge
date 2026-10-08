# Alexa Notify Bridge — Documentation

A lightweight bridge that lets you send custom proactive notifications to your Amazon Echo (Alexa) devices via local HTTP requests, directly from Home Assistant.

Alexa will light up the yellow ring and read your notifications when you ask: *"Alexa, what are my notifications?"*.

---

## Prerequisites

Before installing this add-on, you need to create a private Alexa Skill in your Amazon Developer account to obtain the required credentials. Follow the **"Alexa Skill Creation & Configuration"** guide in the [project README](https://github.com/R91g/Alexa-Notify-Bridge#2-alexa-skill-creation--configuration).

You will need:
- **Alexa Client ID**
- **Alexa Client Secret**

Both can be found in the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) → Your Skill → Build → Permissions.

---

## Configuration

After installing the add-on, go to the **Configuration** tab and fill in the following options:

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| **Alexa Client ID** | ✅ | — | Your Alexa Skill's Client ID |
| **Alexa Client Secret** | ✅ | — | Your Alexa Skill's Client Secret |
| **API Key** | ❌ | *(empty)* | Optional password to protect the `/notify` endpoint |
| **Region** | ✅ | `EU` | Your Amazon region: `NA` (North America), `EU` (Europe), `FE` (Far East) |
| **Log Level** | ✅ | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING` or `ERROR` |

> **Security Tip:** Setting an API Key is strongly recommended. If set, all requests to `/notify` must include the header `x-api-key: your_key`.

---

## Usage

Once the add-on is running, the bridge will be listening on **port 8080**. You can send notifications using HTTP POST requests.

### Setting up a `rest_command` in Home Assistant

The cleanest way to use this add-on is by creating a `rest_command`. Add the following to your `configuration.yaml`:

```yaml
rest_command:
  alexa_notify:
    url: "http://<YOUR_HOME_ASSISTANT_IP>:8080/notify"
    method: POST
    headers:
      Content-Type: "application/json"
      # x-api-key: "your_api_key"  # Uncomment if you set an API Key
    payload: '{"creator_name": "{{ message }}"}'
```

> **Note:** Replace `<YOUR_HOME_ASSISTANT_IP>` with the local IP address of your Home Assistant server (e.g., `http://192.168.1.50:8080/notify`). Do not use `localhost` because Home Assistant Core and add-ons run in separate Docker container network namespaces.

After restarting Home Assistant, you can use it in any automation or script:

```yaml
action: rest_command.alexa_notify
data:
  message: "The washing machine has finished"
```

### Optional: UI-Friendly Script

To make it easy to use from the visual Automation editor, create a script in **Settings > Automations & scenes > Scripts**:

```yaml
alias: "Notify via Alexa"
icon: mdi:bell-circle-outline
fields:
  message:
    name: Message
    description: "The text Alexa will read aloud"
    required: true
    selector:
      text:
sequence:
  - action: rest_command.alexa_notify
    data:
      message: "{{ message }}"
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notify` | `POST` | Send a proactive notification to Alexa |
| `/health` | `GET` | Health check (returns `{"status": "ok"}`) |

### POST `/notify` — Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `creator_name` | `string` | ✅ | — | The text Alexa will read aloud (max 256 characters) |
| `urgency` | `string` | ❌ | `"URGENT"` | Must be `"URGENT"` |

---

## How notifications work (the "Creator" trick)

Amazon's notification API uses a fixed template:
> *"From [Skill], you have a new message from **[Creator]**"*

To get Alexa to say custom text, the message is sent inside the `creator_name` field (the same technique used by popular skills like *Notify Me*).

When you ask *"Alexa, what are my notifications?"*, it will say:
> *"You have a new notification from Home. From Home, you have a new message from **the washing machine has finished**."*

> **💡 Tip:** You can change the skill name (the "Home" part) by editing the `skill.json` file before deploying your Alexa Skill. See the project README for details.

---

## Rate Limiting

To prevent temporary bans from Amazon, the bridge limits requests to **10 notifications per 10-second window**. Exceeding this returns HTTP `429 Too Many Requests`.

---

## Troubleshooting

- **Notifications not arriving?** Check that you have enabled the skill in the Alexa app and granted it the Notifications permission.
- **Authentication errors in the log?** Verify your Alexa Client ID and Client Secret in the add-on Configuration tab.
- **Wrong region?** Make sure the Region setting matches the Amazon account region where your Alexa devices are registered.
- **Check the logs:** Go to the add-on's **Log** tab in Home Assistant for detailed diagnostic information. Set the log level to `DEBUG` for maximum detail.

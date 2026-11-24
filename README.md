# Alexa Notify Bridge 🚀

[🇪🇸 Español](README_es.md) | [🇬🇧 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<a href="https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FR91g%2FAlexa-Notify-Bridge" title="Add to Home Assistant"><img src="https://brands.home-assistant.io/_/homeassistant/icon.png" height="20" alt="Home Assistant" style="vertical-align: middle;"></a>

A lightweight bridge built in Python (FastAPI) and packaged in Docker. It allows you to send custom proactive notifications to your Amazon Echo (Alexa) devices via local HTTP requests.

Ideal for integrating with home automation systems (Home Assistant, Node-RED, etc.), replicating the functionality of popular skills like *Notify Me*. Alexa will light up the yellow ring and read your notifications when you ask: *"Alexa, what are my notifications?"*.

## Features

*   🚀 **Easy to use:** Send a simple local HTTP POST request to trigger a notification on your Alexa account.
*   🐳 **Dockerized:** Ready to run in seconds with Docker Compose.
*   🏠 **Home Assistant add-on:** Install directly from Home Assistant with a graphical configuration UI.
*   🔒 **Privacy-focused:** You don't rely on third-party servers (except Amazon's own API); your credentials stay on your local server.
*   🩺 **Health check:** Built-in `/health` endpoint for monitoring and Docker health checks.

---

## 1. Prerequisites

*   An [Amazon Developer](https://developer.amazon.com/alexa) account.
*   [Node.js](https://nodejs.org/) (optional, only if you choose to configure the skill locally without Docker or Codespaces).
*   **For Docker installation only:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/).

> **⚠️ Alexa+ (Early Access) Compatibility:** On devices enrolled in the **Alexa+ Early Access** program, there is a known limitation on Amazon's side where proactive notifications are delivered to your account (Alexa reads them when you ask *"What are my notifications?"*), but **the yellow ring does not light up** and no chime plays on Echo speakers. This is controlled by Alexa+ and cannot be forced through the API. If you rely on the yellow notification ring, the only workaround currently is to opt out of Alexa+ Early Access and revert to classic Alexa.

---

## 2. Alexa Skill Creation & Configuration

For Alexa to send you proactive events, you need a private Skill in your [Amazon Developer](https://developer.amazon.com/alexa/console/ask) account with proactive notification permissions enabled.

This repository includes an **automated setup wizard (`setup-skill.sh`)** that handles everything for you: it creates the skill, applies the proactive notification permissions, lets you pick a custom skill name (default: *"Home"*), and prints your **Alexa Client ID** and **Alexa Client Secret** right in the terminal.

### Step A: Run the Automated Setup Wizard

Choose **one of the following methods** (**Option 1** is the easiest — no local installation required):

#### Option 1: In your browser via GitHub Codespaces (Recommended — Zero local setup)
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/R91g/Alexa-Notify-Bridge)

> **ℹ️ Is Codespaces free?** Yes. Every personal GitHub account includes **60 free hours per month**. If you see a notice saying *"paid by user"*, don't worry: this setup takes less than 2 minutes and is completely covered by your free monthly quota.

1. Click the **"Open in GitHub Codespaces"** button above (`ask-cli` comes preinstalled automatically).
2. Once the browser terminal finishes loading, run the wizard:
   ```bash
   ./setup-skill.sh
   ```
3. Follow the on-screen prompts (when ASK CLI asks if you want to link an AWS account, type **`n`** — **you do NOT need an AWS account**).
4. Copy the **`ALEXA_CLIENT_ID`** and **`ALEXA_CLIENT_SECRET`** printed at the end.
5. Done! You can close or delete the Codespace.

---

#### Option 2: Using Docker in a single command (For Docker users)
If you already have Docker installed, you can run the same wizard inside an ephemeral container without installing Node.js on your host *(run from the repository root)*:

- **On Linux / macOS:**
  ```bash
  docker run -it --rm -v "$(pwd):/repo" node:lts-alpine sh /repo/setup-skill.sh
  ```
- **On Windows (PowerShell):**
  ```powershell
  docker run -it --rm -v "${PWD}:/repo" node:lts-alpine sh /repo/setup-skill.sh
  ```

---

#### Option 3: Locally with Node.js
If you already have [Node.js](https://nodejs.org/) installed, run from the repository root:
```bash
./setup-skill.sh
```
*(If `ask-cli` is not installed yet, the script will install it automatically).*

<details>
<summary>🛠️ Manual setup (advanced, without the wizard)</summary>

If you prefer doing it manually step by step:
1. Go to the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask), create a new Skill (**Custom Model**), and note down its **Skill ID**.
2. Install and configure ASK CLI:
   ```bash
   npm install -g ask-cli
   ask configure --no-browser   # Type 'n' when asked to link an AWS account
   ```
3. *(Optional)* Edit `alexa-skill/skill.json` (saved as **UTF-8**) if you want to change the default skill name (`"Home"`).
4. Upload the manifest to your Skill:
   ```bash
   ask smapi update-skill-manifest -s <YOUR_SKILL_ID> -g development --manifest "file:alexa-skill/skill.json"
   ```
5. Retrieve your credentials via `ask smapi get-skill-credentials -s <YOUR_SKILL_ID>` or in **Alexa Developer Console → Your Skill → Build → Permissions** (at the bottom of the page).

</details>

> **ℹ️ About the endpoint URI:** The `alexa-skill/skill.json` file contains a Lambda ARN (`ReflectorTemplateSkill`). This is a **generic public endpoint provided by Amazon** used as a placeholder — it is not a personal resource. **Do not change it.** Proactive notifications do not route through this endpoint; it is simply a required field in the skill manifest.

### Step B: Enable the Skill on your account (Final step in the Alexa app!)
For privacy reasons, Amazon always requires enabling the skill and granting notification permission from the mobile app:

1. Open the Alexa app on your phone (make sure you use the same Amazon account used in Step A).
2. Go to **More** > **Skills & Games** > scroll to the bottom and enter **Your Skills**.
3. In the **Development** (or *Dev*) tab, you will see the skill you just created.
4. Tap on it, click **Enable to use**, and **grant it the Notifications permission**.

---

## 3. Installation

Choose the method that best suits your setup:

### Option A: Home Assistant Add-on (Recommended)

The easiest way if you already use Home Assistant:

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FR91g%2FAlexa-Notify-Bridge)

*(Or add it manually)*:

1. In Home Assistant, go to **Settings > Add-ons > Add-on Store**.
2. Click the three dots (⋮) in the top right corner and select **Repositories**.
3. Add this repository URL:
   ```
   https://github.com/R91g/Alexa-Notify-Bridge
   ```
4. Find **Alexa Notify Bridge** in the add-on store and click **Install**.
5. Go to the **Configuration** tab and enter your credentials (Client ID, Client Secret), choose your region and set an optional API Key.
6. Click **Start**.

> **📖 Full documentation:** Once installed, the add-on's **Documentation** tab contains detailed usage instructions including `rest_command` setup and automation examples.

### Option B: Docker Standalone

For servers without Home Assistant, or if you prefer to manage Docker containers directly.

1. Clone this repository on your server and enter the directory:
   ```bash
   git clone https://github.com/R91g/Alexa-Notify-Bridge.git
   cd Alexa-Notify-Bridge
   ```
2. Make a copy of the sample environment variables file:
   ```bash
   cp .env.example .env
   ```
3. Edit the `.env` file and paste your credentials:
   - `ALEXA_CLIENT_ID` — your Alexa Client ID
   - `ALEXA_CLIENT_SECRET` — your Alexa Client Secret

   > **🌍 Region Note:** By default, the `.env` file is configured for the European region (`eu`). If you are in North America or Asia, simply comment out that line in your `.env` file and uncomment the `PROACTIVE_EVENTS_URL` that corresponds to your region.

   > **🔒 Security Tip:** It is strongly recommended to also set an `API_KEY` value to protect your endpoint from unauthorized access on your local network.

4. Start the container in the background:
   ```bash
   docker compose up -d --build
   ```

*(The bridge will be listening on port 8080. You can change this in the `docker-compose.yml` file if needed).*

---

## 4. Usage

Once it's running, you can send notifications by making a POST request.

### Example Command (cURL)
```bash
curl -X POST http://<BRIDGE_IP>:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"creator_name": "the garage door is open"}'
```

> **🔒 Security:** If you have configured an `API_KEY` in your `.env` file, you must add it as a header in your requests:
> ```bash
> -H "x-api-key: your_secret_api_key"
> ```

### API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/notify` | `POST` | Send a proactive notification to Alexa |
| `/health` | `GET` | Lightweight health check (returns `{"status": "ok"}`, unauthenticated) |
| `/status` | `GET` | Bridge configuration, region, credentials and active Amazon token status (protected by `API_KEY` if set) |
| `/history` | `GET` | Returns in-memory notification history (most recent first). Supports `?limit=N` (default 50) |

#### POST `/notify` — Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` (or `creator_name`) | `string` | ✅ | — | The text Alexa will read aloud — accepts either `message` or `creator_name` (if longer than 256 chars, automatically truncated to 253 + '...') |
| `urgency` | `string` | ❌ | `"URGENT"` | Must be `"URGENT"` |
| `expiry_hours` | `number` | ❌ | `24` | Hours until notification expires (clamped automatically between 5 min and 24h) |
| `debounce_seconds` | `number` | ❌ | `0` (or config) | Window in seconds to ignore identical consecutive notifications |

> **✂️ Automatic Truncation:** If a message exceeds Amazon's strict 256-character limit (e.g., when rendering long Home Assistant templates), the bridge automatically truncates it to 253 characters + `...`. The notification is never lost, and the response includes `"truncated": true`.
>
> **🛡️ Anti-Duplicate Debounce Filter:** If a bouncing sensor or automation fires multiple times sending the exact same text within the debounce window (configured globally via `DEBOUNCE_SECONDS` or per request), the bridge discards duplicates with `{"status": "ignored", "debounced": true}` to prevent spamming your speakers.
>
> **⏱️ Rate Limiting:** To prevent temporary bans from Amazon (e.g., if an automation loops), the bridge enforces a limit of **10 notifications per 10-second window**. Exceeding this limit will return an HTTP `429 Too Many Requests` error.

### 💡 The "Creator" Trick (Replicating Notify Me)
Due to Amazon's security limitations, the notifications API does not allow sending completely free text, but uses the template:
> *"From [Skill], you have a new message from **[Creator]**"*

To bypass this limitation (just like famous Skills like *Notify Me* do), we send the message we want Alexa to read inside the `creator_name` field.

So, when you tell your speaker: *"Alexa, what are my notifications?"*, it will say:
*"You have a new notification from Home. From Home, you have a new message from **the garage door is open**."*

---

## 5. Integration with Home Assistant

The cleanest and most centralized way to use this bridge from Home Assistant is by creating a `rest_command`. This allows you to call the notification from any automation or script just by passing the text.

1. Add the following to your `configuration.yaml`:

```yaml
rest_command:
  alexa_notify:
    url: "http://<SERVER_IP>:8080/notify"
    method: POST
    headers:
      Content-Type: "application/json"
      # x-api-key: "your_secret_api_key"  # Uncomment if you use API_KEY
    payload: >-
      {"creator_name": {{ (message | default('')) | to_json }}{% if expiry_hours is defined and expiry_hours not in ['', None, 'None'] %}, "expiry_hours": {{ expiry_hours | float }}{% endif %}{% if debounce_seconds is defined and debounce_seconds not in ['', None, 'None'] %}, "debounce_seconds": {{ debounce_seconds | float }}{% endif %}}
```

> **📌 Note on URL:** Replace `<SERVER_IP>` with the local IP of your server (e.g., `http://192.168.1.50:8080/notify`). If using the **Add-on**, use the local IP of your Home Assistant host (do not use `localhost` because Home Assistant Core and add-ons run in isolated Docker network namespaces). If using **standalone Docker**, use the IP of the machine running the container.

2. Restart Home Assistant to apply the changes.
3. Now you can use it in any automation or script like this:

```yaml
# Standard notification (uses default 24h expiry):
action: rest_command.alexa_notify
data:
  message: "The washing machine has finished"

# Notification with custom expiry (e.g., expires in 15 minutes):
action: rest_command.alexa_notify
data:
  message: "The garage door is still open"
  expiry_hours: 0.25
```

4. **(Optional) UI-Friendly Script:**
   To make it easier to use from the visual Automation editor, you can create a script. Go to **Settings > Automations & scenes > Scripts**, create a new script, click the three dots in the top right corner and select **"Edit in YAML"**. Clear the existing code and paste this:

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
     expiry_hours:
       name: Expiry Hours
       description: "Hours before notification expires (optional, default: 24h)"
       required: false
       selector:
         number:
           min: 0.1
           max: 24
           step: 0.5
           unit_of_measurement: h
     debounce_seconds:
       name: Debounce Seconds
       description: "Seconds to ignore duplicate consecutive messages (optional)"
       required: false
       selector:
         number:
           min: 0
           max: 300
           step: 5
           unit_of_measurement: s
   sequence:
     - action: rest_command.alexa_notify
       data:
         message: "{{ message }}"
         expiry_hours: "{{ expiry_hours | default(none) }}"
         debounce_seconds: "{{ debounce_seconds | default(none) }}"
   ```
   *Now you can select the "Notify via Alexa" action in your automations and get a text box for the message plus optional expiry and debounce selectors!*

---

## 6. Updating

### Home Assistant Add-on (Recommended)
Home Assistant periodically checks the repository and **detects new versions automatically**. When an update is released:
1. An update notification will appear in your dashboard or under **Settings > Add-ons**.
2. Simply open the **Alexa Notify Bridge** add-on page and click **Update**. Your configuration will remain untouched.

### Standalone Docker
If a new version is released on GitHub, you can update manually from the terminal without losing your configuration (your `.env` file is safe because it is excluded in `.gitignore`):

1. Enter the project folder on your server:
   ```bash
   cd Alexa-Notify-Bridge
   ```
2. Download the latest changes from GitHub:
   ```bash
   git pull
   ```
3. Rebuild and restart the container seamlessly:
   ```bash
   docker compose up -d --build
   ```

---

## License

This project is licensed under the [MIT License](LICENSE).

# Alexa Notify Bridge 🚀

[🇪🇸 Español](README_es.md) | [🇬🇧 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Important Disclaimer:** This project was created by someone without extensive programming knowledge with the help of an Artificial Intelligence through *"vibe coding"* (conversational programming). Its structure is focused on being functional and easy to understand. Therefore, it may contain some bugs and potential improvements. If you find any, please let me know.

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
*   [Node.js](https://nodejs.org/) (needed only for installing `ask-cli`).
*   **For Docker installation only:** [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/).

---

## 2. Alexa Skill Creation & Configuration

For Alexa to send you proactive events, you need to create a private Skill in your account.

### Step A: Create the Skill
1. Go to the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).
2. Create a new Skill. Choose a name (e.g., "Home Notifications"), select **Custom Model**, and create the skill.
3. Note down the **Skill ID** of your new Skill (you will find it in the URL or in the general settings).

### Step B: Install ASK CLI and grant permissions (Very Important)
The Proactive Events API requires special permissions that **can only be configured by uploading the manifest file (`skill.json`) using Amazon's official command-line tool (ASK CLI)**.

1. Open your terminal and run the following command to install ASK CLI (requires Node.js):
   ```bash
   npm install -g ask-cli
   ```
2. Link the terminal to your Amazon account by running:
   ```bash
   ask configure
   ```
   *This will open your browser so you can log in to your Amazon Developer account.*
3. In the terminal, navigate to a temporary folder and download the structure of your new skill:
   ```bash
   ask init
   ```
   *(Follow the on-screen instructions, choose your profile, and select the skill you just created in Step A).*
4. Go to the downloaded folder, enter the `skill-package` subfolder, and replace the default `skill.json` file with the `skill.json` file included in this repository (inside the `alexa-skill/` folder).
   > **💡 Tip (Change the name):** By default, Alexa will say *"You have a new notification from **Home**"*. If you want it to say something else (e.g., "HomeAssistant" or "Server"), simply open the `skill.json` file and change the value `"name": "Home"` (or `"name": "Casa"` for Spanish) to your preferred name before uploading it.
   >
   > **⚠️ Encoding Note:** Ensure your text editor saves the `skill.json` file with **UTF-8** encoding. If it is saved in UTF-16 (common in some Windows editors), ASK CLI will throw an error.
   >
   > **ℹ️ About the endpoint URI:** The `skill.json` file contains a Lambda ARN (`ReflectorTemplateSkill`). This is a **generic public endpoint provided by Amazon** used as a placeholder — it is not a personal resource. **Do not change it.** Proactive notifications do not route through this endpoint; it is simply a required field in the skill manifest.
5. Upload the changes to apply the permissions by running:
   ```bash
   ask deploy --target skill-metadata
   ```

*(Fast alternative for advanced users: If you have your Skill ID ready, you can skip `ask init` and upload the file directly by running: `ask smapi update-skill-manifest -s <YOUR_SKILL_ID> -g development --manifest "file:alexa-skill/skill.json"`).*

### Step C: Get Credentials
1. Go back to the [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) and enter your Skill.
2. Go to the **Build** tab.
3. In the bottom menu bar, click on **Build -> Permissions** and at the bottom of the page, you will find the **Alexa Client ID** and the **Alexa Client Secret**. Copy them.

### Step D: Enable the Skill on your account (Final Amazon step!)
For your speaker to notify you, you need to tell Alexa that you want to use this new Skill:

1. Open the Alexa app on your phone (make sure you use the same Amazon account you used for developer).
2. Go to **More** > **Skills & Games** > scroll to the bottom and enter **Your Skills**.
3. In the **Development** (or *Dev*) tab, you will see the skill you just created.
4. Tap on it, click **Enable to use** and **grant it the Notifications permission**.

---

## 3. Installation

Choose the method that best suits your setup:

### Option A: Home Assistant Add-on (Recommended)

The easiest way if you already use Home Assistant.

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
| `/health` | `GET` | Health check (returns `{"status": "ok"}`) |

#### POST `/notify` — Request body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `creator_name` | `string` | ✅ | — | The text Alexa will read aloud (Max 256 characters) |
| `urgency` | `string` | ❌ | `"URGENT"` | Must be `"URGENT"` |

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
    payload: '{"creator_name": "{{ message }}"}'
```

> **📌 Note on URL:** Replace `<SERVER_IP>` with the local IP of your server (e.g., `http://192.168.1.50:8080/notify`). If using the **Add-on**, use the local IP of your Home Assistant host (do not use `localhost` because Home Assistant Core and add-ons run in isolated Docker network namespaces). If using **standalone Docker**, use the IP of the machine running the container.

2. Restart Home Assistant to apply the changes.
3. Now you can use it in any automation or script like this:

```yaml
action: rest_command.alexa_notify
data:
  message: "The washing machine has finished"
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
   sequence:
     - action: rest_command.alexa_notify
       data:
         message: "{{ message }}"
   ```
   *Now you can just select the "Notify via Alexa" action in your automations and it will give you a simple text box!*

---

## 6. Updating

If new versions are released, you can easily update your bridge without losing your configuration (your `.env` file is safe because it is excluded in `.gitignore`):

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

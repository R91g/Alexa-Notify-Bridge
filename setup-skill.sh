#!/bin/sh
# Interactive wizard to create/configure your private Alexa Proactive Notifications Skill
# and retrieve its Alexa Client ID and Client Secret in one step.
#
# Compatible with GitHub Codespaces, Docker (node:lts-alpine), Linux, macOS, and Git Bash.

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
BASE_MANIFEST="${SCRIPT_DIR}/alexa-skill/skill.json"
TMP_MANIFEST=""

cleanup() {
    if [ -n "${TMP_MANIFEST}" ] && [ -f "${TMP_MANIFEST}" ]; then
        rm -f "${TMP_MANIFEST}"
    fi
}
trap cleanup EXIT INT TERM

# ─── Language selection ──────────────────────────────────────────────────────

printf "\n"
printf "======================================================================\n"
printf "  Alexa Notify Bridge — Skill Setup Wizard / Asistente de Skill\n"
printf "======================================================================\n"
printf "\n"
printf "  1) Español\n"
printf "  2) English\n"
printf "\n"
printf "Elige idioma / Choose language [1]: "
read -r LANG_CHOICE || LANG_CHOICE="1"
if [ "${LANG_CHOICE}" = "2" ]; then
    UI_LANG="en"
else
    UI_LANG="es"
fi

msg() {
    if [ "${UI_LANG}" = "en" ]; then
        printf "%s\n" "$2"
    else
        printf "%s\n" "$1"
    fi
}

# ─── Pre-flight checks ───────────────────────────────────────────────────────

if [ ! -f "${BASE_MANIFEST}" ]; then
    msg \
        "❌ Error: No se encontró '${BASE_MANIFEST}'. Ejecuta este script desde la raíz del repositorio." \
        "❌ Error: Could not find '${BASE_MANIFEST}'. Run this script from the repository root."
    exit 1
fi

if ! command -v node >/dev/null 2>&1; then
    msg \
        "❌ Error: Node.js no está instalado. Usa GitHub Codespaces o Docker, o instala Node.js primero." \
        "❌ Error: Node.js is not installed. Use GitHub Codespaces or Docker, or install Node.js first."
    exit 1
fi

if ! command -v ask >/dev/null 2>&1; then
    printf "\n"
    msg \
        "📦 ASK CLI no está instalado todavía. Instalando ask-cli (puede tardar ~30 segundos)..." \
        "📦 ASK CLI is not installed yet. Installing ask-cli (this may take ~30 seconds)..."
    npm install -g ask-cli
fi

# ─── Step 1: Amazon Developer Login ──────────────────────────────────────────

printf "\n"
msg \
    "── Paso 1/3: Inicio de sesión en Amazon Developer ───────────────────" \
    "── Step 1/3: Amazon Developer Sign-In ───────────────────────────────"

NEED_LOGIN="yes"
if [ -f "${HOME}/.ask/cli_config" ]; then
    printf "\n"
    if [ "${UI_LANG}" = "en" ]; then
        printf "An existing ASK CLI login was found. Reuse it? [Y/n]: "
    else
        printf "Se detectó una sesión previa de ASK CLI. ¿Reutilizarla? [S/n]: "
    fi
    read -r REUSE_ANS || REUSE_ANS=""
    case "${REUSE_ANS}" in
        n|N|no|NO) NEED_LOGIN="yes" ;;
        *) NEED_LOGIN="no" ;;
    esac
fi

if [ "${NEED_LOGIN}" = "yes" ]; then
    printf "\n"
    msg \
        "ℹ️  Durante el inicio de sesión de ASK CLI te hará unas preguntas rápidas:" \
        "ℹ️  ASK CLI will ask you a few quick questions during sign-in:"
    msg \
        "   • Profile name → Pulsa Enter (default)" \
        "   • Profile name → Press Enter (default)"
    msg \
        "   • 'Do you want to link your AWS account?' → Responde 'n' (NO necesitas cuenta AWS)" \
        "   • 'Do you want to link your AWS account?' → Type 'n' (you do NOT need an AWS account)"
    msg \
        "   • Abre el enlace de Amazon en tu navegador, inicia sesión y pega aquí el código." \
        "   • Open the Amazon link in your browser, sign in, and paste the authorization code here."
    printf "\n"
    ask configure --no-browser
fi

# ─── Step 2: Skill name & Create/Update ──────────────────────────────────────

printf "\n"
msg \
    "── Paso 2/3: Configurar y crear la Skill de Alexa ───────────────────" \
    "── Step 2/3: Configure and Create the Alexa Skill ───────────────────"
printf "\n"
msg \
    "Por defecto Alexa dirá: \"Tienes una notificación nueva de Casa\" (o \"Home\" en inglés)." \
    "By default Alexa will say: \"You have a new notification from Home\"."

if [ "${UI_LANG}" = "en" ]; then
    printf "Custom skill name (press Enter to keep default): "
else
    printf "Nombre personalizado para la skill (pulsa Enter para dejar el predeterminado): "
fi
read -r CUSTOM_SKILL_NAME || CUSTOM_SKILL_NAME=""

MANIFEST_TO_USE="${BASE_MANIFEST}"
if [ -n "${CUSTOM_SKILL_NAME}" ]; then
    TMP_MANIFEST="$(mktemp "${TMPDIR:-/tmp}/alexa-skill-manifest.XXXXXX.json")"
    BASE_MANIFEST="${BASE_MANIFEST}" TMP_MANIFEST="${TMP_MANIFEST}" CUSTOM_SKILL_NAME="${CUSTOM_SKILL_NAME}" node -e '
        const fs = require("fs");
        const data = JSON.parse(fs.readFileSync(process.env.BASE_MANIFEST, "utf8"));
        const name = process.env.CUSTOM_SKILL_NAME.trim();
        const locales = data.manifest.publishingInformation.locales;
        for (const loc of Object.keys(locales)) {
            locales[loc].name = name;
        }
        fs.writeFileSync(process.env.TMP_MANIFEST, JSON.stringify(data, null, 2), "utf8");
    '
    MANIFEST_TO_USE="${TMP_MANIFEST}"
    msg \
        "✅ Nombre personalizado aplicado: ${CUSTOM_SKILL_NAME}" \
        "✅ Custom name applied: ${CUSTOM_SKILL_NAME}"
fi

printf "\n"
if [ "${UI_LANG}" = "en" ]; then
    printf "Do you already have a Skill ID to update? (leave empty to CREATE a new skill automatically): "
else
    printf "¿Ya tienes un Skill ID para actualizar? (déjalo vacío para CREAR una skill nueva automáticamente): "
fi
read -r EXISTING_SKILL_ID || EXISTING_SKILL_ID=""

SKILL_ID=""
if [ -n "${EXISTING_SKILL_ID}" ]; then
    SKILL_ID="${EXISTING_SKILL_ID}"
    printf "\n"
    msg \
        "⏳ Actualizando el manifiesto de la skill ${SKILL_ID}..." \
        "⏳ Updating manifest for skill ${SKILL_ID}..."
    ask smapi update-skill-manifest -s "${SKILL_ID}" -g development --manifest "file:${MANIFEST_TO_USE}"
else
    printf "\n"
    msg \
        "⏳ Creando tu skill privada en Amazon Developer con permisos de Notificaciones..." \
        "⏳ Creating your private Alexa Skill with Notifications permissions..."
    CREATE_OUTPUT="$(ask smapi create-skill-for-vendor --manifest "file:${MANIFEST_TO_USE}")"
    SKILL_ID="$(printf "%s" "${CREATE_OUTPUT}" | node -e '
        const fs = require("fs");
        const raw = fs.readFileSync(0, "utf8").trim();
        try {
            const parsed = JSON.parse(raw);
            process.stdout.write(parsed.skillId || parsed.id || "");
        } catch (_) {
            const match = raw.match(/amzn1\.ask\.skill\.[A-Za-z0-9-]+/);
            process.stdout.write(match ? match[0] : "");
        }
    ')"
    if [ -z "${SKILL_ID}" ]; then
        msg \
            "❌ No se pudo extraer el Skill ID de la respuesta de Amazon:" \
            "❌ Could not extract Skill ID from Amazon response:"
        printf "%s\n" "${CREATE_OUTPUT}"
        exit 1
    fi
    msg \
        "✅ Skill creada correctamente: ${SKILL_ID}" \
        "✅ Skill created successfully: ${SKILL_ID}"
fi

# Wait for Amazon to finish processing the manifest
msg \
    "⏳ Esperando a que Amazon termine de aprovisionar la skill..." \
    "⏳ Waiting for Amazon to finish provisioning the skill..."

ATTEMPT=0
MAX_ATTEMPTS=20
STATUS="IN_PROGRESS"
while [ "${ATTEMPT}" -lt "${MAX_ATTEMPTS}" ]; do
    STATUS_JSON="$(ask smapi get-skill-status -s "${SKILL_ID}" 2>/dev/null || true)"
    STATUS="$(printf "%s" "${STATUS_JSON}" | node -e '
        const fs = require("fs");
        const raw = fs.readFileSync(0, "utf8").trim();
        try {
            const parsed = JSON.parse(raw);
            const st = parsed && parsed.manifest && parsed.manifest.lastUpdateRequest && parsed.manifest.lastUpdateRequest.status;
            process.stdout.write(st || "UNKNOWN");
        } catch (_) {
            process.stdout.write("UNKNOWN");
        }
    ')"
    if [ "${STATUS}" = "SUCCEEDED" ]; then
        break
    fi
    if [ "${STATUS}" = "FAILED" ]; then
        msg \
            "❌ Amazon rechazó el manifiesto de la skill. Detalle:" \
            "❌ Amazon rejected the skill manifest. Details:"
        printf "%s\n" "${STATUS_JSON}"
        exit 1
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep 3
done

if [ "${STATUS}" != "SUCCEEDED" ]; then
    msg \
        "⚠️  Amazon está tardando más de lo habitual (estado: ${STATUS}), intentando obtener credenciales igualmente..." \
        "⚠️  Amazon is taking longer than usual (status: ${STATUS}), attempting to fetch credentials anyway..."
else
    msg \
        "✅ Manifiesto y permisos aplicados correctamente." \
        "✅ Manifest and permissions applied successfully."
fi

# ─── Step 3: Fetch Credentials ───────────────────────────────────────────────

printf "\n"
msg \
    "── Paso 3/3: Obteniendo tus credenciales de Alexa ───────────────────" \
    "── Step 3/3: Retrieving your Alexa Credentials ──────────────────────"

CREDS_JSON="$(ask smapi get-skill-credentials -s "${SKILL_ID}" 2>/dev/null || true)"
CLIENT_ID="$(printf "%s" "${CREDS_JSON}" | node -e '
    const fs = require("fs");
    try {
        const d = JSON.parse(fs.readFileSync(0, "utf8"));
        const c = d.skillMessagingCredentials || d;
        process.stdout.write(c.clientId || "");
    } catch (_) {}
')"
CLIENT_SECRET="$(printf "%s" "${CREDS_JSON}" | node -e '
    const fs = require("fs");
    try {
        const d = JSON.parse(fs.readFileSync(0, "utf8"));
        const c = d.skillMessagingCredentials || d;
        process.stdout.write(c.clientSecret || "");
    } catch (_) {}
')"

printf "\n"
printf "======================================================================\n"
if [ -n "${CLIENT_ID}" ] && [ -n "${CLIENT_SECRET}" ]; then
    msg \
        "  🎉 ¡TODO LISTO! Copia estos valores en Home Assistant o en tu .env:" \
        "  🎉 ALL DONE! Copy these values into Home Assistant or your .env:"
    printf "======================================================================\n"
    printf "\n"
    printf "  Skill ID            : %s\n" "${SKILL_ID}"
    printf "  ALEXA_CLIENT_ID     : %s\n" "${CLIENT_ID}"
    printf "  ALEXA_CLIENT_SECRET : %s\n" "${CLIENT_SECRET}"
    printf "\n"
    printf "======================================================================\n"
else
    msg \
        "  ✅ Skill lista (${SKILL_ID}), pero no se pudieron leer las credenciales automáticamente." \
        "  ✅ Skill is ready (${SKILL_ID}), but credentials could not be fetched automatically."
    printf "======================================================================\n"
    printf "\n"
    msg \
        "  Ábrela aquí → Build → Permissions (al final de la página):" \
        "  Open it here → Build → Permissions (at the bottom of the page):"
    printf "  https://developer.amazon.com/alexa/console/ask\n\n"
fi

msg \
    "📱 ÚLTIMO PASO (en la app de Alexa de tu móvil):" \
    "📱 FINAL STEP (in the Alexa app on your phone):"
msg \
    "   1. Abre la app de Alexa (con la misma cuenta de Amazon)." \
    "   1. Open the Alexa app (using the same Amazon account)."
msg \
    "   2. Ve a Más → Skills y juegos → Tus Skills → pestaña Desarrollo (Dev)." \
    "   2. Go to More → Skills & Games → Your Skills → Dev tab."
msg \
    "   3. Toca tu nueva skill, pulsa 'Activar para usar' y concede permiso de Notificaciones." \
    "   3. Tap your new skill, select 'Enable to use', and grant the Notifications permission."
printf "\n"

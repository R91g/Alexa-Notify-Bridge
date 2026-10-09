# Alexa Notify Bridge 🚀

[🇪🇸 Español](README_es.md) | [🇬🇧 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Aclaración importante:** Este proyecto ha sido creado por una persona sin grandes conocimientos de programación gracias a la ayuda de una Inteligencia Artificial mediante *"vibe coding"* (programación conversacional). Su estructura está enfocada en ser funcional y fácil de entender. Por tanto, es posible que contenga algunos errores y posibles mejoras. Si encuentras alguno, por favor, házmelo saber.

Este proyecto es un puente (*bridge*) ligero construido en Python (FastAPI) y empaquetado en Docker. Su objetivo es permitirte enviar notificaciones proactivas personalizadas a tus dispositivos Amazon Echo (Alexa) mediante peticiones HTTP locales.

Es ideal para integrarlo con sistemas de domótica (Home Assistant, Node-RED, etc.), replicando el funcionamiento de Skills populares como *Notify Me*. Con esto, Alexa encenderá el anillo amarillo y te leerá las notificaciones cuando le preguntes: *"Alexa, ¿qué notificaciones tengo?"*.

## Características

*   🚀 **Fácil de usar:** Envía una simple petición HTTP POST a nivel local para generar una notificación en tu cuenta de Alexa.
*   🐳 **Dockerizado:** Listo para levantar en segundos con Docker Compose.
*   🏠 **Add-on de Home Assistant:** Instala directamente desde Home Assistant con una interfaz gráfica de configuración.
*   🔒 **Privacidad:** No dependes de servidores de terceros (salvo la propia API de Amazon); tus credenciales se quedan en tu servidor local.
*   🩺 **Health check:** Endpoint `/health` incorporado para monitorización y Docker health checks.

---

## 1. Requisitos Previos

*   Una cuenta de [Amazon Developer](https://developer.amazon.com/alexa).
*   [Node.js](https://nodejs.org/) (opcional, solo si eliges configurar la skill localmente sin Docker ni Codespaces).
*   **Solo para instalación con Docker:** [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/).

---

## 2. Creación y Configuración de la Skill en Amazon

Para que Alexa te envíe eventos proactivos, necesitas crear una Skill privada en tu cuenta.

### Paso A: Crear la Skill
1. Entra en [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask).
2. Crea una nueva Skill. Elige un nombre (ej. "Notificaciones de Casa"), selecciona **Custom Model** (Modelo Personalizado) y crea la skill.
3. Apunta el **Skill ID** de tu nueva Skill (lo encontrarás en la URL o en los ajustes generales).

### Paso B: Configurar permisos con ASK CLI (Muy Importante)
La API de Eventos Proactivos requiere permisos especiales que **solo se pueden configurar subiendo el archivo de manifiesto (`skill.json`) mediante la herramienta oficial de Amazon (ASK CLI)**.

Elige **uno de los siguientes métodos** para aplicar el manifiesto (la **Opción 1** es la más recomendada si no quieres instalar nada en tu PC):

#### Opción 1: En el navegador con GitHub Codespaces (Sin instalar nada — Ideal para Home Assistant)
No necesitas tener Node.js ni Docker instalados en tu ordenador. Se hace 100% desde el navegador de forma gratuita:

1. En este repositorio de GitHub, haz clic en el botón verde **`<> Code`** → pestaña **Codespaces** → **Create codespace on main**.
2. Espera a que cargue el terminal en el navegador e instala ASK CLI:
   ```bash
   npm install -g ask-cli
   ```
3. Inicia sesión con tu cuenta de Amazon:
   ```bash
   ask configure --no-browser
   ```
   *(Abre en una nueva pestaña el enlace que aparece en la consola, inicia sesión en Amazon y pega el código de autorización devuelto en la terminal).*
4. Aplica el manifiesto a tu Skill:
   ```bash
   ask smapi update-skill-manifest -s <TU_SKILL_ID> -g development --manifest "file:alexa-skill/skill.json"
   ```
   *(Sustituye `<TU_SKILL_ID>` por el Skill ID que apuntaste en el Paso A).*
5. ¡Listo! Ya puedes cerrar la pestaña del navegador de Codespaces.

---

#### Opción 2: Con Docker en un solo comando (Para usuarios de Docker)
Si ya tienes Docker instalado en tu servidor o equipo, puedes ejecutar un contenedor efímero sin instalar Node.js ni dependencias en tu sistema:

> **Nota:** Ejecuta este comando desde la raíz del repositorio donde se encuentra la carpeta `alexa-skill`.

- **En Linux / macOS:**
  ```bash
  docker run -it --rm -v "$(pwd)/alexa-skill:/skill" node:lts-alpine sh -c "npm install -g ask-cli && ask configure --no-browser && ask smapi update-skill-manifest -s <TU_SKILL_ID> -g development --manifest file:/skill/skill.json"
  ```
- **En Windows (PowerShell):**
  ```powershell
  docker run -it --rm -v "${PWD}/alexa-skill:/skill" node:lts-alpine sh -c "npm install -g ask-cli && ask configure --no-browser && ask smapi update-skill-manifest -s <TU_SKILL_ID> -g development --manifest file:/skill/skill.json"
  ```
*(Sustituye `<TU_SKILL_ID>` por tu Skill ID. Te pedirá abrir un enlace en tu navegador para autorizar la sesión).*

---

#### Opción 3: En local con Node.js
Si prefieres usar la terminal de tu ordenador y tienes Node.js instalado:

1. Instala ASK CLI:
   ```bash
   npm install -g ask-cli
   ```
2. Inicia sesión en Amazon:
   ```bash
   ask configure
   ```
3. Desde la carpeta del repositorio, sube el manifiesto:
   ```bash
   ask smapi update-skill-manifest -s <TU_SKILL_ID> -g development --manifest "file:alexa-skill/skill.json"
   ```
   *(Sustituye `<TU_SKILL_ID>` por tu Skill ID).*

---

> **💡 Tip (Cambiar el nombre):** Por defecto, Alexa dirá *"Tienes una notificación nueva de **Casa**"* (o *"**Home**"* en inglés). Si quieres que diga otra cosa (ej. "HomeAssistant" o "Servidor"), abre el archivo `alexa-skill/skill.json` y cambia el valor `"name": "Casa"` (o el idioma que uses) por el nombre que prefieras antes de ejecutar el comando de subida.
>
> **⚠️ Nota de codificación:** Si editas el archivo `skill.json`, asegúrate de que tu editor lo guarde con formato **UTF-8**. Si se guarda en UTF-16 (común en algunos editores de Windows), ASK CLI dará error.
>
> **ℹ️ Sobre el endpoint URI:** El archivo `skill.json` contiene un ARN de Lambda (`ReflectorTemplateSkill`). Se trata de un **endpoint público genérico proporcionado por Amazon** que se usa como placeholder — no es un recurso personal. **No lo modifiques.** Las notificaciones proactivas no pasan por este endpoint; simplemente es un campo obligatorio del manifiesto de la skill.

### Paso C: Obtener Credenciales
1. Vuelve a la [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) y entra en tu Skill.
2. Entra en el apartado **Build**.
3. En la barra inferior del menú, haz clic en **Build -> Permissions** y en la parte de abajo de la página, encontrarás el **Alexa Client ID** y el **Alexa Client Secret**. Cópialos.

### Paso D: Habilitar la Skill en tu cuenta (¡Último paso de Amazon!)
Para que tu altavoz te notifique, necesitas decirle a Alexa que quieres usar esta nueva Skill:

1. Abre la app de Alexa en tu móvil (asegúrate de usar la misma cuenta de Amazon que usaste de developer).
2. Ve a **Más** > **Skills y juegos** > haz scroll hasta abajo y entra en **Tus Skills**.
3. En la pestaña **Desarrollo** (o *Dev*), verás la skill que acabas de crear.
4. Toca sobre ella, pulsa **Activar para usar** (Enable to use) y **concédele el permiso de Notificaciones**.

---

## 3. Instalación

Elige el método que mejor se adapte a tu entorno:

### Opción A: Add-on de Home Assistant (Recomendado)

La forma más sencilla si ya usas Home Assistant.

1. En Home Assistant, ve a **Ajustes > Complementos > Tienda de complementos**.
2. Haz clic en los tres puntos (⋮) de la esquina superior derecha y selecciona **Repositorios**.
3. Añade esta URL de repositorio:
   ```
   https://github.com/R91g/Alexa-Notify-Bridge
   ```
4. Busca **Alexa Notify Bridge** en la tienda de complementos y pulsa **Instalar**.
5. Ve a la pestaña **Configuración** e introduce tus credenciales (Client ID, Client Secret), elige tu región y establece una API Key opcional.
6. Pulsa **Iniciar**.

> **📖 Documentación completa:** Una vez instalado, la pestaña **Documentación** del complemento contiene instrucciones detalladas de uso, incluyendo configuración de `rest_command` y ejemplos de automatizaciones.

### Opción B: Docker Independiente

Para servidores sin Home Assistant, o si prefieres gestionar los contenedores Docker directamente.

1. Clona este repositorio en tu servidor y entra en la carpeta:
   ```bash
   git clone https://github.com/R91g/Alexa-Notify-Bridge.git
   cd Alexa-Notify-Bridge
   ```
2. Haz una copia del archivo de ejemplo de variables de entorno:
   ```bash
   cp .env.example .env
   ```
3. Edita el archivo `.env` y pega tus credenciales:
   - `ALEXA_CLIENT_ID` — tu Alexa Client ID
   - `ALEXA_CLIENT_SECRET` — tu Alexa Client Secret

   > **🌍 Nota sobre Regiones:** Por defecto, el archivo `.env` está configurado para la región de Europa (`eu`). Si estás en Norteamérica o Asia, simplemente comenta esa línea en el archivo `.env` y descomenta la `PROACTIVE_EVENTS_URL` que te corresponda.

   > **🔒 Consejo de seguridad:** Es muy recomendable definir también un valor para `API_KEY` para proteger tu endpoint de accesos no autorizados en tu red local.

4. Levanta el contenedor en segundo plano:
   ```bash
   docker compose up -d --build
   ```

*(El puente estará escuchando en el puerto 8080. Puedes cambiarlo en el archivo `docker-compose.yml` si lo necesitas).*

---

## 4. Uso

Una vez funcionando, puedes enviar notificaciones enviando una petición POST.

### Comando de Ejemplo (cURL)
```bash
curl -X POST http://<IP_DEL_BRIDGE>:8080/notify \
  -H "Content-Type: application/json" \
  -d '{"creator_name": "la puerta del garaje está abierta"}'
```

> **🔒 Seguridad:** Si has configurado una `API_KEY` en tu archivo `.env`, deberás añadirla como un encabezado en tus peticiones:
> ```bash
> -H "x-api-key: tu_api_key_secreta"
> ```

### Referencia de la API

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/notify` | `POST` | Enviar una notificación proactiva a Alexa |
| `/health` | `GET` | Health check (devuelve `{"status": "ok"}`) |
| `/history` | `GET` | Devuelve el historial en memoria (más recientes primero). Soporta `?limit=N` (por defecto 50) |

#### POST `/notify` — Cuerpo de la petición

| Campo | Tipo | Requerido | Por defecto | Descripción |
|-------|------|-----------|-------------|-------------|
| `creator_name` | `string` | ✅ | — | El texto que Alexa leerá en voz alta (Máx. 256 caracteres) |
| `urgency` | `string` | ❌ | `"URGENT"` | Debe ser `"URGENT"` |
| `expiry_hours` | `number` | ❌ | `24` | Horas hasta que la notificación expira (acotado automáticamente entre 5 min y 24h) |

> **⏱️ Rate Limiting:** Para evitar baneos temporales por parte de Amazon (ej. si una automatización entra en bucle), el puente implementa un límite de **10 notificaciones por cada ventana de 10 segundos**. Si superas este límite, recibirás un error HTTP `429 Too Many Requests`.

### 💡 El truco del "Creador" (Replicando Notify Me)
Por limitaciones de seguridad de Amazon, la API de notificaciones no permite enviar texto completamente libre, sino que usa la plantilla:
> *"De [Skill], tienes un mensaje nuevo de **[Creador]**"*

Para saltarnos esta limitación (igual que hacen Skills famosas como *Notify Me*), enviamos el mensaje que queremos que lea Alexa dentro del campo `creator_name`.

Así, cuando le digas a tu altavoz: *"Alexa, ¿qué notificaciones tengo?"*, te dirá:
*"Tienes una notificación nueva de Casa. De Casa, tienes un mensaje nuevo de **la puerta del garaje está abierta**."*

---

## 5. Integración con Home Assistant

La forma más limpia y centralizada de usar este puente desde Home Assistant es creando un `rest_command`. Esto te permite llamar a la notificación desde cualquier automatización o script simplemente pasándole el texto.

1. Añade lo siguiente a tu archivo `configuration.yaml`:

```yaml
rest_command:
  alexa_notify:
    url: "http://<IP_DEL_SERVIDOR>:8080/notify"
    method: POST
    headers:
      Content-Type: "application/json"
      # x-api-key: "tu_api_key_secreta"  # Descomenta si usas API_KEY
    payload: >-
      {"creator_name": {{ (message | default('')) | to_json }}{% if expiry_hours is defined and expiry_hours not in ['', None, 'None'] %}, "expiry_hours": {{ expiry_hours | float }}{% endif %}}
```

> **📌 Nota sobre la URL:** Reemplaza `<IP_DEL_SERVIDOR>` por la IP local de tu servidor (ej. `http://192.168.1.50:8080/notify`). Si usas el **Add-on**, pon la IP local de tu máquina de Home Assistant (no uses `localhost` porque Home Assistant Core y el Add-on se ejecutan en contenedores Docker aislados). Si usas **Docker independiente**, pon la IP de la máquina donde esté corriendo el contenedor.

2. Reinicia Home Assistant para aplicar los cambios.
3. Ahora puedes usarlo en cualquier automatización o script así:

```yaml
# Notificación normal (usa el tiempo de expiración por defecto de 24h):
action: rest_command.alexa_notify
data:
  message: "La lavadora ha terminado"

# Notificación con expiración personalizada (ej. expira en 15 minutos):
action: rest_command.alexa_notify
data:
  message: "La puerta del garaje sigue abierta"
  expiry_hours: 0.25
```

4. **(Opcional) Script para la interfaz visual:**
   Para que sea mucho más fácil usarlo desde el editor visual de automatizaciones, puedes crear un script. Ve a **Ajustes > Automatizaciones y escenas > Scripts**, crea un nuevo script, haz clic en los tres puntos de la esquina superior derecha y selecciona **"Editar en YAML"**. Borra lo que haya y pega esto:

   ```yaml
   alias: "Notificar por Alexa"
   icon: mdi:bell-circle-outline
   fields:
     message:
       name: Mensaje
       description: "El texto que leerá Alexa"
       required: true
       selector:
         text:
     expiry_hours:
       name: Horas de expiración
       description: "Horas antes de expirar (opcional, por defecto 24h)"
       required: false
       selector:
         number:
           min: 0.1
           max: 24
           step: 0.5
           unit_of_measurement: h
   sequence:
     - action: rest_command.alexa_notify
       data:
         message: "{{ message }}"
         expiry_hours: "{{ expiry_hours | default(none) }}"
   ```
   *Ahora podrás seleccionar la acción "Notificar por Alexa" en tus automatizaciones y tendrás un cuadro de texto para el mensaje y un selector opcional para la expiración.*

---

## 6. Actualización

### Si usas el Add-on de Home Assistant (Recomendado)
Home Assistant comprobará periódicamente el repositorio y **detectará las nuevas versiones de forma automática**. Cuando haya una actualización disponible:
1. Te aparecerá una notificación de actualización pendiente en tu panel de control o en **Ajustes > Complementos**.
2. Simplemente entra en la ficha de **Alexa Notify Bridge** y haz clic en **Actualizar**. Toda tu configuración se mantendrá intacta.

### Si usas Docker Independiente
Si hay una nueva versión disponible en GitHub, puedes actualizar manualmente desde la terminal sin perder tu configuración (tu archivo `.env` está a salvo porque está excluido en `.gitignore`):

1. Entra en la carpeta del proyecto en tu servidor:
   ```bash
   cd Alexa-Notify-Bridge
   ```
2. Descarga los últimos cambios:
   ```bash
   git pull
   ```
3. Reconstruye y reinicia el contenedor de forma transparente:
   ```bash
   docker compose up -d --build
   ```

---

## Licencia

Este proyecto está bajo la licencia [MIT](LICENSE).

# Alexa Notify Bridge 🚀

[🇪🇸 Español](README_es.md) | [🇬🇧 English](README.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<a href="https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FR91g%2FAlexa-Notify-Bridge" title="Añadir a Home Assistant"><img src="https://brands.home-assistant.io/_/homeassistant/icon.png" height="20" alt="Home Assistant" style="vertical-align: middle;"></a>

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

> **⚠️ Compatibilidad con Alexa+ (Acceso anticipado):** En dispositivos inscritos en el programa de acceso anticipado de **Alexa+**, existe una limitación por parte de Amazon por la que las notificaciones proactivas llegan correctamente a la cuenta (Alexa las lee si le preguntas *"¿qué notificaciones tengo?"*), pero **no se enciende el anillo amarillo** ni suena el aviso en los altavoces Echo. Es un comportamiento propio de Alexa+ que no puede controlarse desde la API. Si necesitas el anillo amarillo, la única solución actual es salir del acceso anticipado y volver a Alexa clásica.

---

## 2. Creación y Configuración de la Skill en Amazon

Para que Alexa te envíe eventos proactivos, necesitas crear una Skill privada en tu cuenta de [Amazon Developer](https://developer.amazon.com/alexa/console/ask) con permisos especiales de notificaciones.

El repositorio incluye un **asistente automático (`setup-skill.sh`)** que se encarga de todo por ti: crea la skill, aplica los permisos proactivos, te permite elegir el nombre (por defecto *"Casa"*) y te muestra directamente en pantalla tu **Alexa Client ID** y **Alexa Client Secret**.

### Paso A: Ejecutar el asistente automático

Elige **uno de los siguientes métodos** (la **Opción 1** es la más sencilla: no requiere instalar nada en tu PC):

#### Opción 1: En el navegador con GitHub Codespaces (Recomendado — Sin instalar nada)
[![Abrir en GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/R91g/Alexa-Notify-Bridge)

> **ℹ️ ¿Es gratis Codespaces?** Sí. Todas las cuentas personales de GitHub incluyen **60 horas gratis al mes**. Si aparece un aviso de *"paid by user"*, no te cobrarán nada: este proceso dura menos de 2 minutos y entra dentro de tu cuota gratuita mensual.

1. Haz clic en el botón **"Open in GitHub Codespaces"** de arriba (ya viene con `ask-cli` preinstalado).
2. Cuando termine de cargar la terminal en el navegador, ejecuta el asistente:
   ```bash
   ./setup-skill.sh
   ```
3. Sigue las instrucciones en pantalla (al iniciar sesión con Amazon, responde **`n`** cuando te pregunte si quieres vincular una cuenta de AWS — **no necesitas cuenta AWS**).
4. Copia el **`ALEXA_CLIENT_ID`** y **`ALEXA_CLIENT_SECRET`** que el asistente imprimirá al final.
5. ¡Listo! Ya puedes cerrar o borrar el Codespace.

---

#### Opción 2: Con Docker en un solo comando (Para usuarios de Docker)
Si ya tienes Docker instalado, puedes ejecutar el mismo asistente en un contenedor efímero sin instalar Node.js en tu sistema *(ejecuta el comando desde la raíz del repositorio)*:

- **En Linux / macOS:**
  ```bash
  docker run -it --rm -v "$(pwd):/repo" node:lts-alpine sh /repo/setup-skill.sh
  ```
- **En Windows (PowerShell):**
  ```powershell
  docker run -it --rm -v "${PWD}:/repo" node:lts-alpine sh /repo/setup-skill.sh
  ```

---

#### Opción 3: En local con Node.js
Si ya tienes [Node.js](https://nodejs.org/) en tu equipo, ejecuta desde la raíz del repositorio:
```bash
./setup-skill.sh
```
*(Si `ask-cli` no está instalado, el script lo instalará automáticamente).*

<details>
<summary>🛠️ Método manual (avanzado, sin usar el asistente)</summary>

Si prefieres hacerlo paso a paso manualmente:
1. Entra en [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask), crea una Skill nueva (**Custom Model**) y apunta su **Skill ID**.
2. Instala y configura ASK CLI:
   ```bash
   npm install -g ask-cli
   ask configure --no-browser   # Responde 'n' a vincular cuenta AWS
   ```
3. *(Opcional)* Edita `alexa-skill/skill.json` (en **UTF-8**) si quieres cambiar el nombre `"Casa"`.
4. Sube el manifiesto a tu Skill:
   ```bash
   ask smapi update-skill-manifest -s <TU_SKILL_ID> -g development --manifest "file:alexa-skill/skill.json"
   ```
5. Obtén tus credenciales con `ask smapi get-skill-credentials -s <TU_SKILL_ID>` o en **Alexa Developer Console → Tu Skill → Build → Permissions** (al final de la página).

</details>

> **ℹ️ Sobre el endpoint URI:** El archivo `alexa-skill/skill.json` contiene un ARN de Lambda (`ReflectorTemplateSkill`). Se trata de un **endpoint público genérico proporcionado por Amazon** usado como placeholder — no es un recurso personal. **No lo modifiques.** Las notificaciones proactivas no pasan por este endpoint; es solo un campo obligatorio del manifiesto.

### Paso B: Habilitar la Skill en tu cuenta (¡Último paso en la app de Alexa!)
Por privacidad, Amazon siempre exige activar la skill y conceder el permiso de notificaciones desde la app móvil:

1. Abre la app de Alexa en tu móvil (asegúrate de usar la misma cuenta de Amazon que usaste en el Paso A).
2. Ve a **Más** > **Skills y juegos** > haz scroll hasta abajo y entra en **Tus Skills**.
3. En la pestaña **Desarrollo** (o *Dev*), verás la skill que acabas de crear.
4. Toca sobre ella, pulsa **Activar para usar** (*Enable to use*) y **concédele el permiso de Notificaciones**.

---

## 3. Instalación

Elige el método que mejor se adapte a tu entorno:

### Opción A: Add-on de Home Assistant (Recomendado)

La forma más sencilla si ya usas Home Assistant:

[![Añadir repositorio a Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FR91g%2FAlexa-Notify-Bridge)

*(O si prefieres añadirlo manualmente)*:

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
| `/health` | `GET` | Health check ligero (devuelve `{"status": "ok"}`, sin autenticación) |
| `/status` | `GET` | Estado de configuración, región, credenciales y token activo de Amazon (protegido por `API_KEY` si está definida) |
| `/history` | `GET` | Devuelve el historial en memoria (más recientes primero). Soporta `?limit=N` (por defecto 50) |

#### POST `/notify` — Cuerpo de la petición

| Campo | Tipo | Requerido | Por defecto | Descripción |
|-------|------|-----------|-------------|-------------|
| `message` (o `creator_name`) | `string` | ✅ | — | El texto que Alexa leerá en voz alta — acepta tanto `message` como `creator_name` (si supera 256 caracteres, se trunca automáticamente a 253 + '...') |
| `urgency` | `string` | ❌ | `"URGENT"` | Debe ser `"URGENT"` |
| `expiry_hours` | `number` | ❌ | `24` | Horas hasta que la notificación expira (acotado automáticamente entre 5 min y 24h) |
| `debounce_seconds` | `number` | ❌ | `0` (o config) | Ventana en segundos para ignorar notificaciones idénticas consecutivas |

> **✂️ Truncado automático:** Si el mensaje supera el límite estricto de 256 caracteres de Amazon (ej. al usar plantillas largas en Home Assistant), el puente lo recorta automáticamente a 253 caracteres + `...`. La notificación nunca se pierde y la respuesta incluye `"truncated": true`.
>
> **🛡️ Filtro anti-duplicados (Debounce):** Si un sensor con rebotes o una automatización manda el mismo mensaje exacto dentro de la ventana de tiempo (configurable globalmente con `DEBOUNCE_SECONDS` o por petición), el puente lo descarta respondiendo `{"status": "ignored", "debounced": true}` para no saturar al usuario con repeticiones.
>
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
      {"creator_name": {{ (message | default('')) | to_json }}{% if expiry_hours is defined and expiry_hours not in ['', None, 'None'] %}, "expiry_hours": {{ expiry_hours | float }}{% endif %}{% if debounce_seconds is defined and debounce_seconds not in ['', None, 'None'] %}, "debounce_seconds": {{ debounce_seconds | float }}{% endif %}}
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
     debounce_seconds:
       name: Segundos de debounce
       description: "Segundos para ignorar mensajes idénticos consecutivos (opcional)"
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
   *Ahora podrás seleccionar la acción "Notificar por Alexa" en tus automatizaciones y tendrás un cuadro de texto para el mensaje y selectores opcionales para la expiración y el filtro anti-duplicados.*

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

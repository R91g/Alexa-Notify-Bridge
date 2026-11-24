# Alexa Notify Bridge — Documentación

🇪🇸 Español | [🇬🇧 English](https://github.com/R91g/Alexa-Notify-Bridge/blob/master/addon/DOCS.md)

Un puente (*bridge*) ligero que te permite enviar notificaciones proactivas personalizadas a tus dispositivos Amazon Echo (Alexa) mediante peticiones HTTP locales, directamente desde Home Assistant.

Alexa encenderá el anillo amarillo y te leerá las notificaciones cuando le preguntes: *"Alexa, ¿qué notificaciones tengo?"*.

---

## Requisitos previos

Antes de instalar este complemento, necesitas crear una Skill privada en tu cuenta de Amazon Developer para obtener las credenciales necesarias. Sigue la guía **"Creación y Configuración de la Skill en Amazon"** en el [README en español](https://github.com/R91g/Alexa-Notify-Bridge/blob/master/README_es.md#2-creaci%C3%B3n-y-configuraci%C3%B3n-de-la-skill-en-amazon).

Necesitarás:
- **Alexa Client ID**
- **Alexa Client Secret**

Encontrarás ambos en [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask) → Tu Skill → Build → Permissions.

> **⚠️ Compatibilidad con Alexa+ (Acceso anticipado):** En dispositivos inscritos en el programa de acceso anticipado de **Alexa+**, las notificaciones proactivas siguen llegando correctamente a tu cuenta (Alexa las lee si le preguntas *"¿qué notificaciones tengo?"*), pero **no se enciende el anillo amarillo** ni suena el aviso. Es una limitación propia de Alexa+ fuera del control del puente; salir del acceso anticipado devuelve el funcionamiento normal del anillo amarillo.

---

## Configuración

Tras instalar el complemento, ve a la pestaña **Configuración** y rellena las siguientes opciones:

| Opción | Requerido | Por defecto | Descripción |
|--------|-----------|-------------|-------------|
| **Alexa Client ID** | ✅ | — | El Client ID de tu Skill de Alexa |
| **Alexa Client Secret** | ✅ | — | El Client Secret de tu Skill de Alexa |
| **Clave de API** | ❌ | *(vacío)* | Contraseña opcional para proteger los endpoints `/notify`, `/history` y `/status` |
| **Región de la API de Amazon** | ✅ | `EU` | Tu región de Amazon: `NA` (Norteamérica), `EU` (Europa), `FE` (Lejano Oriente) |
| **Nivel de log** | ✅ | `INFO` | Nivel de detalle del registro: `DEBUG`, `INFO`, `WARNING` o `ERROR` |
| **Expiración de notificaciones (horas)** | ✅ | `24` | Horas hasta que expiran las notificaciones (0.1–24). Se puede sobrescribir en cada petición |
| **Filtro anti-duplicados (segundos)** | ❌ | `0` | Segundos mínimos para ignorar notificaciones idénticas consecutivas (0 = desactivado) |

> **Consejo de seguridad:** Es muy recomendable configurar una Clave de API. Si la defines, todas las peticiones a `/notify`, `/history` y `/status` deberán incluir la cabecera `x-api-key: tu_clave`.

---

## Uso

Una vez iniciado el complemento, el puente escuchará en el **puerto 8080**. Puedes enviar notificaciones mediante peticiones HTTP POST.

### Configurar un `rest_command` en Home Assistant

La forma más limpia de usar este complemento es creando un `rest_command`. Añade lo siguiente a tu archivo `configuration.yaml`:

```yaml
rest_command:
  alexa_notify:
    url: "http://<IP_DE_TU_HOME_ASSISTANT>:8080/notify"
    method: POST
    headers:
      Content-Type: "application/json"
      # x-api-key: "tu_api_key"  # Descomenta si has configurado una Clave de API
    payload: >-
      {"creator_name": {{ (message | default('')) | to_json }}{% if expiry_hours is defined and expiry_hours not in ['', None, 'None'] %}, "expiry_hours": {{ expiry_hours | float }}{% endif %}{% if debounce_seconds is defined and debounce_seconds not in ['', None, 'None'] %}, "debounce_seconds": {{ debounce_seconds | float }}{% endif %}}
```

> **Nota:** Sustituye `<IP_DE_TU_HOME_ASSISTANT>` por la IP local de tu servidor de Home Assistant (ej. `http://192.168.1.50:8080/notify`). No uses `localhost` porque Home Assistant Core y los complementos se ejecutan en contenedores Docker aislados.

Tras reiniciar Home Assistant, ya puedes usarlo en cualquier automatización o script:

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

### Opcional: Script para el editor visual

Para usarlo cómodamente desde el editor visual de automatizaciones, crea un script en **Ajustes > Automatizaciones y escenas > Scripts**:

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

---

## Referencia de la API

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/notify` | `POST` | Enviar una notificación proactiva a Alexa |
| `/health` | `GET` | Health check ligero (devuelve `{"status": "ok"}`, sin autenticación) |
| `/status` | `GET` | Estado de configuración, región, credenciales y token activo de Amazon (protegido por `API_KEY` si está definida) |
| `/history` | `GET` | Devuelve el historial en memoria (más recientes primero). Soporta `?limit=N` (por defecto 50) |

### POST `/notify` — Cuerpo de la petición

| Campo | Tipo | Requerido | Por defecto | Descripción |
|-------|------|-----------|-------------|-------------|
| `message` (o `creator_name`) | `string` | ✅ | — | El texto que Alexa leerá en voz alta — acepta tanto `message` como `creator_name` (si supera 256 caracteres, se trunca automáticamente a 253 + '...') |
| `urgency` | `string` | ❌ | `"URGENT"` | Debe ser `"URGENT"` |
| `expiry_hours` | `number` | ❌ | `24` | Horas hasta que la notificación expira (acotado automáticamente entre 5 min y 24h) |
| `debounce_seconds` | `number` | ❌ | `0` (o config) | Ventana en segundos para ignorar notificaciones idénticas consecutivas |

> **✂️ Truncado automático:** Si un mensaje supera el límite estricto de 256 caracteres de Amazon (ej. al renderizar plantillas largas en Home Assistant), el puente lo recorta automáticamente a 253 caracteres + `...`. La notificación nunca se pierde y la respuesta incluye `"truncated": true`.
>
> **🛡️ Filtro anti-duplicados (Debounce):** Si un sensor con rebotes o una automatización envía el mismo texto exacto varias veces dentro de la ventana configurada, el puente descarta los duplicados respondiendo `{"status": "ignored", "debounced": true}` para no saturar tus altavoces.

---

## Cómo funcionan las notificaciones (el truco del "Creador")

La API de notificaciones de Amazon utiliza una plantilla fija:
> *"De [Skill], tienes un mensaje nuevo de **[Creador]**"*

Para que Alexa lea texto libre, el mensaje se envía dentro del campo `creator_name` (la misma técnica que usan skills populares como *Notify Me*).

Cuando preguntes *"Alexa, ¿qué notificaciones tengo?"*, dirá:
> *"Tienes una notificación nueva de Casa. De Casa, tienes un mensaje nuevo de **la lavadora ha terminado**."*

> **💡 Consejo:** Puedes cambiar el nombre de la skill (la parte de "Casa") editando el archivo `skill.json` antes de subir el manifiesto. Consulta el [README del proyecto](https://github.com/R91g/Alexa-Notify-Bridge/blob/master/README_es.md) para más detalles.

---

## Límite de peticiones (Rate Limiting)

Para evitar bloqueos temporales de Amazon, el puente limita el envío a **10 notificaciones cada 10 segundos**. Si se supera, devuelve HTTP `429 Too Many Requests` con la cabecera `Retry-After`.

---

## Reintentos automáticos

Si la API de Amazon devuelve un error de servidor (`5xx`) o falla la red, el puente **reintenta automáticamente una vez** tras 2 segundos (o renueva el token ante un `401`) antes de devolver un error.

---

## Solución de problemas

- **¿No llegan las notificaciones?** Comprueba que has activado la skill en la app de Alexa y le has concedido el permiso de Notificaciones.
- **¿No se enciende el anillo amarillo en Alexa+ (Acceso anticipado)?** En dispositivos inscritos en el programa de acceso anticipado de **Alexa+**, las notificaciones se siguen encolando (Alexa las lee si le preguntas *"¿qué notificaciones tengo?"*), pero Amazon actualmente no enciende el anillo amarillo ni reproduce el sonido. Es una limitación de Alexa+ ajena al puente; salir del acceso anticipado restaura el comportamiento normal.
- **¿Errores de autenticación en el log?** Verifica tu Alexa Client ID y Alexa Client Secret en la pestaña Configuración del complemento.
- **¿Región incorrecta?** Asegúrate de que la región configurada coincide con la región de Amazon donde están registrados tus dispositivos Alexa.
- **Revisa los registros:** Entra en la pestaña **Registro** (*Log*) del complemento en Home Assistant para ver información detallada. Puedes cambiar el nivel de log a `DEBUG` para obtener el máximo detalle.

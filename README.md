# 🤖 VaultBot — Sistema de Backup y Restauración de Miembros

**VaultBot** es un bot de Discord asíncrono construido con **discord.py** y **FastAPI**, diseñado para autenticar usuarios mediante OAuth2 y añadirlos a cualquier servidor de Discord de forma automática.

---

## ✨ Características

- 💾 **Backup de miembros** — Guarda tokens OAuth2 de usuarios de forma persistente.
- 🚀 **Restauración por servidor** — Añade usuarios autenticados a cualquier servidor con un comando.
- 🔐 **Sistema de webhooks por servidor** — Cada servidor registra su propio webhook; solo el owner gestiona la BD.
- 🛡️ **Control de canales** — Los comandos solo funcionan en los canales configurados.
- 📣 **Mensaje automático en #invitar-bot** — Al arrancar el bot, el canal se actualiza solo.
- ⚡ **Totalmente asíncrono** — FastAPI + discord.py para máximo rendimiento.
- 🔄 **Refresco de tokens** — Mantén los tokens válidos sin esfuerzo.
- 📊 **Estado en tiempo real** — Latencia, auths, servidores y webhooks activos.

---

## 📁 Estructura de archivos

```
VaultBot/
├── bot.py           ← Código principal del bot
├── config.json      ← Configuración (token, IDs, canales...)
├── auths.txt        ← Base de datos de tokens (se genera solo)
├── webhooks.json    ← Webhooks registrados por servidor (se genera solo)
└── README.md        ← Esta guía
```

---

## ⚙️ Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/TU_USUARIO/VaultBot.git
cd VaultBot
```

### 2. Instalar dependencias
```bash
pip install discord.py fastapi uvicorn requests
```

### 3. Configurar `config.json`

Abre `config.json` y rellena **todos** los campos:

| Campo | Descripción | Cómo obtenerlo |
|---|---|---|
| `token` | Token de tu bot de Discord | Portal de Discord Developers → Tu app → Bot → Token |
| `secret` | Client Secret de OAuth2 | Portal → Tu app → OAuth2 → Client Secret |
| `id` | Client ID de tu aplicación | Portal → Tu app → General → Application ID |
| `redirect` | URL de redirección OAuth2 | `http://127.0.0.1:8000/callback` (local) o tu dominio |
| `api_endpoint` | Endpoint API Discord | Déjalo como está: `https://discord.com/api/v10` |
| `logs` | Array de webhooks para logs | Crea webhooks en un canal privado de tu servidor |
| `owner_id` | Tu ID de Discord | Discord → Ajustes → Avanzado → Modo desarrollador → clic derecho en tu nombre |
| `canal_invitar_bot` | ID del canal #invitar-bot | Clic derecho en el canal → Copiar ID |
| `canal_verificar` | ID del canal #verificarse | Clic derecho en el canal → Copiar ID |
| `canal_miembros` | ID del canal #dar-miembros | Clic derecho en el canal → Copiar ID |
| `canal_general` | ID del canal general | Clic derecho en el canal → Copiar ID |

### 4. Configurar OAuth2 en Discord Developers

1. Ve a [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Selecciona tu aplicación → **OAuth2**
3. En **Redirects**, añade: `http://127.0.0.1:8000/callback`
4. Guarda los cambios

### 5. Crear canales en tu servidor

Crea estos 4 canales en tu servidor principal:

| Canal | Uso |
|---|---|
| `#invitar-bot` | Mensaje automático con instrucciones y enlace de invitación |
| `#verificarse` | Comparte el enlace de auth con usuarios externos |
| `#dar-miembros` | Canal privado donde tú usas `!miembros` |
| `#general` (o el que quieras) | Comandos generales como `!ayuda`, `!enlace`, `!estado` |

Pon los IDs de esos canales en `config.json`.

---

## ▶️ Arrancar el bot

```bash
python bot.py
```

El bot arrancará FastAPI en el puerto `8000` y se conectará a Discord.  
Al iniciar, enviará automáticamente el mensaje de bienvenida en `#invitar-bot`.

---

## 📋 Comandos — Guía completa

### 🌐 Comandos generales (cualquier servidor)

---

#### `!ayuda`
Muestra esta guía completa dentro de Discord con todos los comandos, explicaciones y el paso a paso para empezar.

**Uso:** `!ayuda`

---

#### `!invitarbot`
Muestra el enlace para invitar VaultBot a cualquier servidor, junto con el enlace de verificación y las instrucciones de inicio.

**Uso:** `!invitarbot`

---

#### `!enlace`
Genera el enlace OAuth2 para que los usuarios se verifiquen. Al hacer clic, el usuario acepta los permisos y queda guardado en la base de datos.

**Uso:** `!enlace`

---

#### `!estado`
Muestra estadísticas del bot en tiempo real.

**Uso:** `!estado`

Muestra:
- 🏓 Latencia en ms
- 💾 Total de usuarios autenticados en la BD
- 🖥️ Número de servidores donde está el bot
- 🔗 Webhooks activos registrados
- 🤖 Nombre del bot y prefijo

---

#### `!setwebhook <url>`
Registra el webhook de tu servidor para poder recibir miembros. Solo pueden usarlo administradores del servidor.

**Uso:** `!setwebhook https://discord.com/api/webhooks/123456/abc...`

**Paso a paso:**
1. Ve a tu servidor → Ajustes del servidor → Integraciones → Webhooks
2. Crea un nuevo webhook en el canal que quieras
3. Copia la URL del webhook
4. En tu servidor (con el bot presente), escribe: `!setwebhook <url_copiada>`
5. El bot confirmará que se guardó correctamente

**Nota:** El bot borra tu mensaje automáticamente para no exponer la URL del webhook.

---

### 🚀 Dar miembros

---

#### `!miembros <cantidad>`
Añade usuarios autenticados al servidor donde se ejecuta el comando.

**Uso:** `!miembros 50`

**Requisitos:**
- El bot debe estar en tu servidor
- Debes haber registrado tu webhook con `!setwebhook`
- Solo funciona en el canal configurado como `canal_miembros`

**Proceso:**
1. El bot carga los usuarios de la base de datos
2. Los baraja aleatoriamente
3. Los va añadiendo uno a uno con barra de progreso en tiempo real
4. Al terminar, muestra un resumen con añadidos, fallidos y tiempo total
5. Notifica el resultado por tu webhook

**Ejemplo de salida:**
```
✅ Operación completada
Servidor: TuServidor
Añadidos: 48
Fallidos: 2
Intentos: 50
Tiempo: 0m 23s
```

---

### 🔧 Comandos de administración (solo owner)

Solo el usuario con el ID definido en `owner_id` puede usarlos.

---

#### `!contar`
Muestra cuántos usuarios únicos hay en la base de datos `auths.txt`.

**Uso:** `!contar`

---

#### `!refrescar`
Refresca los tokens OAuth2 de todos los usuarios guardados para que no expiren.

**Uso:** `!refrescar`

Muestra una barra de progreso en tiempo real con:
- Tokens refrescados correctamente ✅
- Tokens que fallaron ❌
- Tiempo total empleado

**Recomendación:** Úsalo cada 7-14 días para mantener los tokens activos.

---

#### `!transferir <guild_id> <cantidad>`
Añade usuarios directamente a cualquier servidor por su ID (sin necesidad de webhook).

**Uso:** `!transferir 123456789012345678 100`

**Requisitos:**
- El bot debe estar en el servidor destino
- Solo el owner puede usar este comando

---

## 🔒 Sistema de seguridad por canales

Los comandos están restringidos por canal:

| Canal | Comandos permitidos |
|---|---|
| `#invitar-bot` | Mensaje automático al arrancar + `!invitarbot` |
| `#verificarse` | `!enlace` para compartir con usuarios |
| `#dar-miembros` | `!miembros`, `!contar`, `!refrescar`, `!estado`, `!transferir` |
| Cualquier canal | `!ayuda`, `!invitarbot`, `!estado` |

Si alguien intenta usar un comando en el canal incorrecto, el bot avisa y borra el mensaje.

---

## 🌊 Flujo completo de uso

```
1. Alguien invita VaultBot a su servidor (!invitarbot o enlace directo)
        ↓
2. El dueño del servidor usa !setwebhook <url> para registrarse
        ↓
3. El dueño comparte !enlace con sus usuarios
        ↓
4. Los usuarios hacen clic → aceptan OAuth2 → quedan en auths.txt
        ↓
5. El dueño usa !miembros 50 en el canal configurado
        ↓
6. VaultBot añade 50 usuarios a su servidor automáticamente
        ↓
7. El webhook del servidor recibe notificación con el resumen
```

---

## ❓ Preguntas frecuentes

**¿Los tokens de los usuarios expiran?**  
Sí. Usa `!refrescar` periódicamente para renovarlos.

**¿Puedo usar el bot en varios servidores a la vez?**  
Sí. Cada servidor registra su propio webhook con `!setwebhook` y opera de forma independiente.

**¿Los usuarios saben que se les añade?**  
Solo verán que entraron al servidor. No reciben notificación especial.

**¿El archivo auths.txt se puede compartir?**  
No. Contiene tokens privados. Mantenlo seguro.

**¿Qué pasa si el bot se reinicia?**  
Los webhooks se guardan en `webhooks.json` y se cargan automáticamente al arrancar.

---

## ⚠️ Aviso legal

VaultBot está diseñado para backup y restauración controlada de miembros con su consentimiento (OAuth2). El uso para spam, añadir miembros sin consentimiento o violar los Términos de Servicio de Discord queda bajo responsabilidad exclusiva del usuario. Úsalo responsablemente.
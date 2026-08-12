import os
import logging
import time
from datetime import datetime
import requests
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Configuración de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_intervals_data(days=3):
    """Consulta los datos de salud/bienestar en Intervals.icu para los últimos días"""
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID")
    api_key = os.getenv("INTERVALS_API_KEY")

    if not api_key or not athlete_id:
        return "Variables de Intervals.icu no configuradas en Railway."
        
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/wellness"
    try:
        response = requests.get(url, auth=('API_KEY', api_key), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                # Devolver los últimos registros para tener contexto de tendencia
                recent = data[-days:]
                return str(recent)
            return str(data)
        return f"Sin datos de Intervals.icu (Código {response.status_code})."
    except Exception as e:
        return f"Error de conexión con Intervals.icu: {e}"

def is_user_allowed(user_id):
    allowed_user_id = os.getenv("ALLOWED_TELEGRAM_USER_ID")
    if allowed_user_id and str(user_id) != str(allowed_user_id):
        return False
    return True

async def post_init(application: Application):
    """Registra automáticamente el menú desplegable de comandos en la app de Telegram"""
    commands = [
        BotCommand("resumen", "Informe completo de recuperación y estado diario"),
        BotCommand("datos", "Ver métricas numéricas sincronizadas de Garmin/Intervals"),
        BotCommand("ayuda", "Instrucciones de uso del bot"),
        BotCommand("start", "Reiniciar la conversación")
    ]
    await application.bot.set_my_commands(commands)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("Acceso no autorizado.")
        return
    msg = (
        "¡Hola! Soy tu asistente de rendimiento y recuperación.\n\n"
        "💬 Puedes chatear conmigo de forma natural sobre dudas de entreno, descansos o cargas.\n\n"
        "📌 Comandos útiles:\n"
        "• /resumen - Informe biométrico y sugerencia para el día.\n"
        "• /datos - Ver datos numéricos crudos sincronizados de Intervals.\n"
        "• /ayuda - Recordatorio de comandos."
    )
    await update.message.reply_text(msg)

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("Acceso no autorizado.")
        return
    await start(update, context)

async def datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los datos crudos recientes descargados desde Intervals.icu"""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("Acceso no autorizado.")
        return
        
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    intervals_info = get_intervals_data(days=1)
    await update.message.reply_text(f"📊 *Datos más recientes en Intervals.icu:*\n\n`{intervals_info}`", parse_mode="Markdown")

async def resumen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera el informe biométrico estructurado cuando se solicita explícitamente"""
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("Acceso no autorizado.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    intervals_info = get_intervals_data(days=3)
    gemini_key = os.getenv("GEMINI_API_KEY")
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    prompt_resumen = f"""
    Eres un entrenador deportivo experto en fisiología del ejercicio y recuperación.
    FECHA ACTUAL: {fecha_actual}

    DATOS RECIENTES DE INTERVALS.ICU (Últimos días):
    {intervals_info}

    INSTRUCCIONES DE FORMATO Y ESTILO:
    1. Genera un informe limpio, directo, profesional y muy fácil de leer en pantalla de móvil.
    2. Sintetiza las métricas clave (FC en reposo, HRV, horas de sueño, ATL/CTL si están disponibles) comparando brevemente con los días previos.
    3. PROHIBIDO usar símbolos de LaTeX (como $\\rightarrow$), encabezados con '###' ni tablas complejas.
    4. Cierra con una RECOMENDACIÓN CONCRETA para hoy (intensidad de sesión, descanso activo o suave).
    """

    try:
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt_resumen,
        )
        output_text = response.text if response.text else "No se pudo generar el resumen."
        await update.message.reply_text(str(output_text))
    except Exception as e:
        logging.error(f"Error procesando Gemini en /resumen: {e}")
        await update.message.reply_text(f"Error generando el resumen: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_allowed(update.effective_user.id):
        await update.message.reply_text("Acceso no autorizado.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    user_prompt = update.message.text
    intervals_info = get_intervals_data(days=2)
    gemini_key = os.getenv("GEMINI_API_KEY")
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    
    prompt_completo = f"""
    Eres un entrenador personal y preparador físico cercano, directo y humano. Hablas por chat de WhatsApp/Telegram.
    FECHA ACTUAL: {fecha_actual}

    CONTEXTO INTERNO DE DATOS BIOMÉTRICOS (INTERVALS.ICU):
    {intervals_info}

    REGLAS DE RESPUESTA:
    1. TONO: Natural, directo, conciso y cercano. Habla de tú a tú.
    2. FORMATO: PROHIBIDO usar encabezados tipo '###', listas robóticas interminables o código LaTeX.
    3. USO DE DATOS BIOMÉTRICOS: Usa estos datos solo como contexto interno para saber si el atleta está fatigado, descansado o sobrecargado. NO recites la lista de métricas a menos que el usuario lo pida expresamente.
    4. BREVEDAD: Para preguntas casuales o dudas rápidas, responde en 2 a 4 frases concisas y prácticas. Ve directo al grano.

    MENSAJE DEL USUARIO:
    {user_prompt}
    """
    
    try:
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt_completo,
        )
        output_text = response.text if response.text else "No pude generar respuesta."
        
        if len(output_text) > 4000:
            for i in range(0, len(output_text), 4000):
                await update.message.reply_text(output_text[i:i+4000])
        else:
            await update.message.reply_text(str(output_text))

    except Exception as e:
        logging.error(f"Error procesando Gemini: {e}")
        await update.message.reply_text(f"Error procesando la consulta: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Excepción capturada en Telegram: {context.error}")

def main():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logging.error("Falta la variable TELEGRAM_BOT_TOKEN en Railway.")
        return

    logging.info("Iniciando bot de Telegram...")
    
    app = Application.builder().token(bot_token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("resumen", resumen))
    app.add_handler(CommandHandler("datos", datos))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    while True:
        try:
            app.run_polling(drop_pending_updates=True)
            break
        except Exception as e:
            logging.error(f"Error en bucle de polling: {e}. Reintentando en 5 segundos...")
            time.sleep(5)

if __name__ == "__main__":
    main()

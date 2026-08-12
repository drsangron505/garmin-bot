import os
import logging
import time
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_intervals_data():
    athlete_id = os.getenv("INTERVALS_ATHLETE_ID")
    api_key = os.getenv("INTERVALS_API_KEY")

    if not api_key or not athlete_id:
        return "Variables de Intervals.icu no configuradas."
        
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/wellness"
    try:
        response = requests.get(url, auth=('API_KEY', api_key), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return str(data[-1])
            return str(data)
        return f"Sin datos recientes (Código {response.status_code})."
    except Exception as e:
        return f"Error de conexión con Intervals.icu: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Aprobado! Ya estoy configurado. Pregúntame lo que quieras o dime 'Dame mi resumen' para ver tu estado de hoy.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Control de seguridad por ID
    allowed_user_id = os.getenv("ALLOWED_TELEGRAM_USER_ID")
    if allowed_user_id and str(update.effective_user.id) != str(allowed_user_id):
        await update.message.reply_text("Acceso no autorizado.")
        return

    # Feedback visual de "Escribiendo..."
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    user_prompt = update.message.text
    intervals_info = get_intervals_data()
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    prompt_completo = f"""
    Eres un entrenador personal y preparador físico cercano, directo y humano. Hablas por chat de WhatsApp.

    CONTEXTO INTERNO DE DATOS BIOMÉTRICOS (INTERVALS.ICU):
    {intervals_info}

    REGLAS DE RESPUESTA:
    1. TONO: Natural, directo, conciso y cercano. Nada de lenguaje académico ni cháchara. Sé práctico.
    2. FORMATO: PROHIBIDO usar encabezados de Markdown tipo '###', listas interminables o código LaTeX. Escribe en párrafos limpios como un mensaje de texto normal.
    3. DATOS DE INTERVALS: Usa estos datos de fondo para saber si el usuario está fatigado o listo, PERO NO recites las métricas (CTL, ATL, TSB, FC) ni desgloses el JSON a menos que el usuario te pida explícitamente un "resumen", "informe" o "¿cómo están mis números?".
    4. BREVEDAD: Para preguntas casuales o dudas rápidas, responde en 2 a 4 frases muy concretas. Ir al grano es la máxima prioridad.

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
    
    app = Application.builder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
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

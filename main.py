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
        return "Variables de Intervals.icu no configuradas en Railway."
        
    url = f"https://intervals.icu/api/v1/athlete/{athlete_id}/wellness"
    try:
        response = requests.get(url, auth=('API_KEY', api_key), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return str(data[-1])
            return str(data)
        return f"Sin datos de Intervals.icu (Código {response.status_code})."
    except Exception as e:
        return f"Error de conexión con Intervals.icu: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu asistente de entrenamiento. Pregúntame sobre tu descanso, HRV o preparación para la sesión de hoy.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security Check
    allowed_user_id = os.getenv("ALLOWED_TELEGRAM_USER_ID")
    if allowed_user_id and str(update.effective_user.id) != str(allowed_user_id):
        await update.message.reply_text("Servicio privado: No tienes permisos para usar este bot.")
        return

    # Indicador de estado "Escribiendo..." en Telegram
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    user_prompt = update.message.text
    intervals_info = get_intervals_data()
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    prompt_completo = f"""
    Eres un entrenador deportivo experto en fisiología, HRV y recuperación deportiva.
    Analiza la consulta del usuario interpretando sus datos biométricos recientes importados desde Garmin a Intervals.icu:

    DATOS RECIENTES DE INTERVALS.ICU:
    {intervals_info}

    MENSAJE DEL USUARIO:
    {user_prompt}

    Responde de forma estructurada, directa y práctica, dando pautas concretas sobre la intensidad del entrenamiento, descanso activo o ajuste de cargas.
    """
    
    try:
        client = genai.Client(api_key=gemini_key)
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt_completo,
        )
        output_text = response.text if response.text else "No se generó respuesta con los datos actuales."
        
        if len(output_text) > 4000:
            for i in range(0, len(output_text), 4000):
                await update.message.reply_text(output_text[i:i+4000])
        else:
            await update.message.reply_text(str(output_text))

    except Exception as e:
        logging.error(f"Error procesando Gemini: {e}")
        await update.message.reply_text(f"Error procesando la consulta con Gemini: {str(e)}")

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

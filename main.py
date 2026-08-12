import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Configuración de logs para diagnóstico en Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Cargar variables de entorno desde Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializar cliente de Google Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def get_intervals_data():
    """Consulta los datos recientes de salud/bienestar en Intervals.icu usando Basic Auth"""
    if not INTERVALS_API_KEY or not INTERVALS_ATHLETE_ID:
        return "Variables de Intervals.icu no configuradas en Railway."
        
    url = f"https://intervals.icu/api/v1/athlete/{INTERVALS_ATHLETE_ID}/wellness"
    try:
        # Autenticación HTTP Basic requerida por Intervals.icu (Usuario: 'API_KEY', Pass: tu clave)
        response = requests.get(url, auth=('API_KEY', INTERVALS_API_KEY), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return str(data[-1])
            return str(data)
        return f"Sin datos de Intervals.icu (Código {response.status_code})."
    except Exception as e:
        return f"Error de conexión con Intervals.icu: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu asistente de entrenamiento. Pregúntame sobre tu descanso o recuperación.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    intervals_info = get_intervals_data()
    
    prompt_completo = f"""
    Eres un entrenador deportivo experto en fisiología y recuperación.
    Analiza la consulta del usuario combinándola con sus datos biométricos recientes importados desde Garmin a Intervals.icu:

    DATOS RECIENTES DE INTERVALS.ICU:
    {intervals_info}

    MENSAJE DEL USUARIO:
    {user_prompt}

    Responde de forma directa, concisa y práctica con recomendaciones sobre descanso, preparación física o carga de entrenamiento.
    """
    
    try:
        response = client.models.generate_content(
            model='gemini-flash-latest',
            contents=prompt_completo,
        )
        output_text = response.text if response.text else "No se generó respuesta con los datos actuales."
        await update.message.reply_text(str(output_text))
    except Exception as e:
        logging.error(f"Error procesando Gemini: {e}")
        await update.message.reply_text(f"Error procesando la consulta con Gemini: {str(e)}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Manejo global de errores para evitar que el proceso de Railway se detenga"""
    logging.error(f"Excepción capturada en la ejecución del bot: {context.error}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logging.error("Falta la variable TELEGRAM_BOT_TOKEN en Railway.")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logging.info("Iniciando bot de Telegram...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

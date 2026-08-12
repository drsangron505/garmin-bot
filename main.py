import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Cargar variables de entorno desde Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicializar cliente de Google Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def get_intervals_data():
    """Consulta los datos recientes de salud/bienestar en Intervals.icu"""
    url = f"https://intervals.icu/api/v1/athlete/{INTERVALS_ATHLETE_ID}/wellness"
    headers = {"Authorization": f"Bearer {INTERVALS_API_KEY}"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return str(data[-1])
            return str(data)
        return f"No se pudieron obtener datos de Intervals.icu (Código {response.status_code})."
    except Exception as e:
        return f"Error de conexión con Intervals.icu: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Soy tu asistente de entrenamiento. Pregúntame lo que quieras sobre tu descanso o recuperación.")

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
            model='gemini-2.0-flash',
            contents=prompt_completo,
        )
        # Validar que la respuesta contenga texto antes de enviarla a Telegram
        output_text = response.text if response.text else "No se pudo generar un análisis con los datos actuales."
        await update.message.reply_text(str(output_text))
    except Exception as e:
        await update.message.reply_text(f"Error al procesar la consulta con Gemini: {str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()

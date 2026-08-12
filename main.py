import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai

# Configuración de logs para diagnóstico en Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Servidor HTTP secundario para superar el Health Check de Railway
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")
        
    def log_message(self, format, *args):
        pass  # Silenciar logs continuos del health check para mantener limpia la consola

def start_health_check_server():
    port = os.getenv("PORT")
    if port:
        try:
            port_num = int(port)
            server = HTTPServer(('0.0.0.0', port_num), HealthCheckHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            logging.info(f"Servidor de Health Check activo en puerto {port_num}")
        except Exception as e:
            logging.error(f"No se pudo iniciar el servidor de Health Check: {e}")

# Variables de entorno desde Railway
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
INTERVALS_ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Inicialización del cliente de Google Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

def get_intervals_data():
    """Consulta los datos recientes de salud/bienestar en Intervals.icu usando Basic Auth"""
    if not INTERVALS_API_KEY or not INTERVALS_ATHLETE_ID:
        return "Variables de Intervals.icu no configuradas en Railway."
        
    url = f"https://intervals.icu/api/v1/athlete/{INTERVALS_ATHLETE_ID}/wellness"
    try:
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
        
        # Telegram limita cada mensaje a 4096 caracteres. Dividimos en bloques de 4000 si supera el límite.
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
    if not TELEGRAM_BOT_TOKEN:
        logging.error("Falta la variable TELEGRAM_BOT_TOKEN en Railway.")
        return

    # Levantar el servidor HTTP interno para satisfacer el Health Check de Railway
    start_health_check_server()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)
    
    logging.info("Iniciando bot de Telegram...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

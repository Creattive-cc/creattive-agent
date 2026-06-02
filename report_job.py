"""Entry point do Cloud Run Job para disparo do resumo diário."""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from agent.reporter import send_daily_report

if __name__ == "__main__":
    try:
        result = send_daily_report()
        print("Resumo enviado com sucesso:", result)
        sys.exit(0)
    except Exception as e:
        print("Erro ao enviar resumo:", e)
        sys.exit(1)

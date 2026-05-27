"""
api.py — FastAPI backend do creattive-agent.
Responsabilidade: webhook WhatsApp, endpoint de chat REST e health check.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agent.core import CreattiveAgent
from dotenv import load_dotenv
import os

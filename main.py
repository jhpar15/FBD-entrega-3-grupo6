from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

client = MongoClient("mongodb://ISIS2304A17202610:QErnMWHEO0AZ@157.253.236.88:8087/ISIS2304A17202610?authSource=admin")
db = client["ISIS2304A17202610"]

@app.get("/")
def inicio():
    return {"estado": "API Dann-Alpes funcionando correctamente"}

# -----------------------------------------
# SECCIÓN: RESEÑAS (RF1, RF4)
# -----------------------------------------
@app.get('/hoteles/{hotel_id}/resenas')
def get_resenas(hotel_id: str):
    # RF4: Consultar reseñas publicadas de un hotel específico
    resenas = list(db["resenas"].find({"hotel_id": hotel_id, "estado": "publicada"}, {"_id": 0}))
    return resenas

@app.post('/hoteles/{hotel_id}/resenas')
def post_resena(hotel_id: str, datos: dict):
    # RF1: Crear una nueva reseña
    datos['hotel_id'] = hotel_id
    datos['fecha_creacion'] = datetime.now()
    datos['estado'] = "publicada"
    datos['destacada'] = False
    datos['utilidad'] = {"total_votos": 0, "usuarios_votaron": []}
    datos['respuesta_admin'] = None
    
    db["resenas"].insert_one(datos)
    
    return {'mensaje': 'Reseña guardada exitosamente'}

# -----------------------------------------
# SECCIÓN: CONSULTAS ANALÍTICAS (RFC1)
# -----------------------------------------
@app.get('/analiticas/top-hoteles')
def get_top_hoteles():
    # RFC1: Top 10 hoteles por calificación
    pipeline = [
        { "$match": { "estado": "publicada" } },
        { "$group": { 
            "_id": "$hotel_id", 
            "calificacion_promedio": { "$avg": "$calificacion" }, 
            "total_resenas": { "$sum": 1 } 
        }},
        { "$sort": { "calificacion_promedio": -1 } },
        { "$limit": 10 }
    ]
    
    resultado = list(db["resenas"].aggregate(pipeline))
    return {"items": resultado}

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
from datetime import datetime

# ==========================================
# RFC2: Evolución de reputación mes a mes
# ==========================================
@app.get("/analiticas/evolucion/{hotel_id}")
def evolucion_hotel(hotel_id: str, anio: int = 2026):
    pipeline = [
        {"$match": {
            "hotel_id": hotel_id,
            "estado": "publicada",
            "fecha_creacion": {
                "$gte": datetime(anio, 1, 1),
                "$lte": datetime(anio, 12, 31, 23, 59, 59)
            }
        }},
        {"$group": {
            "_id": {"$month": "$fecha_creacion"},
            "calificacion_promedio": {"$avg": "$calificacion"},
            "total_resenas": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}},
        {"$project": {
            "_id": 0,
            "mes": "$_id",
            "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
            "total_resenas": 1
        }}
    ]
    resultado = list(db.resenas.aggregate(pipeline))
    return {"items": resultado}

# ==========================================
# RFC3: Perfil comparativo por ciudad
# ==========================================
@app.get("/analiticas/comparativo/{ciudad}")
def comparativo_ciudad(ciudad: str):
    pipeline = [
        {"$match": {"ciudad": ciudad}},
        {"$lookup": {
            "from": "resenas",
            "localField": "_id",
            "foreignField": "hotel_id",
            "as": "resenas_hotel",
            "pipeline": [{"$match": {"estado": "publicada"}}]
        }},
        {"$unwind": {
            "path": "$resenas_hotel",
            "preserveNullAndEmptyArrays": True
        }},
        {"$group": {
            "_id": "$_id",
            "nombre_hotel": {"$first": "$nombre"},
            "ciudad": {"$first": "$ciudad"},
            "calificacion_promedio": {"$avg": "$resenas_hotel.calificacion"},
            "total_resenas": {"$sum": 1},
            "resenas_con_respuesta": {
                "$sum": {"$cond": [{"$ne": ["$resenas_hotel.respuesta_admin", None]}, 1, 0]}
            },
            "resenas_destacadas": {
                "$sum": {"$cond": ["$resenas_hotel.destacada", 1, 0]}
            }
        }},
        {"$project": {
            "_id": 0,
            "hotel_id": "$_id",
            "nombre_hotel": 1,
            "ciudad": 1,
            "calificacion_promedio": {"$round": ["$calificacion_promedio", 2]},
            "total_resenas": 1,
            "porcentaje_con_respuesta": {
                "$round": [{"$multiply": [{"$divide": ["$resenas_con_respuesta", "$total_resenas"]}, 100]}, 1]
            },
            "porcentaje_destacadas": {
                "$round": [{"$multiply": [{"$divide": ["$resenas_destacadas", "$total_resenas"]}, 100]}, 1]
            }
        }},
        {"$sort": {"calificacion_promedio": -1}}
    ]
    resultado = list(db.hoteles.aggregate(pipeline))
    return {"items": resultado}

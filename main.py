from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Conexión a MongoDB
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
    resenas = list(db["resenas"].find({"hotel_id": hotel_id, "estado": "publicada"}))
    return {"items": resenas}

@app.post('/hoteles/{hotel_id}/resenas')
def post_resena(hotel_id: str, datos: dict):
    # NUEVA REGLA: Verifica que no haya reseñado esta reserva antes
    existe = db["resenas"].find_one({"reserva_id": datos["reserva_id"]})
    if existe:
        raise HTTPException(status_code=400, detail="Ya existe una reseña para esta reserva.")

    # RF1: Crear una nueva reseña
    datos['_id'] = f"resena_{uuid.uuid4().hex[:8]}"
    datos['hotel_id'] = hotel_id
    datos['fecha_creacion'] = datetime.now()
    datos['estado'] = "publicada"
    datos['destacada'] = False
    datos['votos_utilidad'] = [] # Modificado para alinear perfectamente con el RF5
    datos['respuesta_admin'] = None
    
    db["resenas"].insert_one(datos)
    return {'mensaje': 'Reseña guardada exitosamente'}


# -----------------------------------------
# SECCIÓN: CONSULTAS ANALÍTICAS (RFC1, RFC2, RFC3)
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

@app.get("/analiticas/evolucion/{hotel_id}")
def evolucion_hotel(hotel_id: str, anio: int = 2026):
    # RFC2: Evolución de reputación mes a mes
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

@app.get("/analiticas/comparativo/{ciudad}")
def comparativo_ciudad(ciudad: str):
    # RFC3: Perfil comparativo por ciudad
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


# -----------------------------------------
# SECCIÓN: FUNCIONES DE CLIENTE (RF2, RF3, RF5, RF6)
# -----------------------------------------
@app.get('/clientes/{cliente_id}/resenas')
def get_historial_cliente(cliente_id: str):
    # RF6: Historial de reseñas del cliente
    resenas = list(db["resenas"].find({"cliente_id": cliente_id}))
    return {"items": resenas}

@app.put('/resenas/{resena_id}')
def editar_resena(resena_id: str, datos: dict):
    # RF2: Editar reseña
    actualizacion = {
        "$set": {
            "texto": datos["texto"],
            "calificacion": datos["calificacion"]
        }
    }
    db["resenas"].update_one({"_id": resena_id}, actualizacion)
    return {"mensaje": "Reseña actualizada exitosamente"}

@app.delete('/resenas/{resena_id}')
def eliminar_resena(resena_id: str):
    # RF3: Eliminar reseña (Borrado lógico)
    db["resenas"].update_one({"_id": resena_id}, {"$set": {"estado": "eliminada"}})
    return {"mensaje": "Reseña eliminada exitosamente"}

from pydantic import BaseModel

# Creamos un "molde" estricto para que Python no se confunda al recibir el dato
class Voto(BaseModel):
    cliente_id: str

# ==========================================
# RF5: Marcar reseña como útil 
@app.get('/resenas/{resena_id}/votar/{cliente_id}')
def votar_utilidad_anti_cors(resena_id: str, cliente_id: str):
    # 1. Verificamos si este cliente ya votó
    ya_voto = db["resenas"].count_documents({"_id": resena_id, "votos_utilidad": cliente_id})
    
    if ya_voto > 0:
        raise HTTPException(status_code=400, detail="¡Ya votaste por esta reseña! No se permite voto doble.")

    # 2. Si no ha votado, lo agregamos a la lista
    db["resenas"].update_one(
        {"_id": resena_id},
        {"$addToSet": {"votos_utilidad": cliente_id}}
    )
    return {"mensaje": "¡Tu voto de utilidad ha sido registrado!"}


# -----------------------------------------
# SECCIÓN: ADMINISTRADOR (RF7, RF8, RF9)
# -----------------------------------------
@app.put('/admin/resenas/{resena_id}/respuesta')
def responder_resena(resena_id: str, datos: dict):
    # RF7: Responder reseña
    actualizacion = {
        "$set": {
            "respuesta_admin": {
                "texto": datos["texto"],
                "fecha_respuesta": datetime.now()
            }
        }
    }
    db["resenas"].update_one({"_id": resena_id}, actualizacion)
    return {"mensaje": "Respuesta enviada exitosamente"}

@app.delete('/admin/resenas/{resena_id}')
def admin_eliminar_resena(resena_id: str):
    # RF8: Eliminar reseña (Admin)
    db["resenas"].update_one({"_id": resena_id}, {"$set": {"estado": "eliminada_por_admin"}})
    return {"mensaje": "Reseña eliminada por administrador"}

@app.put('/admin/hoteles/{hotel_id}/destacar/{resena_id}')
def destacar_resena(hotel_id: str, resena_id: str):
    # RF9: Destacar reseña
    db["resenas"].update_many({"hotel_id": hotel_id}, {"$set": {"destacada": False}})
    db["resenas"].update_one({"_id": resena_id}, {"$set": {"destacada": True}})
    return {"mensaje": "Reseña destacada exitosamente"}

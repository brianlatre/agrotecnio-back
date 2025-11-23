import json
import random

def generate_scenario():
    data = {
        "trucks": [],
        "farms": []
    }

    # 1. FLOTA (Standard)
    print("🚚 Configurando flota de transporte...")
    data["trucks"] = [
        {"id": 1, "capacity_tons": 10, "type": "small"}, 
        {"id": 2, "capacity_tons": 10, "type": "small"}, 
        {"id": 3, "capacity_tons": 20, "type": "large"} 
    ]

    # 2. ESTRATEGIA DE DISPERSIÓN (El Triángulo de la Urgencia)
    # Para forzar más camiones, creamos necesidad simultánea en puntos distantes.
    # Un solo camión no puede viajar al Norte, al Oeste y al Centro en 8h.
    
    clusters = [
        # ZONA 1: VIC (Centro - Alta densidad)
        # Ideal para el camión grande: trayectos cortos, mucho volumen.
        {"name": "Vic_Centre", "lat": 41.9300, "lon": 2.2540, "count": 25, "dist_factor": 0.01, "weight_bonus": 0},
        
        # ZONA 2: RIPOLL (Norte - Lejano)
        # Ida y vuelta son ~80km por carreteras lentas. 
        # Si hay urgencia aquí, bloquea un camión durante 2-3 horas.
        {"name": "Ripoll_Muntanya", "lat": 42.2000, "lon": 2.1900, "count": 15, "dist_factor": 0.02, "weight_bonus": 8}, 
        
        # ZONA 3: MOIÀ (Oeste - Media distancia)
        # Otro frente abierto que requiere atención paralela.
        {"name": "Moia_Altipla", "lat": 41.8100, "lon": 2.0900, "count": 10, "dist_factor": 0.015, "weight_bonus": 5}
    ]

    print("🐷 Generando escenario de 'Tempesta Perfecta' (Distancia + Urgencia)...")
    
    farms_generated = 0
    
    for cluster in clusters:
        for _ in range(cluster["count"]):
            # Dispersión geográfica alrededor del nodo
            lat = random.gauss(cluster["lat"], cluster["dist_factor"])
            lon = random.gauss(cluster["lon"], cluster["dist_factor"])
            
            # LÓGICA DE PESO Y VOLUMEN
            # Truco: Las granjas lejanas tienen cerdos MÁS pesados (Panic Mode).
            # Esto obliga al algoritmo a priorizarlas. Si solo tienes 1 camión,
            # se pasará el día yendo a Ripoll y dejará Vic sin atender (penalización).
            # Solución óptima: Enviar pequeños a Ripoll/Moià y el Grande a Vic.
            
            base_weight = 110 + cluster["weight_bonus"] # 110kg base + bono por zona
            w = random.gauss(base_weight, 2.0) # Poca desviación para asegurar urgencia
            
            # Inventario diseñado para "molestar" al grande en rutas lejanas
            # Lotes de ~90 cerdos (10T). 
            # El camión grande (20T) tendría que hacer 2 paradas en la montaña (muy lento) para llenarse.
            # El camión pequeño (10T) hace 1 parada y vuelve (rápido y eficiente).
            inv = random.randint(85, 100)

            # Algunas granjas muy grandes en el centro para justificar el camión grande
            if cluster["name"] == "Vic_Centre" and random.random() < 0.3:
                inv = random.randint(300, 500)
                w = random.uniform(105, 115) # Peso normal, volumen alto

            data["farms"].append({
                "id": f"Farm_{farms_generated + 1}_{cluster['name']}",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "inventory": inv,
                "avg_weight": round(w, 2)
            })
            farms_generated += 1

    # Guardar
    filename = 'scenario_data.json'
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    print(f"✨ Archivo '{filename}' generado.")
    print(f"   - Distribución: {clusters[0]['count']} Vic, {clusters[1]['count']} Ripoll, {clusters[2]['count']} Moià.")
    print(f"   - Estrategia: Alta urgencia en periféria para forzar paralelismo.")

if __name__ == "__main__":
    generate_scenario()
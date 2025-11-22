import math
import json
import logging
import requests
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# --- CONFIGURACIÓN DE LOGGING (FORMATO HISTORIA) ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s | %(message)s', 
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("SmartLogistics")

# --- CONFIGURACIÓN ---
CONFIG = {
    "slaughterhouse": {"lat": 41.930, "lng": 2.254, "max_capacity": 2000},
    "prices": {
        "base_per_kg": 1.56,
        "penalty_medium": 0.15, 
        "penalty_high": 0.20,   
        "transport_small": 1.15, # €/km (10T)
        "transport_large": 1.25, # €/km (20T)
        "fleet_fixed": 2000      
    }
}

@dataclass
class Farm:
    id: str
    lat: float
    lng: float
    pigs: int
    avg_weight: float
    visited_this_week: bool = False

    def get_total_weight(self):
        return self.pigs * self.avg_weight

    def get_market_price_per_kg(self):
        penalty = 0.0
        w = self.avg_weight
        if w < 100 or w > 120: penalty = CONFIG["prices"]["penalty_high"]
        elif w < 105 or w > 115: penalty = CONFIG["prices"]["penalty_medium"]
        return CONFIG["prices"]["base_per_kg"] * (1 - penalty)

class OSRMRouter:
    """Calcula distancias reales y construye la Matriz de Distancias"""
    BASE_URL = "http://router.project-osrm.org/table/v1/driving/"

    def get_distance_matrix(self, locations: List[Tuple[float, float]]):
        logger.info(f"📡 Conectando con API OSRM para calcular matriz de {len(locations)}x{len(locations)} ubicaciones...")
        
        coords = ";".join([f"{lon},{lat}" for lat, lon in locations])
        url = f"{self.BASE_URL}{coords}?annotations=distance"
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("✅ Datos de tráfico real descargados correctamente.")
                return data['distances'] # Matriz en metros
        except Exception as e:
            logger.warning(f"⚠️ API OSRM falló ({str(e)}). Activando modo FALLBACK (Cálculo matemático).")
            return self._create_fallback_matrix(locations)

    def _create_fallback_matrix(self, locations):
        size = len(locations)
        matrix = [[0] * size for _ in range(size)]
        logger.info("🧮 Calculando matriz mediante fórmula Haversine x 1.3 (Factor carretera)...")
        for i in range(size):
            for j in range(size):
                if i != j:
                    matrix[i][j] = self._haversine(locations[i], locations[j]) * 1000 * 1.3
        return matrix

    def _haversine(self, p1, p2):
        R = 6371
        dLat = math.radians(p2[0] - p1[0])
        dLon = math.radians(p2[1] - p1[1])
        a = math.sin(dLat/2)**2 + math.cos(math.radians(p1[0]))*math.cos(math.radians(p2[0]))*math.sin(dLon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

class PigSolverVRP:
    def __init__(self):
        self.router = OSRMRouter()
        self.depot_loc = (CONFIG["slaughterhouse"]["lat"], CONFIG["slaughterhouse"]["lng"])

    def solve_day(self, farms_data: List[dict]):
        print("\n" + "="*60)
        logger.info("🧠 INICIANDO CEREBRO LOGÍSTICO (VRP OPTIMIZER)")
        print("="*60 + "\n")

        # 1. Preparar Datos
        logger.info("--- [PASO 1] ANÁLISIS Y FILTRADO DE GRANJAS ---")
        all_farms = [Farm(**f) for f in farms_data]
        candidates = []

        for f in all_farms:
            weight = f.get_total_weight()
            is_viable = not f.visited_this_week and f.pigs > 0 and f.avg_weight > 95
            
            if is_viable:
                logger.info(f"  ✅ Granja {f.id} ACEPTADA: {f.pigs} cerdos (~{f.avg_weight}kg). Carga total: {weight}kg")
                candidates.append(f)
            else:
                reason = "Ya visitada" if f.visited_this_week else "Peso insuficiente" if f.avg_weight <= 95 else "Sin stock"
                logger.info(f"  ❌ Granja {f.id} RECHAZADA. Motivo: {reason}")

        if not candidates:
            logger.warning("⚠️ No hay candidatos viables para hoy. Abortando misión.")
            return {"routes": [], "summary": {"total_pigs": 0, "net_profit": 0}}

        # Estructura para el Solver
        # Índice 0 siempre es el Depósito (Matadero)
        logger.info(f"  📊 Total Candidatos: {len(candidates)}. Construyendo nodos de ruta...")
        locations = [self.depot_loc] + [(f.lat, f.lng) for f in candidates]
        demands = [0] + [int(f.get_total_weight()) for f in candidates] # Peso en Kg
        
        # 2. Matriz de Distancias
        logger.info("\n--- [PASO 2] CONSTRUCCIÓN DE MATRIZ DE COSTES ---")
        distance_matrix = self.router.get_distance_matrix(locations)
        logger.info(f"  🗺️  Matriz generada: {len(locations)}x{len(locations)} nodos interconectados.")

        # 3. Configurar OR-Tools
        logger.info("\n--- [PASO 3] CONFIGURACIÓN DE RESTRICCIONES MATEMÁTICAS ---")
        manager = pywrapcp.RoutingIndexManager(len(locations), 10, 0) 
        routing = pywrapcp.RoutingModel(manager)

        # Callback de Distancia
        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(distance_matrix[from_node][to_node])

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
        logger.info("  ⚙️  Objetivo del Solver: Minimizar distancia total recorrida.")

        # A. Restricción de CAPACIDAD
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  
            [20000] * 10,  # 20T Max
            True, 
            "Capacity"
        )
        logger.info("  ⚖️  Restricción activada: Máximo 20,000kg por camión.")

        # B. Restricción de PARADAS
        routing.AddConstantDimension(
            1, 
            3 + 1, # 3 granjas + 1 depósito
            True, 
            "Stops"
        )
        logger.info("  🛑 Restricción activada: Máximo 3 paradas por ruta.")

        # 4. Ejecutar Solver
        logger.info("\n--- [PASO 4] EJECUTANDO ALGORITMO DE OPTIMIZACIÓN ---")
        logger.info("  ⏳ Evaluando miles de combinaciones posibles...")
        
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.time_limit.seconds = 2

        solution = routing.SolveWithParameters(search_parameters)

        # 5. Interpretar Resultados
        logger.info("\n--- [PASO 5] ANÁLISIS DE LA SOLUCIÓN ---")
        
        if not solution:
            logger.error("💀 No se encontró solución viable.")
            return {}

        final_routes = []
        total_pigs_processed = 0
        total_profit_global = 0

        for vehicle_id in range(10):
            index = routing.Start(vehicle_id)
            if routing.IsEnd(solution.Value(routing.NextVar(index))):
                continue 

            logger.info(f"\n🚛 [CAMIÓN VIRTUAL #{vehicle_id}] ASIGNADO:")
            
            route_stops = []
            route_distance_m = 0
            route_weight = 0
            
            # Reconstruir ruta
            route_log_str = "  📍 Matadero"
            
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != 0: # Si no es depósito
                    farm = candidates[node_index - 1]
                    route_stops.append(farm)
                    w = demands[node_index]
                    route_weight += w
                    route_log_str += f" -> Granja {farm.id} (+{w}kg)"
                
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                dist_segment = routing.GetArcCostForVehicle(previous_index, index, vehicle_id)
                route_distance_m += dist_segment

            route_log_str += f" -> Matadero (Fin)"
            logger.info(route_log_str)
            logger.info(f"  📦 Carga Final: {route_weight}kg | Distancia: {route_distance_m/1000:.2f}km")

            # Métricas Financieras
            dist_km = route_distance_m / 1000
            
            # DECISIÓN ECONÓMICA DE FLOTA
            if route_weight <= 10000:
                truck_type = "small"
                logger.info(f"  💡 DECISIÓN: Carga < 10T. Usando Camión PEQUEÑO (Ahorro de costes)")
            else:
                truck_type = "large"
                logger.info(f"  💡 DECISIÓN: Carga > 10T. Usando Camión GRANDE (Máxima eficiencia)")

            cost_km = CONFIG["prices"][f"transport_{truck_type}"]
            trip_cost = dist_km * cost_km
            
            # Ingresos
            trip_revenue = 0
            pigs_in_route = 0
            for f in route_stops:
                revenue_f = (f.pigs * f.avg_weight) * f.get_market_price_per_kg()
                trip_revenue += revenue_f
                pigs_in_route += f.pigs

            profit = trip_revenue - trip_cost
            logger.info(f"  💰 Balance Ruta: Ingresos {trip_revenue:.2f}€ - Coste {trip_cost:.2f}€ = BENEFICIO {profit:.2f}€")

            final_routes.append({
                "truck": truck_type,
                "stops": [f.id for f in route_stops],
                "total_pigs": pigs_in_route,
                "total_weight": route_weight,
                "distance_km": round(dist_km, 2),
                "cost": round(trip_cost, 2),
                "profit": round(profit, 2)
            })
            
            total_pigs_processed += pigs_in_route
            total_profit_global += profit

        logger.info(f"\n--- RESUMEN FINAL ---")
        logger.info(f"🐖 Total Cerdos: {total_pigs_processed}")
        logger.info(f"🚚 Rutas Optimizadas: {len(final_routes)}")
        logger.info(f"💸 Beneficio Neto Global: {total_profit_global:.2f}€")
        print("="*60 + "\n")

        return {
            "summary": {
                "total_pigs": total_pigs_processed,
                "total_routes": len(final_routes),
                "total_net_profit": round(total_profit_global, 2)
            },
            "routes": final_routes
        }

# --- EJECUCIÓN ---
if __name__ == "__main__":
    # Mock Data: Escenario complejo para probar el Multi-Stop
    farms = [
        {"id": "F1", "lat": 41.95, "lng": 2.26, "pigs": 50, "avg_weight": 110},   # Pequeña 5.5T
        {"id": "F2", "lat": 41.96, "lng": 2.27, "pigs": 60, "avg_weight": 108},   # Pequeña 6.4T
        {"id": "F3", "lat": 41.94, "lng": 2.25, "pigs": 40, "avg_weight": 112},   # Pequeña 4.4T 
        # F1+F2+F3 suman ~16.3T -> Deberían ir juntas en un camión de 20T
        
        {"id": "F4", "lat": 42.10, "lng": 2.40, "pigs": 180, "avg_weight": 110},  # Grande 19.8T (Sola)
        {"id": "F5", "lat": 42.15, "lng": 2.45, "pigs": 10, "avg_weight": 90},    # Rechazada (Peso bajo)
    ]

    solver = PigSolverVRP()
    result = solver.solve_day(farms)
    # print(json.dumps(result, indent=2)) # Descomenta si quieres ver el JSON puro al final
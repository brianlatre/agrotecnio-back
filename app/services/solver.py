import math
import json
import random
import numpy as np
import urllib.request
import time
from datetime import datetime, timedelta

# --- CONFIGURATION AND CONSTANTS ---

SIMULATION_DAYS = 14
WORK_DAYS = [0, 1, 2, 3, 4]  # 0=Monday, ..., 6=Sunday
MAX_STOPS = 3 # Maximum stops per trip

# Time Constraints
MAX_DAILY_HOURS = 8.0
AVG_SPEED_KMH = 50.0 
SERVICE_TIME_PER_STOP = 0.5 
UNLOADING_TIME_SLAUGHTERHOUSE = 0.5 

# API CONFIGURATION
USE_REAL_ROADS_API = True
OSRM_API_URL = "http://router.project-osrm.org/route/v1/driving/"
CACHE_DISTANCES = {} 

CIRCUITY_FACTOR_FALLBACK = 1.3 

# Prices and Costs (EUR)
PRICE_PER_KG = 1.56
FIXED_COST_TRUCK = 2000.0  
COST_PER_KM_SMALL = 1.15
COST_PER_KM_LARGE = 1.25

# Weights (kg)
IDEAL_MIN = 105
IDEAL_MAX = 115
PENALTY_RANGE_1_MIN = 100
PENALTY_RANGE_1_MAX = 120
PENALTY_FACTOR_MILD = 0.15  
PENALTY_FACTOR_HARSH = 0.20 

# Growth parameters
DAILY_GROWTH_MEAN = 0.8  
DAILY_GROWTH_STD = 0.1

# Base Location (Slaughterhouse - Vic Area)
SLAUGHTERHOUSE_LOC = {"lat": 41.9308, "lon": 2.2545} 
SLAUGHTERHOUSE_CAPACITY = 2000 

# --- CLASSES ---

class Truck:
    def __init__(self, t_id, capacity_tons, truck_type):
        self.id = t_id
        self.capacity_kg = capacity_tons * 1000
        self.truck_type = truck_type 
        self.cost_per_km = COST_PER_KM_SMALL if truck_type == 'small' else COST_PER_KM_LARGE
        self.current_load_kg = 0
        self.pigs_loaded = 0
        self.route = [] 
        self.daily_hours_used = 0.0
        print(f"[INIT] Truck {self.id} created. Type: {self.truck_type}, Cap: {self.capacity_kg}kg")
    
    def reset_daily_stats(self):
        self.current_load_kg = 0
        self.pigs_loaded = 0
        self.route = []
        self.daily_hours_used = 0.0

    def reset_route(self):
        self.current_load_kg = 0
        self.pigs_loaded = 0
        self.route = []

class Farm:
    def __init__(self, f_id, lat, lon, initial_pigs, avg_weight):
        self.id = f_id
        self.lat = lat
        self.lon = lon
        self.inventory = initial_pigs
        self.avg_weight = avg_weight
        self.last_visit_day = -999
        self.weight_std = 5.0 
        self.urgency_score = 0

    def grow_pigs(self):
        gain = random.normalvariate(DAILY_GROWTH_MEAN, DAILY_GROWTH_STD)
        old_weight = self.avg_weight
        self.avg_weight += gain
        # Log reducido para no saturar, descomentar si necesario
        # print(f"[GROWTH] {self.id}: {old_weight:.1f}kg -> {self.avg_weight:.1f}kg")

class Simulation:
    def __init__(self):
        print("[SYSTEM] Initializing Simulation...")
        self.farms = []
        self.trucks = []
        self.results = {
            "summary": {},
            "daily_logs": []
        }
        self.total_profit = 0
        self.total_penalties = 0
        self.total_transport_cost = 0
        
        self.init_scenario()

    def init_scenario(self):
        json_file = 'scenario_data.json'
        try:
            print(f"[SYSTEM] Loading scenario from '{json_file}'...")
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            for t in data['trucks']:
                self.trucks.append(Truck(t['id'], t['capacity_tons'], t['type']))
            
            for f in data['farms']:
                self.farms.append(Farm(f['id'], f['lat'], f['lon'], f['inventory'], f['avg_weight']))
                
            print(f"[SYSTEM] Successfully loaded {len(self.trucks)} trucks and {len(self.farms)} farms.")
            
        except FileNotFoundError:
            print(f"[ERROR] Could not find '{json_file}'. Please run 'generate_data.py' first.")
            exit(1)

    # --- HELPER FUNCTIONS ---

    def get_haversine_estimate(self, lat1, lon1, lat2, lon2):
        R = 6371  
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c * CIRCUITY_FACTOR_FALLBACK

    def get_real_road_distance(self, lat1, lon1, lat2, lon2):
        if not USE_REAL_ROADS_API:
            return self.get_haversine_estimate(lat1, lon1, lat2, lon2)

        cache_key = (round(lat1,4), round(lon1,4), round(lat2,4), round(lon2,4))
        if cache_key in CACHE_DISTANCES:
            return CACHE_DISTANCES[cache_key]

        url = f"{OSRM_API_URL}{lon1},{lat1};{lon2},{lat2}?overview=false"
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if "routes" in data and len(data["routes"]) > 0:
                        dist_km = data["routes"][0]["distance"] / 1000.0
                        CACHE_DISTANCES[cache_key] = dist_km
                        return dist_km
        except Exception:
            pass

        fallback_dist = self.get_haversine_estimate(lat1, lon1, lat2, lon2)
        CACHE_DISTANCES[cache_key] = fallback_dist
        return fallback_dist

    def calculate_revenue_batch(self, num_pigs, avg_weight, std_weight):
        weights = np.random.normal(avg_weight, std_weight, num_pigs)
        total_revenue = 0
        total_penalty_amount = 0
        
        for w in weights:
            penalty = 0
            if 105 <= w <= 115:
                penalty = 0
            elif (100 <= w < 105) or (115 < w <= 120):
                penalty = PENALTY_FACTOR_MILD
            else:
                penalty = PENALTY_FACTOR_HARSH
            
            value = w * PRICE_PER_KG * (1 - penalty)
            total_revenue += value
            total_penalty_amount += (w * PRICE_PER_KG * penalty)

        return total_revenue, total_penalty_amount

    def estimate_trip_time(self, total_dist_km, num_stops):
        drive_time = total_dist_km / AVG_SPEED_KMH
        service_time = (num_stops * SERVICE_TIME_PER_STOP) + UNLOADING_TIME_SLAUGHTERHOUSE
        return drive_time + service_time

    # --- PLANNER LOGIC (DSS) ---

    def plan_day(self, day_index):
        weekday = day_index % 7
        day_num = day_index + 1
        
        print(f"\n=== INICIANDO DÍA {day_num} (Día semana: {weekday}) ===")

        for f in self.farms:
            f.grow_pigs()

        if weekday not in WORK_DAYS:
            print(f"[SISTEMA] Día {day_num} es fin de semana. Sin operaciones.")
            return None

        daily_log = {"day": day_num, "trucks_ops": [], "total_processed": 0, "daily_profit": 0}

        # 1. Identify Candidates
        candidates = []
        skipped_count = 0
        for f in self.farms:
            days_since = day_index - f.last_visit_day
            if days_since >= 7 and f.inventory > 0:
                candidates.append(f)
            else:
                skipped_count += 1
        
        print(f"[FILTRO] Candidatos: {len(candidates)} | Omitidos (Regla 7 días o vacíos): {skipped_count}")

        # Scoring
        PANIC_THRESHOLD_WEIGHT = 118.0 
        print(f"[ANÁLISIS] Calculando 'Urgency Score' para {len(candidates)} granjas...")
        for f in candidates:
            dist_to_hub = self.get_real_road_distance(SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'], f.lat, f.lon)
            if f.avg_weight >= PANIC_THRESHOLD_WEIGHT:
                f.urgency_score = 1000 + f.avg_weight # Pánico
                mode = "PÁNICO"
            else:
                est_revenue = f.avg_weight * PRICE_PER_KG
                est_transport_cost = dist_to_hub * 2 * 1.20 
                f.urgency_score = est_revenue - est_transport_cost
                mode = "ECONÓMICO"

        candidates.sort(key=lambda x: x.urgency_score, reverse=True)
        
        # Mostrar Top 5 Decisiones
        print("  [DECISIÓN] Top 5 Prioridades del Día:")
        for i, c in enumerate(candidates[:5]):
             print(f"    {i+1}. {c.id} | Peso: {c.avg_weight:.1f}kg | Score: {c.urgency_score:.1f} | Dist Hub: ~?")

        slaughtered_today = 0
        
        # Multi-trip Logic
        active_trucks = []
        for t in self.trucks:
            t.reset_daily_stats()
            active_trucks.append(t)

        while candidates and slaughtered_today < SLAUGHTERHOUSE_CAPACITY and active_trucks:
            
            truck = active_trucks.pop(0)
            truck.reset_route() 

            if truck.daily_hours_used >= MAX_DAILY_HOURS:
                # print(f"[TIEMPO] Camión {truck.id} finalizó jornada.")
                continue 

            print(f"\n[RUTA] Planificando Viaje para Camión {truck.id} (Horas usadas: {truck.daily_hours_used:.1f}h)")
            
            # 1. Seleccionar primera parada
            current_farm = candidates.pop(0)
            truck.route.append(current_farm)
            
            pigs_cap = int(truck.capacity_kg / current_farm.avg_weight)
            pigs_take = min(pigs_cap, current_farm.inventory)
            rem_slaughter = SLAUGHTERHOUSE_CAPACITY - slaughtered_today
            pigs_take = min(pigs_take, rem_slaughter)
            
            truck.pigs_loaded = pigs_take
            truck.current_load_kg = pigs_take * current_farm.avg_weight
            
            print(f"  -> Parada 1: {current_farm.id} (Prioridad Alta). Carga: {pigs_take} cerdos.")

            # 2. Búsqueda Multi-stop (Smart Neighbor)
            while len(truck.route) < MAX_STOPS and truck.current_load_kg < truck.capacity_kg * 0.90:
                print(f"  [DECISIÓN] Buscando vecino inteligente para completar carga ({int(truck.capacity_kg - truck.current_load_kg)}kg libres)...")
                best_next = None
                best_score = -float('inf')
                
                comparison_log = [] # Para loguear las opciones consideradas
                
                for cand in candidates:
                    if cand.inventory > 0:
                        dist_km = self.get_haversine_estimate(current_farm.lat, current_farm.lon, cand.lat, cand.lon)
                        
                        # Solo considerar vecinos en radio razonable
                        if dist_km > 100: continue
                        
                        # Scoring Heurístico
                        cost_score = -(dist_km * 1.2)
                        qual_score = 100 - abs(cand.avg_weight - 110)
                        if cand.avg_weight < 100: qual_score -= 200
                        if cand.avg_weight > 118: qual_score += 500
                        
                        comb = qual_score + cost_score
                        
                        # Guardamos log de los mejores candidatos para mostrar decisión
                        if comb > -100: # Filtro para no ensuciar log con opciones muy malas
                            comparison_log.append(f"    > {cand.id}: Dist {dist_km:.0f}km (Cost {cost_score:.0f}) + Calidad {cand.avg_weight:.1f}kg (Pts {qual_score}) = Score {comb:.0f}")

                        if comb > best_score:
                            best_score = comb
                            best_next = cand
                
                # Imprimir comparativa (limitada a 3 para no saturar)
                if comparison_log:
                    print("\n".join(comparison_log[:3]))
                    if len(comparison_log) > 3: print(f"    ... y {len(comparison_log)-3} más.")

                if best_next:
                    print(f"  => GANADOR: {best_next.id} (Score: {best_score:.0f})")
                    candidates.remove(best_next)
                    current_farm = best_next
                    truck.route.append(current_farm)
                    
                    rem_kg = truck.capacity_kg - truck.current_load_kg
                    p_cap = int(rem_kg / current_farm.avg_weight)
                    p_take = min(p_cap, current_farm.inventory)
                    p_take = min(p_take, SLAUGHTERHOUSE_CAPACITY - slaughtered_today - truck.pigs_loaded)
                    
                    if p_take > 0:
                        truck.pigs_loaded += p_take
                        truck.current_load_kg += p_take * current_farm.avg_weight
                        print(f"     Agregados {p_take} cerdos. Camiòn al {int(truck.current_load_kg/truck.capacity_kg*100)}%")
                    else:
                        print("     Vecino encontrado pero cupo escorxador lleno.")
                        break
                else:
                    print("  => NINGÚN vecino viable encontrado (muy lejos o mala calidad).")
                    break
            
            # -- VALIDATE TIME --
            trip_dist_km = 0
            c_lat, c_lon = SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon']
            for f in truck.route:
                trip_dist_km += self.get_real_road_distance(c_lat, c_lon, f.lat, f.lon)
                c_lat, c_lon = f.lat, f.lon
            trip_dist_km += self.get_real_road_distance(c_lat, c_lon, SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'])
            
            est_time = self.estimate_trip_time(trip_dist_km, len(truck.route))
            
            print(f"  [VALIDACIÓN TIEMPO] Acumulado: {truck.daily_hours_used:.2f}h + Nuevo Viaje: {est_time:.2f}h = {truck.daily_hours_used + est_time:.2f}h")
            
            if truck.daily_hours_used + est_time <= MAX_DAILY_HOURS:
                # COMMIT
                print(f"  ✅ VIAJE APROBADO. Total cerdos: {truck.pigs_loaded}. Distancia: {trip_dist_km:.1f}km")
                truck.daily_hours_used += est_time
                slaughtered_today += truck.pigs_loaded
                
                # Apply deductions
                remaining_cap_kg = truck.capacity_kg
                actual_pigs_loaded_verify = 0
                for farm_in_route in truck.route:
                    p_cap = int(remaining_cap_kg / farm_in_route.avg_weight)
                    p_take = min(p_cap, farm_in_route.inventory)
                    amount_for_this_farm = min(p_take, truck.pigs_loaded - actual_pigs_loaded_verify)
                    
                    farm_in_route.inventory -= amount_for_this_farm
                    farm_in_route.last_visit_day = day_index
                    actual_pigs_loaded_verify += amount_for_this_farm
                    remaining_cap_kg -= (amount_for_this_farm * farm_in_route.avg_weight)
                
                self.process_truck_trip(truck, daily_log, trip_dist_km, est_time)
                active_trucks.append(truck) # Vuelve a la cola
                
            else:
                # REJECT
                print(f"  ⛔ VIAJE RECHAZADO. Excede jornada laboral de {MAX_DAILY_HOURS}h.")
                # Devolver granjas a candidatos
                for f in reversed(truck.route):
                    candidates.insert(0, f) 
                pass 

        return daily_log

    def process_truck_trip(self, truck, daily_log, precalc_dist_km, trip_duration):
        total_dist = precalc_dist_km
        route_names = [f.id for f in truck.route]
        
        trip_cost = total_dist * truck.cost_per_km
        avg_w_route = sum([f.avg_weight for f in truck.route]) / len(truck.route)
        rev, pen = self.calculate_revenue_batch(truck.pigs_loaded, avg_w_route, 5.0)
        profit = rev - trip_cost
        
        fill_pct = (truck.current_load_kg / truck.capacity_kg) * 100
        # print(f"  -> FINANCIALS: Net: {profit:.0f} EUR")
        
        self.total_profit += profit
        self.total_penalties += pen
        self.total_transport_cost += trip_cost
        
        op_data = {
            "truck_id": truck.id,
            "route": route_names,
            "trip_duration_hours": round(trip_duration, 2),
            "distance_km": round(total_dist, 2),
            "pigs_delivered": truck.pigs_loaded,
            "load_pct": round(fill_pct, 1),
            "trip_cost": round(trip_cost, 2),
            "revenue": round(rev, 2),
            "penalty": round(pen, 2),
            "profit": round(profit, 2)
        }
        daily_log["trucks_ops"].append(op_data)
        daily_log["total_processed"] += truck.pigs_loaded
        daily_log["daily_profit"] += profit

    def run(self):
        print("\n[SISTEMA] INICIANDO SIMULACIÓN DE LOGÍSTICA PORCINA\n")
        
        for d in range(SIMULATION_DAYS):
            log = self.plan_day(d)
            if log:
                self.results["daily_logs"].append(log)
        
        total_fixed_cost = 2 * len(self.trucks) * FIXED_COST_TRUCK 
        self.total_profit -= total_fixed_cost
        self.total_transport_cost += total_fixed_cost
        
        self.results["summary"] = {
            "total_profit_net": round(self.total_profit, 2),
            "total_transport_cost": round(self.total_transport_cost, 2),
            "total_penalties": round(self.total_penalties, 2),
            "final_farm_status": [{"id": f.id, "remaining": f.inventory, "weight": round(f.avg_weight, 1)} for f in self.farms]
        }
        
        return self.results

# --- EXECUTION ---

if __name__ == "__main__":
    sim = Simulation()
    results = sim.run()
    
    with open('simulation_results.json', 'w') as f:
        json.dump(results, f, indent=4)
        
    print("\n=== INFORME FINAL ===")
    print(f"Beneficio Neto: {results['summary']['total_profit_net']} EUR")
    print(f"Coste Transporte: {results['summary']['total_transport_cost']} EUR")
    print("Archivo 'simulation_results.json' generado.")
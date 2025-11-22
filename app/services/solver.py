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

# API CONFIGURATION for Real Road Distances
USE_REAL_ROADS_API = True
OSRM_API_URL = "http://router.project-osrm.org/route/v1/driving/"
CACHE_DISTANCES = {} # Cache to avoid API rate limits

# Fallback factor if API fails
CIRCUITY_FACTOR_FALLBACK = 1.3 

# Prices and Costs (EUR)
PRICE_PER_KG = 1.56
FIXED_COST_TRUCK = 2000.0  # Per week
COST_PER_KM_SMALL = 1.15
COST_PER_KM_LARGE = 1.25

# Weights (kg)
IDEAL_MIN = 105
IDEAL_MAX = 115
PENALTY_RANGE_1_MIN = 100
PENALTY_RANGE_1_MAX = 120

# Penalties
PENALTY_FACTOR_MILD = 0.15  # 15%
PENALTY_FACTOR_HARSH = 0.20 # 20%

# Growth parameters
DAILY_GROWTH_MEAN = 0.8  # kg/day gained
DAILY_GROWTH_STD = 0.1

# Base Location (Slaughterhouse - Vic Area)
SLAUGHTERHOUSE_LOC = {"lat": 41.9308, "lon": 2.2545} 
SLAUGHTERHOUSE_CAPACITY = 2000 # Pigs per day capacity

# --- CLASSES ---

class Truck:
    def __init__(self, t_id, capacity_tons, truck_type):
        self.id = t_id
        self.capacity_kg = capacity_tons * 1000
        self.truck_type = truck_type # 'small' or 'large'
        self.cost_per_km = COST_PER_KM_SMALL if truck_type == 'small' else COST_PER_KM_LARGE
        self.current_load_kg = 0
        self.pigs_loaded = 0
        self.route = [] # List of Farm objects
        print(f"[INIT] Truck {self.id} created. Type: {self.truck_type}, Cap: {self.capacity_kg}kg")
    
    def reset(self):
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
        # Pigs gain weight daily
        gain = random.normalvariate(DAILY_GROWTH_MEAN, DAILY_GROWTH_STD)
        old_weight = self.avg_weight
        self.avg_weight += gain
        # [LOG REQUEST] Growth log activated
        print(f"[GROWTH] {self.id}: Pigs grew from {old_weight:.2f}kg to {self.avg_weight:.2f}kg (+{gain:.2f}kg)")

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
        # 1. Create Fleet
        print("[SYSTEM] Creating Fleet (Standard Capacity)...")
        self.trucks.append(Truck(1, 10, 'small')) 
        self.trucks.append(Truck(2, 10, 'small'))
        self.trucks.append(Truck(3, 20, 'large'))

        # 2. Create Farms
        print("[SYSTEM] Generating 50 Mixed Farms (Small, Medium, Large)...")
        base_coords = [
            (41.93, 2.25), (41.80, 2.10), (42.00, 2.30), (41.65, 2.00), # Vic/Osona
            (41.61, 0.62), (41.70, 0.80), (41.55, 0.50), (41.80, 0.90)  # Lleida
        ]
        
        for i in range(50):
            base = base_coords[i % len(base_coords)]
            lat = base[0] + random.uniform(-0.15, 0.15)
            lon = base[1] + random.uniform(-0.15, 0.15)
            
            rand_type = random.random()
            if rand_type < 0.60:
                inv = random.randint(20, 60) # Small
            elif rand_type < 0.90:
                inv = random.randint(100, 200) # Medium
            else:
                inv = random.randint(300, 600) # Large

            w = random.uniform(85, 105)
            self.farms.append(Farm(f"Farm_{i+1}", lat, lon, inv, w))

    # --- HELPER FUNCTIONS ---

    def get_haversine_estimate(self, lat1, lon1, lat2, lon2):
        """
        Mathematical estimation (fast). Used for fallback and massive loops.
        """
        R = 6371  # Earth radius km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c * CIRCUITY_FACTOR_FALLBACK

    def get_real_road_distance(self, lat1, lon1, lat2, lon2):
        """
        [CRITICAL FIX A] Real Road Distance using OSRM API.
        Includes caching to prevent rate limits and slow execution.
        """
        if not USE_REAL_ROADS_API:
            return self.get_haversine_estimate(lat1, lon1, lat2, lon2)

        # Check Cache (Undirected assumption for speed: A->B approx B->A)
        # We key by tuple coordinates
        cache_key = (round(lat1,4), round(lon1,4), round(lat2,4), round(lon2,4))
        if cache_key in CACHE_DISTANCES:
            return CACHE_DISTANCES[cache_key]

        # Prepare Request
        # OSRM format: {lon},{lat};{lon},{lat}
        url = f"{OSRM_API_URL}{lon1},{lat1};{lon2},{lat2}?overview=false"
        
        try:
            # We use a small timeout to fail fast and fallback to math if API is slow
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    # OSRM returns distance in meters
                    if "routes" in data and len(data["routes"]) > 0:
                        dist_km = data["routes"][0]["distance"] / 1000.0
                        CACHE_DISTANCES[cache_key] = dist_km
                        # Be polite to the public API
                        # time.sleep(0.05) 
                        return dist_km
        except Exception as e:
            # print(f"[API WARN] OSRM lookup failed ({e}). Using Fallback.")
            pass

        # Fallback if API fails
        fallback_dist = self.get_haversine_estimate(lat1, lon1, lat2, lon2)
        CACHE_DISTANCES[cache_key] = fallback_dist # Cache the fallback to stop trying failed URLs
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

    # --- PLANNER LOGIC (DSS) ---

    def plan_day(self, day_index):
        weekday = day_index % 7
        day_num = day_index + 1
        
        print(f"\n=== STARTING DAY {day_num} (Weekday: {weekday}) ===")

        for f in self.farms:
            f.grow_pigs()

        if weekday not in WORK_DAYS:
            print(f"[SYSTEM] Day {day_num} is a weekend. No operations.")
            return None

        daily_log = {
            "day": day_num,
            "trucks_ops": [],
            "total_processed": 0,
            "daily_profit": 0
        }

        # 1. Identify Candidates
        candidates = []
        for f in self.farms:
            days_since = day_index - f.last_visit_day
            if days_since >= 7 and f.inventory > 0:
                candidates.append(f)
        
        print(f"[LOGIC] Found {len(candidates)} candidate farms.")

        # [CRITICAL FIX B] Advanced Scoring System
        PANIC_THRESHOLD_WEIGHT = 118.0 
        
        print("[LOGIC] Scoring candidates (Using API for key metrics)...")
        for f in candidates:
            # We use the API for the score calculation because it's critical for the Profit estimate
            dist_to_hub = self.get_real_road_distance(SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'], f.lat, f.lon)
            
            if f.avg_weight >= PANIC_THRESHOLD_WEIGHT:
                # Panic Mode
                f.urgency_score = 1000 + f.avg_weight
            else:
                # Economic Mode
                est_revenue = f.avg_weight * PRICE_PER_KG
                est_transport_cost = dist_to_hub * 2 * 1.20 
                f.urgency_score = est_revenue - est_transport_cost

        candidates.sort(key=lambda x: x.urgency_score, reverse=True)

        slaughtered_today = 0
        for t in self.trucks:
            t.reset()

        # 3. Route Assignment
        for truck in self.trucks:
            if slaughtered_today >= SLAUGHTERHOUSE_CAPACITY:
                break
            if not candidates:
                break

            print(f"[ROUTE] Planning Truck {truck.id}...")
            
            current_farm = candidates.pop(0)
            truck.route.append(current_farm)
            
            pigs_capacity = int(truck.capacity_kg / current_farm.avg_weight)
            pigs_to_take = min(pigs_capacity, current_farm.inventory)
            remaining_slaughter_cap = SLAUGHTERHOUSE_CAPACITY - slaughtered_today
            pigs_to_take = min(pigs_to_take, remaining_slaughter_cap)

            truck.pigs_loaded += pigs_to_take
            truck.current_load_kg += pigs_to_take * current_farm.avg_weight
            
            current_farm.inventory -= pigs_to_take
            current_farm.last_visit_day = day_index
            slaughtered_today += pigs_to_take
            
            # Calculate Fill % for logging
            fill_pct = (truck.current_load_kg / truck.capacity_kg) * 100
            print(f"  -> Stop 1: {current_farm.id} (Score: {current_farm.urgency_score:.1f}). Load: {pigs_to_take}. Truck Fill: {fill_pct:.1f}%")

            # Multi-stop Search
            while len(truck.route) < MAX_STOPS and truck.current_load_kg < truck.capacity_kg * 0.90:
                best_next_farm = None
                min_dist = float('inf')
                
                # PERFORMANCE NOTE: 
                # For the inner loop (scanning 40+ candidates), we use the Haversine Estimate.
                # Calling the API 50 times here would freeze the script.
                for cand in candidates:
                    if cand.inventory > 0:
                        # Use FAST estimation here
                        d = self.get_haversine_estimate(current_farm.lat, current_farm.lon, cand.lat, cand.lon)
                        if d < min_dist:
                            min_dist = d
                            best_next_farm = cand
                
                if best_next_farm and min_dist < 100: 
                    # [LOG REQUEST] Reason for next stop selection
                    print(f"  -> Found neighbor: {best_next_farm.id} (~{min_dist:.1f}km away). Reason: Closest available farm (Nearest Neighbor heuristic) to minimize empty driving.")
                    
                    candidates.remove(best_next_farm)
                    current_farm = best_next_farm
                    truck.route.append(current_farm)
                    
                    remaining_weight = truck.capacity_kg - truck.current_load_kg
                    pigs_cap = int(remaining_weight / current_farm.avg_weight)
                    pigs_take = min(pigs_cap, current_farm.inventory)
                    pigs_take = min(pigs_take, SLAUGHTERHOUSE_CAPACITY - slaughtered_today)
                    
                    if pigs_take > 0:
                        truck.pigs_loaded += pigs_take
                        truck.current_load_kg += pigs_take * current_farm.avg_weight
                        current_farm.inventory -= pigs_take
                        current_farm.last_visit_day = day_index
                        slaughtered_today += pigs_take
                        
                        # Calculate Fill % for logging
                        fill_pct = (truck.current_load_kg / truck.capacity_kg) * 100
                        print(f"  -> Stop {len(truck.route)}: {current_farm.id}. Added {pigs_take} pigs. Truck Fill: {fill_pct:.1f}%")
                    else:
                        break
                else:
                    break 

            if truck.pigs_loaded > 0:
                self.process_truck_trip(truck, daily_log)

        return daily_log

    def process_truck_trip(self, truck, daily_log):
        total_dist = 0
        current_lat, current_lon = SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon']
        route_names = []
        
        # Use API for FINAL COST CALCULATION (This is where precision equals money)
        for farm in truck.route:
            dist = self.get_real_road_distance(current_lat, current_lon, farm.lat, farm.lon)
            total_dist += dist
            current_lat, current_lon = farm.lat, farm.lon
            route_names.append(farm.id)

        return_dist = self.get_real_road_distance(current_lat, current_lon, SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'])
        total_dist += return_dist
        
        trip_cost = total_dist * truck.cost_per_km
        avg_w_route = sum([f.avg_weight for f in truck.route]) / len(truck.route)
        rev, pen = self.calculate_revenue_batch(truck.pigs_loaded, avg_w_route, 5.0)
        profit = rev - trip_cost
        
        print(f"  -> TRIP FINANCIALS: Route: {route_names} | Road Dist: {total_dist:.1f}km | Net: {profit:.0f} EUR")
        
        self.total_profit += profit
        self.total_penalties += pen
        self.total_transport_cost += trip_cost
        
        op_data = {
            "truck_id": truck.id,
            "route": route_names,
            "distance_km": round(total_dist, 2),
            "pigs_delivered": truck.pigs_loaded,
            "load_pct": round((truck.current_load_kg / truck.capacity_kg) * 100, 1),
            "trip_cost": round(trip_cost, 2),
            "revenue": round(rev, 2),
            "penalty": round(pen, 2),
            "profit": round(profit, 2)
        }
        daily_log["trucks_ops"].append(op_data)
        daily_log["total_processed"] += truck.pigs_loaded
        daily_log["daily_profit"] += profit

    def run(self):
        print("\n[SYSTEM] STARTING MAIN SIMULATION LOOP (With Real Roads API)\n")
        
        for d in range(SIMULATION_DAYS):
            log = self.plan_day(d)
            if log:
                self.results["daily_logs"].append(log)
        
        print("\n[SYSTEM] Applying Weekly Fixed Costs...")
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
        
    print("\n=== FINAL SIMULATION REPORT ===")
    print(f"Total Net Profit: {results['summary']['total_profit_net']} EUR")
    print(f"Total Transport Cost: {results['summary']['total_transport_cost']} EUR")
    print(f"Total Penalties: {results['summary']['total_penalties']} EUR")
    print("File 'simulation_results.json' generated successfully.")
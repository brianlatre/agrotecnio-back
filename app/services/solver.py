import math
import json
import random
import numpy as np
import urllib.request
import time
import os
from datetime import datetime, timedelta

# --- CONFIGURATION AND CONSTANTS ---

SIMULATION_DAYS = 14
WORK_DAYS = [0, 1, 2, 3, 4]
MAX_STOPS = 3

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
FIXED_COST_TRUCK_WEEKLY = 2000.0  

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

# Critical Thresholds
PANIC_THRESHOLD_WEIGHT = 112.5 
OPTIMAL_MIN_WEIGHT = 108.0 

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
        return old_weight, self.avg_weight, gain

class Simulation:
    def __init__(self, auto_load=True):
        if auto_load: print("[SYSTEM] Initializing Simulation Engine...")
        self.farms = []
        self.trucks = []
        self.results = {
            "summary": {},
            "daily_logs": [],
            "metadata": {} 
        }
        self.total_profit = 0
        self.total_penalties = 0
        self.total_transport_cost = 0
        
        if auto_load:
            self.init_from_files()

    def init_from_files(self):
        self.load_scenario_data()
        
        # Load Fleet Configuration
        if not os.path.exists('fleet_config.json'):
            print("[ERROR] 'fleet_config.json' not found. Run optimize.py first.")
            # Fallback default if optimizer wasn't run
            print("[SYSTEM] Using default fallback fleet: 1 Small, 1 Large")
            self.setup_manual_fleet(1, 1)
        else:
            with open('fleet_config.json', 'r') as f:
                fleet_cfg = json.load(f)
                print(f"[SYSTEM] Loading optimized fleet configuration: {fleet_cfg}")
                self.setup_manual_fleet(fleet_cfg['small'], fleet_cfg['large'])

    def load_scenario_data(self):
        if not os.path.exists('scenario_data.json'):
            print("[ERROR] 'scenario_data.json' not found. Run generate_data.py.")
            exit(1)
        self.farms = []
        with open('scenario_data.json', 'r') as f:
            scenario = json.load(f)
            for fdata in scenario['farms']:
                self.farms.append(Farm(fdata['id'], fdata['lat'], fdata['lon'], fdata['inventory'], fdata['avg_weight']))
        
        # [FIX CRÍTICO] Generar metadades immediatament després de carregar
        self.results["metadata"] = {
            "slaughterhouse": SLAUGHTERHOUSE_LOC,
            "farms": {f.id: {"lat": f.lat, "lon": f.lon} for f in self.farms}
        }

    def setup_manual_fleet(self, num_small, num_large):
        """Used by Optimizer to set fleet on the fly"""
        self.trucks = []
        tid = 1
        for _ in range(num_small):
            self.trucks.append(Truck(tid, 10, 'small'))
            tid += 1
        for _ in range(num_large):
            self.trucks.append(Truck(tid, 20, 'large'))
            tid += 1

    def reset_simulation(self):
        """Resets counters for optimization loops"""
        self.total_profit = 0
        self.total_penalties = 0
        self.total_transport_cost = 0
        self.results["daily_logs"] = []
        # Reload farms to reset inventory/weights
        self.load_scenario_data()

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

    def get_distance(self, lat1, lon1, lat2, lon2, use_api=True):
        if not use_api or not USE_REAL_ROADS_API:
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

        fallback = self.get_haversine_estimate(lat1, lon1, lat2, lon2)
        CACHE_DISTANCES[cache_key] = fallback
        return fallback

    def calculate_revenue_batch(self, num_pigs, avg_weight, std_weight, silent=False):
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

        if total_penalty_amount > 0 and not silent:
            print(f"   >>> [PENALTY] {num_pigs} pigs (Avg: {avg_weight:.1f}kg) -> Lost: -{total_penalty_amount:.2f}€")

        return total_revenue, total_penalty_amount

    def estimate_trip_time(self, total_dist_km, num_stops):
        drive_time = total_dist_km / AVG_SPEED_KMH
        service_time = (num_stops * SERVICE_TIME_PER_STOP) + UNLOADING_TIME_SLAUGHTERHOUSE
        return drive_time + service_time

    def plan_day(self, day_index, silent=False, use_api=True):
        weekday = day_index % 7
        day_num = day_index + 1
        
        if not silent: print(f"\n=== STARTING DAY {day_num} (Weekday: {weekday}) ===")

        daily_growth_stats = []
        for f in self.farms:
            old, new, gain = f.grow_pigs()
            if f.inventory > 0: 
                daily_growth_stats.append({"id": f.id, "new": new})

        if not silent:
            daily_growth_stats.sort(key=lambda x: x["new"], reverse=True)
            print("[INFO] Top Heavy Farms:")
            for s in daily_growth_stats[:3]:
                print(f"   - {s['id']}: {s['new']:.1f}kg")

        if weekday not in WORK_DAYS:
            return None

        daily_log = {"day": day_num, "trucks_ops": [], "total_processed": 0, "daily_profit": 0}

        candidates = []
        for f in self.farms:
            days_since = day_index - f.last_visit_day
            if days_since >= 7 and f.inventory > 0:
                candidates.append(f)
        
        # Scoring
        for f in candidates:
            # Always use estimation for scoring to be fast
            dist_est = self.get_haversine_estimate(SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'], f.lat, f.lon)
            
            projected_weight = f.avg_weight
            if weekday == 4:
                projected_weight += (DAILY_GROWTH_MEAN * 2)

            if projected_weight >= PANIC_THRESHOLD_WEIGHT:
                f.urgency_score = 2000 + projected_weight
            elif f.avg_weight < OPTIMAL_MIN_WEIGHT:
                f.urgency_score = -2000 + f.avg_weight 
            else:
                sweet_spot_bonus = 0
                if 110 <= f.avg_weight <= 112:
                    sweet_spot_bonus = 500

                est_revenue = f.avg_weight * PRICE_PER_KG
                est_transport_cost = dist_est * 2 * 1.20 
                f.urgency_score = est_revenue - est_transport_cost + sweet_spot_bonus

        candidates.sort(key=lambda x: x.urgency_score, reverse=True)
        
        slaughtered_today = 0
        active_trucks = list(self.trucks) # Copy list to cycle through
        for t in active_trucks: t.reset_daily_stats()

        while candidates and slaughtered_today < SLAUGHTERHOUSE_CAPACITY and active_trucks:
            
            if candidates[0].urgency_score < 0:
                if not silent: print(f"[STRATEGY] Stopping operations. Farms not ready.")
                break

            truck = active_trucks.pop(0)
            truck.reset_route() 

            if truck.daily_hours_used >= MAX_DAILY_HOURS:
                continue 

            if not silent: print(f"\n[ROUTE] Truck {truck.id} (Hrs used: {truck.daily_hours_used:.2f}h)")
            
            current_farm = candidates.pop(0)
            truck.route.append(current_farm)
            
            pigs_cap = int(truck.capacity_kg / current_farm.avg_weight)
            pigs_take = min(pigs_cap, current_farm.inventory)
            rem_slaughter = SLAUGHTERHOUSE_CAPACITY - slaughtered_today
            pigs_take = min(pigs_take, rem_slaughter)
            
            truck.pigs_loaded = pigs_take
            truck.current_load_kg = pigs_take * current_farm.avg_weight
            
            if not silent: print(f"  -> Start: {current_farm.id} ({current_farm.avg_weight:.1f}kg).")

            curr_lat, curr_lon = current_farm.lat, current_farm.lon
            dist_hub_direct = self.get_haversine_estimate(curr_lat, curr_lon, SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'])
            dist_accum_base = self.get_haversine_estimate(SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'], curr_lat, curr_lon)
            
            # Multi-stop
            while len(truck.route) < MAX_STOPS and truck.current_load_kg < truck.capacity_kg * 0.90:
                best_next = None
                best_score = -float('inf')
                
                for cand in candidates:
                    if cand.inventory > 0:
                        if cand.avg_weight < OPTIMAL_MIN_WEIGHT: continue

                        leg_dist = self.get_haversine_estimate(current_farm.lat, current_farm.lon, cand.lat, cand.lon)
                        return_dist_cand = self.get_haversine_estimate(cand.lat, cand.lon, SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'])
                        detour_km = (leg_dist + return_dist_cand) - dist_hub_direct
                        
                        if leg_dist > 50 and detour_km > 25: continue

                        new_total_dist = dist_accum_base + leg_dist + return_dist_cand
                        new_total_time = self.estimate_trip_time(new_total_dist, len(truck.route) + 1)
                        
                        if (truck.daily_hours_used + new_total_time) > (MAX_DAILY_HOURS + 0.5): continue

                        cost_score = -(detour_km * 2.0)
                        qual_score = 0
                        if cand.avg_weight >= PANIC_THRESHOLD_WEIGHT: qual_score = 1000
                        elif 110 <= cand.avg_weight <= 112.5: qual_score = 500
                        else: qual_score = 100 - abs(cand.avg_weight - 110)
                        
                        comb = qual_score + cost_score
                        
                        if comb > best_score:
                            best_score = comb
                            best_next = cand
                            best_leg_dist = leg_dist
                            best_return_dist = return_dist_cand
                            best_detour = detour_km

                if best_next:
                    if not silent: print(f"  => ADDED: {best_next.id}. Detour: +{best_detour:.1f}km")
                    candidates.remove(best_next)
                    current_farm = best_next
                    truck.route.append(current_farm)
                    dist_accum_base += best_leg_dist 
                    dist_hub_direct = best_return_dist 
                    
                    rem_kg = truck.capacity_kg - truck.current_load_kg
                    p_cap = int(rem_kg / current_farm.avg_weight)
                    p_take = min(p_cap, current_farm.inventory)
                    p_take = min(p_take, SLAUGHTERHOUSE_CAPACITY - slaughtered_today - truck.pigs_loaded)
                    
                    if p_take > 0:
                        truck.pigs_loaded += p_take
                        truck.current_load_kg += p_take * current_farm.avg_weight
                    else:
                        break
                else:
                    break
            
            # Validate Time Final & Backtracking
            route_accepted = False
            while len(truck.route) > 0:
                trip_dist_km = 0
                c_lat, c_lon = SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon']
                for f in truck.route:
                    trip_dist_km += self.get_distance(c_lat, c_lon, f.lat, f.lon, use_api)
                    c_lat, c_lon = f.lat, f.lon
                trip_dist_km += self.get_distance(c_lat, c_lon, SLAUGHTERHOUSE_LOC['lat'], SLAUGHTERHOUSE_LOC['lon'], use_api)
                
                est_time = self.estimate_trip_time(trip_dist_km, len(truck.route))
                total_time_check = truck.daily_hours_used + est_time
                
                if total_time_check <= MAX_DAILY_HOURS:
                    route_accepted = True
                    break 
                else:
                    removed_farm = truck.route.pop()
                    candidates.insert(0, removed_farm) 
                    if not silent: print(f"  ⚠️ Time exceeded ({total_time_check:.2f}h). Removing {removed_farm.id}")

            if route_accepted and len(truck.route) > 0:
                truck.daily_hours_used += est_time
                
                # Recalculate exact loads
                truck.pigs_loaded = 0
                truck.current_load_kg = 0
                remaining_cap_kg = truck.capacity_kg
                final_pigs_this_trip = 0
                
                for farm_in_route in truck.route:
                    p_cap = int(remaining_cap_kg / farm_in_route.avg_weight)
                    p_take = min(p_cap, farm_in_route.inventory)
                    rem_global = SLAUGHTERHOUSE_CAPACITY - slaughtered_today - final_pigs_this_trip
                    p_take = min(p_take, rem_global)
                    
                    if p_take > 0:
                        farm_in_route.inventory -= p_take
                        farm_in_route.last_visit_day = day_index
                        final_pigs_this_trip += p_take
                        remaining_cap_kg -= (p_take * farm_in_route.avg_weight)
                        truck.current_load_kg += (p_take * farm_in_route.avg_weight)
                
                truck.pigs_loaded = final_pigs_this_trip
                slaughtered_today += final_pigs_this_trip
                
                if not silent: print(f"  ✅ CONFIRMED. Stops: {len(truck.route)} | Pigs: {truck.pigs_loaded}")
                
                self.process_truck_trip(truck, daily_log, trip_dist_km, est_time, silent)
                active_trucks.append(truck) 
            else:
                pass 

        return daily_log

    def process_truck_trip(self, truck, daily_log, precalc_dist_km, trip_duration, silent=False):
        total_dist = precalc_dist_km
        route_names = [f.id for f in truck.route]
        
        load_factor = 0
        if truck.capacity_kg > 0:
            load_factor = truck.current_load_kg / truck.capacity_kg
            
        trip_cost = total_dist * truck.cost_per_km * load_factor
        
        avg_w_route = sum([f.avg_weight for f in truck.route]) / len(truck.route)
        rev, pen = self.calculate_revenue_batch(truck.pigs_loaded, avg_w_route, 5.0, silent)
        profit = rev - trip_cost
        
        fill_pct = load_factor * 100
        
        self.total_profit += profit
        self.total_penalties += pen
        self.total_transport_cost += trip_cost
        
        if not silent:
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
        print("\n[SYSTEM] STARTING SIMULATION...")
        
        for d in range(SIMULATION_DAYS):
            log = self.plan_day(d, silent=False)
            if log:
                self.results["daily_logs"].append(log)
        
        total_fixed_cost = 2 * len(self.trucks) * FIXED_COST_TRUCK_WEEKLY 
        self.total_profit -= total_fixed_cost
        self.total_transport_cost += total_fixed_cost
        
        # Ensure metadata is in final results
        self.results["metadata"] = {
            "slaughterhouse": SLAUGHTERHOUSE_LOC,
            "farms": {f.id: {"lat": f.lat, "lon": f.lon} for f in self.farms}
        }

        self.results["summary"] = {
            "total_profit_net": round(self.total_profit, 2),
            "total_transport_cost": round(self.total_transport_cost, 2),
            "total_penalties": round(self.total_penalties, 2),
            "final_farm_status": [{"id": f.id, "remaining": f.inventory, "weight": round(f.avg_weight, 1)} for f in self.farms]
        }
        
        return self.results

if __name__ == "__main__":
    sim = Simulation()
    results = sim.run()
    
    with open('simulation_results.json', 'w') as f:
        json.dump(results, f, indent=4)
        
    print("\n=== FINAL REPORT ===")
    print(f"Net Profit: {results['summary']['total_profit_net']} EUR")
    print("File 'simulation_results.json' generated.")
import json
import solve # Imports the whole engine

class Optimizer:
    def __init__(self):
        # Initialize simulation in 'manual' mode (auto_load=False)
        self.sim = solve.Simulation(auto_load=False)
        # Check if data exists
        self.sim.load_scenario_data()
        print(f"[OPTIMIZER] Engine loaded. Ready to analyze fleet configurations.")

    def run_scenario(self, num_small, num_large):
        # Reset full state
        self.sim.reset_simulation()
        # Set fleet for this test
        self.sim.setup_manual_fleet(num_small, num_large)
        
        # Run 14 days silently using FAST mode (use_api=False)
        for day in range(solve.SIMULATION_DAYS):
            self.sim.plan_day(day, silent=True, use_api=False) # Crucial: use_api=False for speed
            
        # Calculate Net
        fixed_costs = 2 * len(self.sim.trucks) * solve.FIXED_COST_TRUCK_WEEKLY
        net = self.sim.total_profit - fixed_costs
        return net, self.sim.total_penalties

    def find_optimal(self):
        print("\nRunning Fleet Tournament (Using shared engine)...")
        print(f"{'SM':<4} {'LG':<4} {'NET PROFIT':<12} {'PENALTIES':<10}")
        print("-" * 40)
        
        scenarios = [
            (1, 0), (2, 0), (3, 0), (4, 0),
            (1, 1), (2, 1), (3, 1), 
            (0, 1), (0, 2), (1, 2)
        ]
        
        best_cfg = None
        max_profit = -float('inf')
        
        for sm, lg in scenarios:
            net, pens = self.run_scenario(sm, lg)
            is_best = net > max_profit
            marker = "⭐" if is_best else ""
            print(f"{sm:<4} {lg:<4} {net:<12.0f} {pens:<10.0f} {marker}")
            
            if is_best:
                max_profit = net
                best_cfg = {"small": sm, "large": lg}
        
        # Output JSON
        with open('fleet_config.json', 'w') as f:
            json.dump(best_cfg, f, indent=4)
            
        print(f"\n✅ Optimal fleet saved to 'fleet_config.json': {best_cfg}")

if __name__ == "__main__":
    opt = Optimizer()
    opt.find_optimal()
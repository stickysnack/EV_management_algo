import matplotlib.pyplot as plt
import numpy as np
import os
from charging_robots_simulation import ChargingSimulation, PROBLEM_SCALES

# Create results directory if it doesn't exist
if not os.path.exists("results"):
    os.makedirs("results")

def run_comparative_simulation(scale="small", duration=24*60):
    """Run simulations with all strategies and compare results"""
    strategies = [
        "nearest_first",
        "max_charge_need_first", 
        "earliest_deadline_first",
        "most_urgent_first"
    ]
    
    results = {}
    
    for strategy in strategies:
        print(f"Running simulation with {strategy} strategy...")
        sim = ChargingSimulation(scale=scale, scheduling_strategy=strategy)
        sim.setup()
        stats = sim.run()
        
        # Store results
        results[strategy] = {
            "completion_rate": stats["completion_rate"],
            "avg_waiting_time": stats["avg_waiting_time"],
            "avg_charging_time": stats["avg_charging_time"],
            "battery_swaps": stats["battery_swaps"],
            "avg_robot_utilization": stats["avg_robot_utilization"],
            "completed_count": stats["completed_count"],
            "failed_count": stats["failed_count"]
        }

        print(f"  Completed: {stats['completed_count']}")
        print(f"  Failed: {stats['failed_count']}")
        print(f"  Completion rate: {stats['completion_rate']:.1f}%")
        print()
    
    # Generate comparison graphs
    generate_comparison_graphs(results, scale)
    
    return results


def generate_comparison_graphs(results, scale, filename="strategy_comparison"):
    """Generate graphs comparing different strategies"""
    # Setup
    plt.figure(figsize=(15, 12))
    
    # Convert strategy names for display
    strategy_names = {
        "nearest_first": "Nearest First",
        "max_charge_need_first": "Max Charge Need",
        "earliest_deadline_first": "Earliest Deadline",
        "most_urgent_first": "Most Urgent"
    }
    
    strategies = list(results.keys())
    x = np.arange(len(strategies))
    width = 0.2
    
    # 1. Completion Rate Comparison
    plt.subplot(2, 2, 1)
    completion_rates = [results[s]["completion_rate"] for s in strategies]
    plt.bar(x, completion_rates, width=0.6)
    plt.ylabel('Completion Rate (%)')
    plt.title(f'Completion Rate Comparison ({scale} Scale)')
    plt.xticks(x, [strategy_names.get(s, s) for s in strategies], rotation=45)
    
    for i, v in enumerate(completion_rates):
        plt.text(i, v + 1, f"{v:.1f}%", ha='center')
    
    # 2. Waiting and Charging Time Comparison
    plt.subplot(2, 2, 2)
    waiting_times = [results[s]["avg_waiting_time"] for s in strategies]
    charging_times = [results[s]["avg_charging_time"] for s in strategies]
    
    x1 = np.arange(len(strategies))
    x2 = [x + width for x in x1]
    
    plt.bar(x1, waiting_times, width, label='Avg. Waiting Time')
    plt.bar(x2, charging_times, width, label='Avg. Charging Time')
    
    plt.ylabel('Time (minutes)')
    plt.title(f'Time Comparison ({scale} Scale)')
    plt.xticks([x + width/2 for x in x1], [strategy_names.get(s, s) for s in strategies], rotation=45)
    plt.legend()
    
    # 3. Robot Utilization Comparison
    plt.subplot(2, 2, 3)
    utilization = [results[s]["avg_robot_utilization"] for s in strategies]
    plt.bar(x, utilization, width=0.6)
    plt.ylabel('Utilization (%)')
    plt.title(f'Robot Utilization Comparison ({scale} Scale)')
    plt.xticks(x, [strategy_names.get(s, s) for s in strategies], rotation=45)
    
    for i, v in enumerate(utilization):
        plt.text(i, v + 1, f"{v:.1f}%", ha='center')
    
    # 4. Completed vs Failed Vehicles
    plt.subplot(2, 2, 4)
    completed = [results[s]["completed_count"] for s in strategies]
    failed = [results[s]["failed_count"] for s in strategies]
    
    x1 = np.arange(len(strategies))
    x2 = [x + width for x in x1]
    
    plt.bar(x1, completed, width, label='Completed')
    plt.bar(x2, failed, width, label='Failed')
    
    plt.ylabel('Vehicle Count')
    plt.title(f'Vehicle Completion Comparison ({scale} Scale)')
    plt.xticks([x + width/2 for x in x1], [strategy_names.get(s, s) for s in strategies], rotation=45)
    plt.legend()
    
    # Save the figure
    plt.tight_layout()
    plt.savefig(f"results/{filename}_{scale}.png")
    plt.close()


def run_all_comparisons():
    """Run comparisons for all problem scales"""
    for scale in PROBLEM_SCALES.keys():
        print(f"\nRunning comparison for {scale} scale")
        results = run_comparative_simulation(scale=scale)
        
        # Display summary of best strategy for each metric
        print("\nBest strategies by metric:")
        
        # Completion rate
        best_strategy = max(results.items(), key=lambda x: x[1]["completion_rate"])[0]
        print(f"  Highest completion rate: {best_strategy} ({results[best_strategy]['completion_rate']:.1f}%)")
        
        # Waiting time (lower is better)
        best_strategy = min(results.items(), key=lambda x: x[1]["avg_waiting_time"])[0]
        print(f"  Lowest waiting time: {best_strategy} ({results[best_strategy]['avg_waiting_time']:.1f} min)")
        
        # Robot utilization
        best_strategy = max(results.items(), key=lambda x: x[1]["avg_robot_utilization"])[0]
        print(f"  Highest robot utilization: {best_strategy} ({results[best_strategy]['avg_robot_utilization']:.1f}%)")
        
        print("\n" + "="*50)


if __name__ == "__main__":
    run_all_comparisons()
from persistence.loader import load_employees_for_day, load_tasks
from optimizer import TaskOptimizer
import sys

def main():
    print("--- Daily Task Planner (15-min Resolution) ---")
    print("Loading data from TOML files...")
    
    try:
        employees = load_employees_for_day("turnos.toml", day_key="segunda")
        tasks = load_tasks("tarefas.toml", day_key="segunda")
    except Exception as e:
        print(f"Error loading data: {e}")
        # Identify if it's tomllib missing
        if "tomllib" in str(e) or "module" in str(e):
             print("TIP: Ensure you have Python 3.11+ or install 'tomli'.")
        return

    print(f"\nLoaded {len(employees)} employees and {len(tasks)} tasks.")
    
    # Filter out employees with no shifts
    active_employees = [e for e in employees if e.shifts]
    print(f"Active employees for Monday: {len(active_employees)}")
    
    if not active_employees or not tasks:
        print("No active employees or tasks found. Check your TOML data.")
        return

    print("\nRunning Optimizer (CP-SAT)...")
    optimizer = TaskOptimizer(active_employees, tasks)
    schedule = optimizer.solve()

    if schedule:
        print("\nOptimization Successful!")
        schedule_str = schedule.to_string(active_employees)
        print(schedule_str)
        
        with open("horario_segunda.txt", "w", encoding="utf-8") as f:
            f.write(schedule_str)
        print("\nSchedule saved to 'horario_segunda.txt'")
        
        # Calculate metrics (Optional verification)
        # metrics = schedule.calculate_metrics(active_employees, tasks)
        # print(f"Total Cost: {metrics.total_cost:.2f}")
    else:
        print("Failed to find a solution. Constraints might be too tight.")

if __name__ == "__main__":
    main()

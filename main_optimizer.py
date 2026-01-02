from model import Employee, Shift, Task, time_to_block
from optimizer import TaskOptimizer

def main():
    print("Initializing Optimization Demo (Phase 3)...\n")

    # 1. Setup Data (Similar to Phase 2)
    emp_fast = Employee("E_FAST", "FastWorker", 
        shifts=[Shift(time_to_block(8,0), time_to_block(12,0))],
        switch_cost=2.0 # High switch penalty
    )

    emp_steady = Employee("E_STEADY", "SteadyWorker",
        shifts=[Shift(time_to_block(8,0), time_to_block(16,0))],
        switch_cost=0.5
    )

    emp_spec = Employee("E_SPEC", "Specialist",
        shifts=[Shift(time_to_block(8,0), time_to_block(14,0))],
        ideal_tasks=["T_HARD"],
        switch_cost=1.0
    )

    employees = [emp_fast, emp_steady, emp_spec]

    # Tasks
    # T_HARD: 8 blocks (2 hours)
    # T_EASY: 8 blocks (2 hours)
    task_hard = Task("T_HARD", "HardTask", effort_required=8)
    task_easy = Task("T_EASY", "EasyTask", effort_required=8)
    
    tasks = [task_hard, task_easy]

    # 2. Run Optimizer
    print("Running Constraint Programming Solver...")
    optimizer = TaskOptimizer(employees, tasks)
    schedule = optimizer.solve()

    if schedule:
        print("\nOptimization Successful!")
        print(schedule.to_string(employees))
        
        # Calculate Phase 2 metrics on the result
        print("\nCalculating Behavioral Metrics on Optimized Schedule:")
        metrics = schedule.calculate_metrics(employees, tasks)
        print(f"Total Cost: {metrics.total_cost:.2f}")
    else:
        print("Failed to find a solution.")

if __name__ == "__main__":
    main()

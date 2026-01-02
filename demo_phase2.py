from model import Employee, Shift, Task, Schedule, time_to_block

def main():
    print("Initializing Behavioral Model Demo (Phase 2)...\n")

    # 1. Setup Data - Employees with varied profiles
    
    # "Fast but Fragile": Fast worker, but high fatigue rate.
    emp_fast = Employee("E_FAST", "FastWorker", 
        shifts=[Shift(time_to_block(8,0), time_to_block(12,0))],
        base_speed=1.5,
        fatigue_rate=0.05, # Drops 5% per 15 mins!
        switch_cost=1.0
    )

    # "Slow & Steady": Slow, but zero fatigue and low switch cost.
    emp_steady = Employee("E_STEADY", "SteadyWorker",
        shifts=[Shift(time_to_block(8,0), time_to_block(16,0))],
        base_speed=0.9,
        fatigue_rate=0.0,
        switch_cost=0.1
    )

    # "Specialist": Normal speed, high penalty for non-ideal tasks.
    emp_spec = Employee("E_SPEC", "Specialist",
        shifts=[Shift(time_to_block(8,0), time_to_block(12,0))],
        base_speed=1.0,
        ideal_tasks=["T_HARD"],
        switch_cost=2.0
    )

    employees = [emp_fast, emp_steady, emp_spec]

    # Tasks
    # T_HARD: Requires 6 units of effort. 
    # T_EASY: Requires 4 units.
    task_hard = Task("T_HARD", "HardTask", effort_required=6.0)
    task_easy = Task("T_EASY", "EasyTask", effort_required=4.0)
    
    tasks = [task_hard, task_easy]

    # 2. Schedule Allocation
    schedule = Schedule()
    
    start_time = time_to_block(8, 0)
    
    # Scenario:
    # SteadyWorker does EasyTask for 5 blocks (1.25 hours)
    # Expected progress: 5 blocks * 0.9 speed = 4.5 units (Complete > 4.0)
    for i in range(5):
        schedule.assign(start_time + i, emp_steady, task_easy)

    # FastWorker tries HardTask but gets tired.
    # Assignment: 5 blocks.
    # Speed sequence: 
    # 1. 1.5 * 1.00 = 1.5
    # 2. 1.5 * 0.95 = 1.425
    # 3. 1.5 * 0.90 = 1.35
    # 4. 1.5 * 0.85 = 1.275
    # 5. 1.5 * 0.80 = 1.2
    # Total ~ 6.75 units (Complete > 6.0)
    for i in range(5):
        schedule.assign(start_time + i, emp_fast, task_hard)
        
    # Specialist is assigned to EasyTask (Not Ideal!) -> Penalty
    for i in range(2):
        schedule.assign(start_time + i, emp_spec, task_easy)

    # 3. Calculate Metrics
    print("Calculating Behavioral Metrics...")
    metrics = schedule.calculate_metrics(employees, tasks)
    
    # 4. Results
    print(f"\nTotal Schedule Cost: {metrics.total_cost:.2f}")
    
    print("\nEmployee Costs Breakdown:")
    for emp in employees:
        cost = metrics.employee_costs.get(emp.id, 0)
        print(f"  - {emp.name}: {cost:.2f}")
        
    print("\nTask Progress:")
    for t in tasks:
        prog = metrics.task_progress.get(t.id, 0)
        status = "DONE" if prog >= t.effort_required else "INCOMPLETE"
        print(f"  - {t.name}: {prog:.2f} / {t.effort_required} ({status})")

    # 5. Validation
    errors = schedule.validate_overall(tasks, metrics)
    print("\nValidation Results:")
    if not errors:
        print("  SUCCESS: All usage constraints met.")
    else:
        for e in errors:
            print(f"  FAIL: {e}")

    # Visual
    print("\n" + schedule.to_string(employees))

if __name__ == "__main__":
    main()

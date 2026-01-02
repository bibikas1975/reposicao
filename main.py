from model import Employee, Shift, Task, Schedule, time_to_block

def main():
    print("Initializing Daily Task Planner Demo...\n")

    # 1. Setup Data
    # Employees with variable shifts
    # Ana: 08:00 - 12:00, 13:00 - 17:00 (Split shift)
    ana = Employee("E1", "Ana", [
        Shift(time_to_block(8, 0), time_to_block(12, 0)),
        Shift(time_to_block(13, 0), time_to_block(17, 0))
    ])

    # Bob: 06:00 - 14:00 (Continuous early)
    bob = Employee("E2", "Bob", [
        Shift(time_to_block(6, 0), time_to_block(14, 0))
    ])

    # Carlos: 14:00 - 22:00 (Continuous late)
    carlos = Employee("E3", "Carlos", [
        Shift(time_to_block(14, 0), time_to_block(22, 0))
    ])

    employees = [ana, bob, carlos]

    # Tasks
    # T1: Stocking (2 hours = 8 blocks)
    # T2: Cleaning (1 hour = 4 blocks)
    # T3: Cashier Morning (4 hours = 16 blocks)
    task_stocking = Task("T1", "Stock", 8) 
    task_cleaning = Task("T2", "Clean", 4)
    task_cashier  = Task("T3", "Cash", 16)
    
    tasks = [task_stocking, task_cleaning, task_cashier]

    # 2. Scheduling (Manual Valid Allocation)
    schedule = Schedule()

    # Bob does Cashier from 06:00 to 10:00 (16 blocks)
    start_b = time_to_block(6, 0)
    for i in range(16):
        schedule.assign(start_b + i, bob, task_cashier)

    # Ana does Stocking from 08:00 to 10:00 (8 blocks)
    # Note: Ana arrives at 08:00.
    start_a = time_to_block(8, 0)
    for i in range(8):
        schedule.assign(start_a + i, ana, task_stocking)

    # Bob does Cleaning from 10:00 to 11:00 (4 blocks)
    start_b2 = time_to_block(10, 0)
    for i in range(4):
        schedule.assign(start_b2 + i, bob, task_cleaning)

    # 3. Validation
    print("Validating Schedule...")
    errors = schedule.validate_overall(tasks)
    
    if not errors:
        print("SUCCESS: Schedule is valid!")
    else:
        print("ERRORS FOUND:")
        for e in errors:
            print(f"- {e}")
    
    # 4. Visualization
    print("\n" + schedule.to_string(employees))

if __name__ == "__main__":
    main()

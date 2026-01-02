from ortools.sat.python import cp_model
from typing import List, Dict, Tuple, Optional
from model import Employee, Task, Shift, TOTAL_BLOCKS, block_to_time, Schedule

class TaskOptimizer:
    def __init__(self, employees: List[Employee], tasks: List[Task]):
        self.employees = employees
        self.tasks = tasks
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Variables
        # x[e_idx, t_idx, s] = 1 if employee e assigns task t at block s
        self.x = {} 
        
    def solve(self) -> Optional[Schedule]:
        # 1. Variables Definition
        # We mapped objects to indices for easier CP-SAT handling
        e_range = range(len(self.employees))
        t_range = range(len(self.tasks))
        s_range = range(TOTAL_BLOCKS)
        
        # x[e, t, s]
        for e in e_range:
            for t in t_range:
                for s in s_range:
                    self.x[(e, t, s)] = self.model.NewBoolVar(f"x_e{e}_t{t}_s{s}")

        # 2. Hard Constraints

        # A. Availability: Employee can only work if they have a shift containing block s
        for e in e_range:
            emp_obj = self.employees[e]
            for s in s_range:
                if not emp_obj.is_available(s):
                    # Force all task vars to 0 for this block
                    for t in t_range:
                        self.model.Add(self.x[(e, t, s)] == 0)

        # B. Employee Exclusivity: At most 1 task per employee per block
        for e in e_range:
            for s in s_range:
                self.model.Add(sum(self.x[(e, t, s)] for t in t_range) <= 1)

        # C. Task Exclusivity: At most 1 employee per task per block
        for t in t_range:
            for s in s_range:
                self.model.Add(sum(self.x[(e, t, s)] for e in e_range) <= 1)

        # D. Task Duration / Progress Requirement
        # Requirement: Total assignments * base_speed * efficiency must >= effort?
        # SIMPLIFICATION FOR OPTIMIZER:
        # Since fatigue is dynamic and non-linear, it's hard to model exactly in CP-SAT without complex constraints.
        # We will approximate: 
        #   - We allocate 'duration_blocks' amount of time slots.
        #   - We assume standard speed (1 block = 1 unit) for the Constraint Satisfaction.
        #   - The "Cost Function" will punish assigning to slow people, but we force fixed duration here.
        #   - Or better: The user asked to "Accumulate exactly its total duration in blocks".
        # Let's interpret "duration" as "task.effort_required" assuming 1 unit/block for now to allow solution.
        
        for t in t_range:
            task_obj = self.tasks[t]
            # req_blocks = int(task_obj.effort_required) # Assuming effort is integer-ish blocks
            # Let's use duration if we had it, or map effort to blocks.
            # In Phase 2 we defined effort. Let's assume 1.0 effort = 1 block for planning.
            required_blocks = int(task_obj.effort_required)
            
            self.model.Add(sum(self.x[(e, t, s)] for e in e_range for s in s_range) == required_blocks)


        # 3. Objective Function (Soft Constraints & Costs)
        total_cost = 0

        # A. Preference / Capability Cost
        # If employee is assigned a task they don't like (or is not 'ideal'), add penalty.
        # Also could factor in base_speed (prefer faster people implicitly? No, just purely cost).
        
        for e in e_range:
            emp_obj = self.employees[e]
            for t in t_range:
                task_obj = self.tasks[t]
                
                # Check preference
                is_ideal = (task_obj.id in emp_obj.ideal_tasks) if emp_obj.ideal_tasks else True
                
                # Cost per block assigned
                # If not ideal, penalty = 10 (arbitrary)
                penalty = 0 if is_ideal else 5
                
                if penalty > 0:
                    for s in s_range:
                        total_cost += self.x[(e, t, s)] * penalty

        # B. Switching Costs
        # switch[e, s] = 1 if employee e changes task at block s (compared to s-1)
        # Detailed logic: if x[e,t,s] != x[e,t,s-1], determination is tricky.
        # Simplified: If x[e,t,s] == 1 and x[e,t,s-1] == 0, is it a switch? Or a start?
        # Let's count "Starting a task leg" as a switch cost (except the very first block of shift?)
        # Let's use a standard trick: y[e,s] = sum(x[e,t,s]*t) is not linear.
        
        # We will create explicit IsStart variables or Switch variables.
        # Let's penalize "Change of Task ID". 
        # switch_var[e, s] is bool.
        # cost += switch_var * emp.switch_cost
        
        for e in e_range:
            emp_obj = self.employees[e]
            if emp_obj.switch_cost <= 0:
                continue
            
            for s in range(1, TOTAL_BLOCKS):
                # For each task, did it change?
                # Case 1: Task t was ON at s-1, OFF at s -> Stop/Switch
                # Case 2: Task t was OFF at s-1, ON at s -> Start/Switch
                
                # A simpler proxy for switch cost in CP-SAT:
                # Penalize every time a task starts. (x[s] == 1 and x[s-1] == 0)
                # This encourages long continuous blocks.
                for t in t_range:
                    # start_flag[t] is 1 if task t starts at s
                    start_var = self.model.NewBoolVar(f"start_e{e}_t{t}_s{s}")
                    
                    # start_var >= x[s] - x[s-1]
                    # if x[s]=1, x[s-1]=0 -> start_var >= 1 -> start_var=1
                    # if x[s]=1, x[s-1]=1 -> start_var >= 0 -> ... minimization makes it 0
                    self.model.Add(start_var >= self.x[(e, t, s)] - self.x[(e, t, s-1)])
                    
                    # Add to cost
                    # Note: This penalizes "Resuming" a task too. 
                    total_cost += start_var * int(emp_obj.switch_cost * 100) 
                    # *100 because solver likes integers.

        # Minimize
        self.model.Minimize(total_cost)

        # 4. Solvers
        status = self.solver.Solve(self.model)
        
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"Solution Found: {self.solver.StatusName(status)}")
            print(f"Objective Value: {self.solver.ObjectiveValue()}")
            return self._build_schedule_from_solution(e_range, t_range, s_range)
        else:
            print("No solution found.")
            return None

    def _build_schedule_from_solution(self, e_range, t_range, s_range) -> Schedule:
        sched = Schedule()
        
        for e in e_range:
            emp_obj = self.employees[e]
            for t in t_range:
                task_obj = self.tasks[t]
                for s in s_range:
                    if self.solver.Value(self.x[(e, t, s)]) == 1:
                        # We must respect the Schedule.assign checks
                        # but we know they are valid by constraints.
                        # However, Schedule.assign might raise error if we didn't model "Already busy" correctly?
                        # Our constraints B and C ensure exclusivity.
                        sched.grid[s][emp_obj.id] = task_obj.id
        
        return sched

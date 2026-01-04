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

        # C. Task Capacity / Demand
        for t in t_range:
            task_obj = self.tasks[t]
            
            if task_obj.is_fixed():
                # --- FIXED SCHEDULE TASK (e.g. Caixa) ---
                # Must meet specific staffing demand at each time block
                demand_curve = task_obj.demand_curve
                
                for s in s_range:
                    demand = demand_curve[s] if s < len(demand_curve) else 0
                    
                    if demand > 0:
                        # Sum of assigned employees >= demand
                        self.model.Add(sum(self.x[(e, t, s)] for e in e_range) >= demand)
                    else:
                        # If demand is 0, should we force 0 assignment?
                        # Usually yes, unless it's 'optional' over-staffing.
                        # For 'Caixa', 0 demand means closed or no need?
                        # Let's enforce 0 to be clean, or allow it?
                        # Enforcing 0 prevents ghost working.
                        self.model.Add(sum(self.x[(e, t, s)] for e in e_range) == 0)

            else:
                # --- FLEXIBLE TASK (e.g. Reposicao) ---
                # 1. Total Volume Requirement
                required_blocks = int(task_obj.effort_required)
                self.model.Add(sum(self.x[(e, t, s)] for e in e_range for s in s_range) == required_blocks)
                
                # 2. Exclusivity (Single Worker per Task?)
                # "Reposição de Mercearia" -> can 2 people do it?
                # Usually YES, multiple people can stock shelves.
                # So we DO NOT enforce "sum(e) <= 1".
                # However, if it's a "One Person Job", we would.
                # Given the scale, assuming parallel work is allowed.
                pass

        # D. Skill Requirements
        for t in t_range:
            task_obj = self.tasks[t]
            if not task_obj.skill_needed:
                continue
                
            for e in e_range:
                emp_obj = self.employees[e]
                if not emp_obj.has_skill(task_obj.skill_needed):
                    # Cannot do this task ever
                    for s in s_range:
                        self.model.Add(self.x[(e, t, s)] == 0)


        # 3. Objective Function (Soft Constraints & Costs)
        total_cost = 0

        # A. Preference / Capability Cost
        for e in e_range:
            emp_obj = self.employees[e]
            for t in t_range:
                task_obj = self.tasks[t]
                
                # Check preference
                is_ideal = (task_obj.id in emp_obj.ideal_tasks) if emp_obj.ideal_tasks else True
                
                # Base penalty
                penalty = 0 if is_ideal else 5
                
                if penalty > 0:
                    for s in s_range:
                        total_cost += self.x[(e, t, s)] * penalty

        # B. Switching Costs (Continuity)
        for e in e_range:
            emp_obj = self.employees[e]
            if emp_obj.switch_cost <= 0:
                continue
            
            # Weighted switch cost
            cost_weight = int(emp_obj.switch_cost * 100)
            
            for s in range(1, TOTAL_BLOCKS):
                for t in t_range:
                    # Penalize starting a task segment
                    # start_var >= x[s] - x[s-1]
                    start_var = self.model.NewBoolVar(f"start_e{e}_t{t}_s{s}")
                    self.model.Add(start_var >= self.x[(e, t, s)] - self.x[(e, t, s-1)])
                    
                    total_cost += start_var * cost_weight

        # C. Priority Scheduling (High Priority Flexible Tasks -> Early)
        for t in t_range:
            task_obj = self.tasks[t]
            if task_obj.is_fixed():
                continue 
                
            # Priority Weight: 20.0 / priority
            # Prio 1 -> Weight 20, Prio 4 -> Weight 5
            time_penalty_weight = 20.0 / max(1, task_obj.priority)
            
            for e in e_range:
                for s in s_range:
                    # Cost += x[e,t,s] * s * weight
                    scaled_s = s * 0.1 
                    total_cost += self.x[(e, t, s)] * int(scaled_s * time_penalty_weight)

        # Minimize
        self.model.Minimize(total_cost)

        # 4. Solvers
        # To find OPTIMAL, we need more time or parallel search.
        # FEASIBLE means it hit the time limit or was happy enough.
        self.solver.parameters.max_time_in_seconds = 300.0 # Give it 5 minutes
        self.solver.parameters.num_search_workers = 8 # Use multi-core
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
                        # Direct assignment bypassing strict checking (as we trust the solver)
                        # We just populate the grid.
                        # Note: Sched.grid is Dict[emp_id, task_id]
                        sched.grid[s][emp_obj.id] = task_obj.id
        
        return sched

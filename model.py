from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

# --- Time Constants and Helpers ---
START_HOUR = 6
END_HOUR = 22 # Working day ends at 22:00? The input data has 22:30 shifts, sometimes 00:30.
# Let's extend the internal modeling range to handle late shifts properly.
# If we go up to 02:00 next day, that's 26 hours absolute.
PHYSICAL_END_HOUR = 26 
# 15 minute resolution
BLOCKS_PER_HOUR = 4 
TOTAL_BLOCKS = (PHYSICAL_END_HOUR - START_HOUR) * BLOCKS_PER_HOUR

def time_to_block(hour: int, minute: int) -> int:
    """Converts a time (HH:MM) to a block index."""
    # Handle wrapping hours (00:00 -> 24:00, 01:00 -> 25:00) strictly for calculation
    # Only if they are very small and we expect late night.
    effective_hour = hour
    if effective_hour < START_HOUR:
        effective_hour += 24
        
    if not (START_HOUR <= effective_hour < PHYSICAL_END_HOUR):
        # We allow a bit of buffer or just clamp?
        # For now raise error to be safe, but data might be dirty.
        # Check turnos: "20:30-00:30"
        pass
        
    relative_hour = effective_hour - START_HOUR
    block = relative_hour * BLOCKS_PER_HOUR + (minute // 15)
    return block

def block_to_time(block_idx: int) -> str:
    """Converts a block index back to HH:MM string."""
    total_minutes = block_idx * 15
    absolute_minutes = (START_HOUR * 60) + total_minutes
    
    hour = (absolute_minutes // 60) % 24
    minute = absolute_minutes % 60
    return f"{hour:02d}:{minute:02d}"

# --- Data Structures ---

@dataclass
class Shift:
    """Represents a continuous work period for an employee."""
    start_block: int
    end_block: int  # exclusive [start, end)
    
    def contains(self, block_idx: int) -> bool:
        return self.start_block <= block_idx < self.end_block

    def duration(self) -> int:
        return self.end_block - self.start_block

@dataclass
class Employee:
    """An employee with behavioral attributes."""
    id: str
    name: str
    shifts: List[Shift] = field(default_factory=list)
    
    # New Attributes from TOML
    category: str = "standard"
    profile: str = "standard"
    skills: List[str] = field(default_factory=list)
    
    # Behavioral Attributes
    base_speed: float = 1.0          
    switch_cost: float = 1.0         
    fatigue_rate: float = 0.0        
    ideal_tasks: List[str] = field(default_factory=list) 

    def is_available(self, block_idx: int) -> bool:
        """Checks if employee is working during a specific block."""
        return any(shift.contains(block_idx) for shift in self.shifts)
    
    def has_skill(self, skill: str) -> bool:
        if not skill: return True
        return skill in self.skills

@dataclass
class Task:
    """A specific task that needs to be done."""
    id: str
    name: str
    effort_required: float  # Total blocks required (for Flexible tasks)
    
    # New Attributes
    priority: int = 1 # Lower is more important (1=Highest)
    skill_needed: str = ""
    demand_curve: Optional[List[int]] = None # For Fixed tasks: list of N ints (staff count needed per block)
    
    def is_fixed(self) -> bool:
        return self.demand_curve is not None

# --- Schedule & Validation ---

@dataclass
class ScheduleMetrics:
    total_cost: float = 0.0
    task_progress: Dict[str, float] = field(default_factory=dict)
    employee_costs: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

class Schedule:
    """Holds the allocation of tasks to employees over time blocks."""
    def __init__(self):
        # allocation[block_idx] = { employee_id: task_id }
        self.grid: List[Dict[str, str]] = [{} for _ in range(TOTAL_BLOCKS)]
        
    def assign(self, block_idx: int, employee: Employee, task: Task):
        """Assigns a task to an employee for a specific block."""
        if not (0 <= block_idx < TOTAL_BLOCKS):
            raise ValueError(f"Block {block_idx} out of range.")
        
        if not employee.is_available(block_idx):
            raise ValueError(f"Employee {employee.name} is not on shift at {block_to_time(block_idx)}")

        if employee.id in self.grid[block_idx]:
            current_task = self.grid[block_idx][employee.id]
            raise ValueError(f"Employee {employee.name} already assigned to {current_task} at {block_to_time(block_idx)}")

        for emp_id, t_id in self.grid[block_idx].items():
            if t_id == task.id:
                 raise ValueError(f"Task {task.name} is already being worked on by {emp_id} at {block_to_time(block_idx)}")

        self.grid[block_idx][employee.id] = task.id

    def calculate_metrics(self, employees: List[Employee], tasks: List[Task]) -> ScheduleMetrics:
        metrics = ScheduleMetrics()
        metrics.task_progress = {t.id: 0.0 for t in tasks}
        metrics.employee_costs = {e.id: 0.0 for e in employees}
        
        task_map = {t.id: t for t in tasks}

        for emp in employees:
            consecutive_blocks = 0
            last_task_id = None
            
            # Iterate through the entire day to track state
            for b in range(TOTAL_BLOCKS):
                task_id = self.grid[b].get(emp.id)
                
                # Check if on shift
                on_shift = emp.is_available(b)
                
                if not on_shift:
                    consecutive_blocks = 0 # Reset fatigue if off shift? 
                    # Simplicity: taking a break (off shift) resets fatigue count.
                    last_task_id = None
                    continue
                
                # On shift logic
                if task_id:
                    # 1. State Update
                    consecutive_blocks += 1
                    
                    # 2. Switch Cost
                    if last_task_id is not None and task_id != last_task_id:
                        cost = emp.switch_cost
                        metrics.employee_costs[emp.id] += cost
                        metrics.total_cost += cost
                        # metrics.warnings.append(f"Switch cost for {emp.name} at {block_to_time(b)}")
                    
                    last_task_id = task_id

                    # 3. Progress Calculation (Effective Speed)
                    # Fatigue reduces speed linearly: speed * (1 - rate * count)
                    # Minimum speed clamped to 10% to prevent negative
                    fatigue_factor = max(0.1, 1.0 - (emp.fatigue_rate * consecutive_blocks))
                    effective_speed = emp.base_speed * fatigue_factor
                    
                    metrics.task_progress[task_id] += effective_speed
                    
                    # 4. Profile Penalty (if task not in ideal_tasks)
                    if emp.ideal_tasks and task_id not in emp.ideal_tasks:
                        # Penalty for doing non-ideal task
                        pen = 0.5 # Arbitrary constant
                        metrics.employee_costs[emp.id] += pen
                        metrics.total_cost += pen

                else:
                    # On shift but IDLE
                    # Reset consecutive work? Or does waiting tire you out?
                    # Let's say idle resets physical fatigue but adds 'Idle Cost'
                    consecutive_blocks = 0 
                    last_task_id = None
                    
                    idle_cost = 0.2 # Arbitrary idle penalty
                    metrics.employee_costs[emp.id] += idle_cost
                    metrics.total_cost += idle_cost

        return metrics

    def validate_overall(self, tasks: List[Task], metrics: ScheduleMetrics = None) -> List[str]:
        errors = []
        # If metrics not provided, we can't accept it easily without recalculating, 
        # but let's assume usage pattern is calculate -> validate.
        if not metrics:
             errors.append("Metrics not calculated properly.")
             return errors

        for task in tasks:
            progress = metrics.task_progress.get(task.id, 0)
            if progress < task.effort_required:
                errors.append(f"Task {task.name} incomplete: {progress:.2f}/{task.effort_required} units.")
            # We allow over-completion? Maybe warn?
            # elif progress > task.effort_required + 0.5: # Tolerance
            #    errors.append(f"Task {task.name} over-done.")

        return errors

    def to_string(self, employees: List[Employee]) -> str:
        """Returns a string representation of the schedule."""
        
        # Helper to find start block
        def get_start_block(emp):
            if not emp.shifts: return 9999
            # Assuming shifts are sorted or we take min
            return min(s.start_block for s in emp.shifts)

        # Sort employees by entry time
        sorted_employees = sorted(employees, key=get_start_block)
        
        lines = ["Schedule Visualization:"]
        
        # Header
        header = "Time   | " + " | ".join(f"{e.name[:5]:^5}" for e in sorted_employees)
        lines.append(header)
        lines.append("-" * len(header))

        for b in range(TOTAL_BLOCKS):
            time_str = block_to_time(b)
            row = f"{time_str}  | "
            
            # Optimization: skip rows where NO ONE is working?
            # Or keep all to show full day. Let's keep all.
            
            # Check if this row has ANY activity or just empty/vazio?
            # User wants to see the schedule, so standard view is fine.
            
            for e in sorted_employees:
                task_id = self.grid[b].get(e.id, "")
                if not e.is_available(b):
                    cell = "     " # Blank for not on shift
                elif task_id:
                    cell = f"{task_id[:5]:^5}"
                else:
                    cell = "Vazio" # Was Livre
                
                row += f"{cell} | "
            lines.append(row)
            
        return "\n".join(lines)

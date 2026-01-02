from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set

# --- Time Constants and Helpers ---
START_HOUR = 6
END_HOUR = 22
BLOCKS_PER_HOUR = 4
TOTAL_BLOCKS = (END_HOUR - START_HOUR) * BLOCKS_PER_HOUR

def time_to_block(hour: int, minute: int) -> int:
    """Converts a time (HH:MM) to a block index (0 to TOTAL_BLOCKS-1)."""
    if not (START_HOUR <= hour < END_HOUR):
        raise ValueError(f"Time {hour}:{minute} out of bounds ({START_HOUR}:00-{END_HOUR}:00)")
    
    relative_hour = hour - START_HOUR
    block = relative_hour * BLOCKS_PER_HOUR + (minute // 15)
    return block

def block_to_time(block_idx: int) -> str:
    """Converts a block index back to HH:MM string."""
    if not (0 <= block_idx < TOTAL_BLOCKS):
        return "OUT_OF_BOUNDS"
    
    total_minutes = block_idx * 15
    hour = START_HOUR + (total_minutes // 60)
    minute = total_minutes % 60
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
    
    # Behavioral Attributes
    base_speed: float = 1.0          # Multiplier for work progress (e.g. 1.2 is 20% faster)
    switch_cost: float = 0.0         # Cost penalty incurred when switching tasks
    fatigue_rate: float = 0.0        # Efficiency drop per consecutive block (e.g. 0.01 = 1% drop)
    ideal_tasks: List[str] = field(default_factory=list) # List of Task IDs this employee prefers/is good at

    def is_available(self, block_idx: int) -> bool:
        """Checks if employee is working during a specific block."""
        return any(shift.contains(block_idx) for shift in self.shifts)

@dataclass
class Task:
    """A specific task that needs to be done."""
    id: str
    name: str
    effort_required: float  # Total 'work units' required to complete. 
                            # (Formerly duration_blocks, now explicit effort).
                            # If base_speed=1 and no fatigue, 1 block = 1.0 effort.

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
        emp_map = {e.id: e for e in employees}
        lines = ["Schedule Visualization:"]
        
        # Header
        header = "Time   | " + " | ".join(f"{e.name[:5]:^5}" for e in employees)
        lines.append(header)
        lines.append("-" * len(header))

        for b in range(TOTAL_BLOCKS):
            time_str = block_to_time(b)
            row = f"{time_str}  | "
            
            for e in employees:
                task_id = self.grid[b].get(e.id, "")
                if not e.is_available(b):
                    cell = " --- " 
                elif task_id:
                    cell = f"{task_id[:5]:^5}"
                else:
                    cell = " IDLE" 
                
                row += f"{cell} | "
            lines.append(row)
            
        return "\n".join(lines)

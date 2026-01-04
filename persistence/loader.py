import tomllib
from typing import List, Dict, Any
from model import Employee, Shift, Task, time_to_block, TOTAL_BLOCKS, START_HOUR, END_HOUR

def load_toml(file_path: str) -> Dict[str, Any]:
    with open(file_path, "rb") as f:
        return tomllib.load(f)

def parse_time_str(time_str: str) -> int:
    """Converts 'HH:MM' string to block index (5-min resolution)."""
    try:
        hours, minutes = map(int, time_str.split(":"))
        return time_to_block(hours, minutes)
    except ValueError as e:
        raise ValueError(f"Invalid time format '{time_str}': {e}")

def parse_time_range(range_str: str) -> Shift:
    """Converts 'HH:MM-HH:MM' to a Shift object."""
    try:
        start_str, end_str = range_str.split("-")
        start_block = parse_time_str(start_str)
        # Handle cases where end time might be effectively next day (e.g. 00:00 -> 24:00 relative)?
        # For now, simplistic approach:
        # If end is 00:30, it might mean next day. But our model is single day 06:00-22:00.
        # The user data has "20:30-00:30". We need to handle wrapping or clamping.
        # Given START_HOUR=6, 00:30 is likely technically 'tomorrow'.
        # For this prototype, we'll clamp or special case if needed.
        # Actually, let's look at time_to_block implementation.
        # It expects hour >= START_HOUR.
        # If hour is 0, 1, 2... these are probably effectively 24, 25, 26 relative to start?
        # Let's adjust logic in model.py later to handle this, or handle it here.
        # For "00:30", let's treat it as hour 24.
        
        end_parts = end_str.split(":")
        end_h = int(end_parts[0])
        end_m = int(end_parts[1])
        if end_h < START_HOUR: 
             # likely next day, e.g. 00:30. Add 24h? 
             # Or just strictly use linear hours. 
             # Let's assume input might be "00:30" meaning +1 day.
             # We hack it here: if < START_HOUR, add 24.
             end_h += 24
             
        end_block = time_to_block(end_h, end_m)
        return Shift(start_block, end_block)
    except Exception as e:
        # Re-raise with context
        raise ValueError(f"Error parsing range '{range_str}': {e}")

def load_employees(file_path: str) -> List[Employee]:
    data = load_toml(file_path)
    employees = []
    
    # Simple mapping of day name to key in the file structure
    # As per turnos.toml: [funcionarios.horarios] -> segunda, terca...
    # We are loading for a SINGLE DAY for the optimization context.
    # Let's assume we pass the day_of_week to this function or load all?
    # The current optimizer is single-day. Let's start by loading "segunda" by default or making it an arg.
    # For now, I'll allow selecting the day.
    
    return employees # Stub for now, need the Day argument logic or decision.

def load_employees_for_day(file_path: str, day_key: str = "segunda") -> List[Employee]:
    data = load_toml(file_path)
    employee_list = []
    
    for emp_data in data.get("funcionarios", []):
        name = emp_data.get("nome", "Unknown")
        category = emp_data.get("categoria", "standard")
        profile = emp_data.get("perfil", "standard")
        skills = emp_data.get("competencias", [])
        
        # Schedule parsing
        # horarios = emp_data.get("horarios", {}) 
        # The file format was flattened: schedules are direct keys.
        day_schedule = emp_data.get(day_key, "VAZIO")
        
        shifts = []
        if isinstance(day_schedule, list):
            for interval in day_schedule:
                shifts.append(parse_time_range(interval))
        elif isinstance(day_schedule, str):
            if "-" in day_schedule: # Single interval "08:00-12:00"
                shifts.append(parse_time_range(day_schedule))
            else:
                # "VAZIO", "Folga...", etc. -> No shifts.
                pass
        
        # Create Employee
        # We need to map profile to params? Or just store profile string?
        # Model update will add 'profile' field.
        emp = Employee(
            id=name.replace(" ", "_"), # Simple ID generation
            name=name,
            shifts=shifts,
            profile=profile,
            category=category,
            skills=skills
        )
        # Determine strict parameters based on profile here? 
        # Or delegate to Employee class? 
        # Let's set defaults based on profile map here for now or just pass it through.
        # We'll stick to passing it through for the Model to handle logic if possible, 
        # OR set base_speed/switch_cost here.
        if profile == "sprinter":
            emp.switch_cost = 0.5 # Low switch cost, good for fast changes
            emp.base_speed = 1.1  # Fast
        elif profile == "constante":
            emp.switch_cost = 2.0 # High switch cost, dislikes change
            emp.base_speed = 1.0
        
        employee_list.append(emp)
        
    return employee_list

def load_tasks(file_path: str, day_key: str = "segunda") -> List[Task]:
    data = load_toml(file_path)
    tasks = []
    
    # Iterate over all keys that start with "tarefa."? 
    # The toml structure is [tarefa.caixa], [tarefa.congelados]
    # In python dict: data["tarefa"]["caixa"] ...
    
    tarefas_dict = data.get("tarefa", {})
    
    for t_key, t_data in tarefas_dict.items():
        t_name = t_data.get("nome", t_key)
        t_prio = t_data.get("prioridade", 1)
        t_skill = t_data.get("skill_requerida", "")
        
        # Check for flow (demand curve)
        # e.g. fluxo_segunda = [...]
        flow_key = f"fluxo_{day_key}"
        
        demand_curve = None
        is_fixed = False
        
        if flow_key in t_data:
            # Parse flow to demand curve
            # Format: [{ inicio="08:00", fim="10:30", funcionarios=1 }, ...]
            flow_list = t_data[flow_key]
            demand_curve = [0] * TOTAL_BLOCKS
            for interval in flow_list:
                start = parse_time_str(interval["inicio"])
                end = parse_time_str(interval["fim"])
                count = interval["funcionarios"]
                for b in range(start, end):
                    if b < TOTAL_BLOCKS:
                        demand_curve[b] = count
            is_fixed = True
            effort = sum(demand_curve) # Total person-blocks needed
        else:
            # Volume based
            # carga_paletes = { segunda = 5 ... }
            cargas = t_data.get("carga_paletes", {})
            # If cargas is a dict, get day. If direct value?
            load = 0
            if isinstance(cargas, dict):
                load = cargas.get(day_key, 0)
            else:
                load = int(cargas) # fallback
                
            if load <= 0 and not is_fixed:
                continue # No work for this task this day
                
            # Convert load to effort (blocks)
            # tempo_por_palete_minutos
            mins_per_unit = t_data.get("tempo_por_palete_minutos", 60)
            total_minutes = load * mins_per_unit
            effort = total_minutes / 15.0 # 15 min blocks
            
        task = Task(
            id=t_key,
            name=t_name,
            priority=t_prio,
            effort_required=effort,
            skill_needed=t_skill,
            demand_curve=demand_curve
        )
        tasks.append(task)
        
    return tasks

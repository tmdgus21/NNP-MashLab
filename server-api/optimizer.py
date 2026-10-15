"""CP-SAT: one shared meeting interval, exact role staffing, one role/person."""
from ortools.sat.python import cp_model


def covered(ranges, day, start, end):
    return all(any(r["date"] == day and r["start"] <= slot and r["end"] >= slot + 30 for r in ranges) for slot in range(start, end, 30))


def overlaps(ranges, day, start, end):
    return any(r["date"] == day and r["start"] < end and r["end"] > start for r in ranges)


def solve(config, participants, round_number, max_seconds=5):
    model = cp_model.CpModel()
    candidates = [(day, start, start + config["duration"]) for day in config["dates"] for start in range(config["windowStart"], config["windowEnd"] - config["duration"] + 1, 30)]
    selected = [model.new_bool_var(f"time_{i}") for i in range(len(candidates))]
    model.add_exactly_one(selected)
    choices, active, score = {}, {}, []
    roles = config["roles"]
    for p in participants:
        c = p["conditions"]
        active[p["id"]] = model.new_bool_var(f"active_{p['id']}")
        person_vars = []
        for role in roles:
            role_vars = []
            for index, (day, start, end) in enumerate(candidates):
                if role not in c["roles"] or role in c.get("roleUnavailable", []):
                    continue
                if not covered(c["availability"], day, start, end) or overlaps(c.get("unavailable", []), day, start, end):
                    continue
                var = model.new_bool_var(f"x_{p['id']}_{role}_{index}")
                choices[p["id"], role, index] = var
                model.add(var <= selected[index])
                person_vars.append(var)
                role_vars.append(var)
                points = 20 if role in c.get("rolePreferences", []) else 0
                if c["preference"] == "early":
                    points += (1440 - start) // 30
                elif c["preference"] == "late":
                    points += start // 30
                for preferred in c.get("timePreferences", []):
                    if overlaps([preferred], day, start, end):
                        points += 10 if preferred["kind"] == "available" else -10
                if points:
                    score.append(points * var)
            if role in c.get("requiredRoles", []):
                model.add(sum(role_vars) == 1)
        model.add(sum(person_vars) == active[p["id"]])
    for index in range(len(candidates)):
        for role in roles:
            variables = [choices[p["id"], role, index] for p in participants if (p["id"], role, index) in choices]
            model.add(sum(variables) == config["roleNeeds"][role] * selected[index])
    for p in participants:
        c = p["conditions"]
        requirements = list(c.get("companionRequirements", []))
        if c.get("companionId"):
            requirements.append({"participantId": c["companionId"], "relation": "together", "strength": "required"})
        for req in requirements:
            a, b = active[p["id"]], active[req["participantId"]]
            if req["strength"] == "required":
                model.add(a <= b if req["relation"] == "together" else a + b <= 1)
            else:
                satisfied = model.new_bool_var(f"companion_{len(score)}")
                if req["relation"] == "together":
                    model.add(satisfied <= a)
                    model.add(satisfied <= b)
                    model.add(satisfied >= a + b - 1)
                else:
                    model.add(satisfied <= a)
                    model.add(satisfied + b <= 1)
                    model.add(satisfied >= a - b)
                score.append(15 * satisfied)
    model.maximize(sum(score))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 42
    status = solver.solve(model)
    name = solver.status_name(status)
    if name == "MODEL_INVALID":
        raise RuntimeError("CP-SAT model invalid")
    feasible = name in ("OPTIMAL", "FEASIBLE")
    assignments = []
    if feasible:
        for (person, role, index), variable in choices.items():
            if solver.value(variable):
                day, start, end = candidates[index]
                assignments.append({"id": f"{round_number}-{person}-{role}", "role": role, "participantId": person, "interval": {"date": day, "start": start, "end": end}, "status": "proposed"})
    detail = {"OPTIMAL": "필수조건을 만족하는 최적 배정입니다.", "FEASIBLE": "필수조건은 만족하지만 제한시간 내 최적성은 증명하지 못했습니다.", "INFEASIBLE": "가능시간·역할·필요인원·동반 필수조건을 동시에 만족할 수 없습니다.", "UNKNOWN": "제한시간 내 해 또는 불가능 여부를 확인하지 못했습니다. 다시 계산해 주세요."}[name]
    return {"round": round_number, "status": "feasible" if feasible else "infeasible" if name == "INFEASIBLE" else "unknown", "solverStatus": name, "assignments": assignments, "notices": [{"id": "solver", "kind": "info" if feasible else "error" if name == "INFEASIBLE" else "warning", "title": name, "detail": detail}]}

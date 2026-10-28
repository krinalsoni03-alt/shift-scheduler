#!/usr/bin/env python3
"""
Employee Shift Scheduler (Python)

Collects employee names and ranked shift preferences for each day of the week,
then builds a weekly schedule that satisfies these rules:
  * No employee works more than one shift per day.
  * No employee works more than MAX_DAYS_PER_WEEK days.
  * Every shift has at least MIN_PER_SHIFT employees (filled randomly if needed).
  * A shift holds at most MAX_PER_SHIFT employees; when an employee's preferred
    shift is full, the conflict is resolved by moving them to another shift on
    the same day, or carrying them over to the next day.
  * Bonus: preferences are ranked (1st choice, 2nd choice, ...) and honoured in order.

Usage:
    python3 scheduler.py            # interactive input
    python3 scheduler.py --demo     # run with built-in sample data
    python3 scheduler.py --demo --seed 7
"""

import argparse
import random

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SHIFTS = ["Morning", "Afternoon", "Evening"]

MIN_PER_SHIFT = 2
MAX_PER_SHIFT = 3
MAX_DAYS_PER_WEEK = 5

RANDOM = "random"   # choice_rank marker for randomly filled slots


# --------------------------------------------------------------------------- #
#  Input
# --------------------------------------------------------------------------- #
SHIFT_ALIASES = {
    "m": "Morning", "morn": "Morning", "morning": "Morning",
    "a": "Afternoon", "aft": "Afternoon", "afternoon": "Afternoon",
    "e": "Evening", "eve": "Evening", "evening": "Evening",
}


def parse_shift(token):
    """Turn user text such as 'm', 'morning', 'AFT' into a shift name (or None)."""
    return SHIFT_ALIASES.get(token.strip().lower())


def parse_ranking(text):
    """'e, m' -> ['Evening', 'Morning']; blank -> [] (no preference / unavailable)."""
    ranking = []
    for token in text.replace(",", " ").split():
        shift = parse_shift(token)
        if shift is None:
            raise ValueError(f"'{token}' is not a valid shift (use m, a or e)")
        if shift not in ranking:          # ignore duplicates
            ranking.append(shift)
    return ranking


def collect_input():
    """Interactively collect employees and their ranked preferences."""
    employees = {}  # name -> {day: [shift ranked 1st, 2nd, ...]}
    print("Enter employee names (blank line to finish).")
    print("For each day, list shifts in order of preference: m = morning, "
          "a = afternoon, e = evening.")
    print("Example: 'e m' means Evening first, Morning second. Leave blank for no preference.\n")

    while True:
        name = input("Employee name: ").strip()
        if name == "":
            break
        if name in employees:
            print(f"  '{name}' was already entered, skipping.")
            continue

        prefs = {}
        for day in DAYS:
            while True:                       # re-prompt until input is valid
                try:
                    prefs[day] = parse_ranking(input(f"  {day:<9} preference(s): "))
                    break
                except ValueError as err:
                    print(f"    {err}. Try again.")
        employees[name] = prefs
        print()

    return employees


def demo_employees():
    """Sample data: 11 employees with ranked preferences (blank = no preference).

    Monday is deliberately over-requested (morning especially) to exercise the
    conflict logic, and Sunday is under-requested to exercise the random fill.
    """
    #            Mon    Tue    Wed    Thu    Fri    Sat    Sun
    raw = {
        "Alice":  ["m a", "m",   "m",   "",    "m e", "",    ""],
        "Bob":    ["e",   "e",   "",    "e a", "e",   "e",   ""],
        "Carlos": ["m a", "",    "a",   "a",   "",    "a m", ""],
        "Diana":  ["m",   "m",   "m",   "m",   "",    "",    ""],
        "Ethan":  ["m e", "",    "e",   "e",   "e",   "",    "e"],
        "Fatima": ["a e", "a",   "",    "a",   "a",   "",    ""],
        "George": ["m",   "m a", "",    "m",   "m",   "",    ""],
        "Hana":   ["e",   "",    "e a", "",    "a",   "a",   ""],
        "Ivan":   ["a",   "a",   "a",   "",    "",    "e",   "m"],
        "Julia":  ["m a", "e",   "m",   "",    "",    "m",   ""],
        "Kevin":  ["m",   "a",   "",    "e",   "",    "m",   ""],
    }
    return {name: {day: parse_ranking(r) for day, r in zip(DAYS, rankings)}
            for name, rankings in raw.items()}


# --------------------------------------------------------------------------- #
#  Scheduling
# --------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, employees, seed=None):
        self.employees = employees
        self.rng = random.Random(seed)
        # schedule[day][shift] -> list of employee names
        self.schedule = {day: {shift: [] for shift in SHIFTS} for day in DAYS}
        self.days_worked = {name: 0 for name in employees}
        self.assigned_on = {name: {} for name in employees}   # name -> {day: shift}
        self.log = []                                         # conflict / fill messages
        self.choice_rank = {}                                 # (name, day) -> rank met (1, 2, ...), None or RANDOM

    # ---- helpers -------------------------------------------------------- #
    def can_work(self, name, day):
        return day not in self.assigned_on[name] and self.days_worked[name] < MAX_DAYS_PER_WEEK

    def has_room(self, day, shift):
        return len(self.schedule[day][shift]) < MAX_PER_SHIFT

    def assign(self, name, day, shift, rank=None):
        self.schedule[day][shift].append(name)
        self.assigned_on[name][day] = shift
        self.days_worked[name] += 1
        self.choice_rank[(name, day)] = rank

    def unassign(self, name, day):
        shift = self.assigned_on[name].pop(day)
        self.schedule[day][shift].remove(name)
        self.days_worked[name] -= 1
        self.choice_rank.pop((name, day), None)
        return shift

    def try_any_open_shift(self, name, day):
        """Put the employee in the emptiest open shift that day. Returns the shift or None."""
        open_shifts = [s for s in SHIFTS if self.has_room(day, s)]
        if not open_shifts:
            return None
        shift = min(open_shifts, key=lambda s: len(self.schedule[day][s]))
        self.assign(name, day, shift)
        return shift

    # ---- phase 1: preferences + conflict resolution --------------------- #
    def assign_preferences(self):
        carry_over = []   # employees bumped from the previous day

        for index, day in enumerate(DAYS):
            next_carry = []

            # Carried-over employees go first so they are not bumped twice.
            order = carry_over + [n for n in self.employees if n not in carry_over]

            for name in order:
                if not self.can_work(name, day):
                    continue

                ranking = self.employees[name][day]
                carried = name in carry_over
                if not ranking and not carried:
                    continue                      # no request for this day

                placed = False
                for rank, shift in enumerate(ranking, start=1):
                    if self.has_room(day, shift):
                        self.assign(name, day, shift, rank)
                        placed = True
                        break

                if placed:
                    if carried:
                        self.log.append(f"CARRYOVER {day:<9} {name}: placed on "
                                        f"{self.assigned_on[name][day]}")
                    continue

                # Conflict: every preferred shift is full (or a carry-over with no ranking).
                shift = self.try_any_open_shift(name, day)
                if shift is not None:
                    reason = "carried over from previous day" if carried and not ranking \
                        else f"preferred {'/'.join(ranking)} full"
                    self.log.append(f"CONFLICT  {day:<9} {name}: {reason} -> moved to {shift}")
                elif index + 1 < len(DAYS):
                    next_carry.append(name)
                    self.log.append(f"CONFLICT  {day:<9} {name}: all shifts full "
                                    f"-> carried over to {DAYS[index + 1]}")
                else:
                    self.log.append(f"CONFLICT  {day:<9} {name}: all shifts full and no "
                                    f"next day -> not scheduled")

            carry_over = next_carry

    # ---- phase 2: guarantee minimum staffing ----------------------------- #
    def fill_understaffed(self):
        for day in DAYS:
            for shift in SHIFTS:
                while len(self.schedule[day][shift]) < MIN_PER_SHIFT:
                    candidates = [n for n in self.employees if self.can_work(n, day)]
                    if candidates:
                        name = self.rng.choice(candidates)
                        self.assign(name, day, shift, RANDOM)
                        self.log.append(f"FILL     {day:<9} {shift:<9} "
                                        f"<- {name} (randomly assigned)")
                        continue

                    # Nobody free: move someone from an over-staffed shift on another day.
                    if not self.rebalance(day, shift):
                        self.log.append(f"WARNING   {day:<9} {shift:<9} only "
                                        f"{len(self.schedule[day][shift])} staff - "
                                        f"not enough employees available")
                        break

    def rebalance(self, day, shift):
        """Move someone from an over-staffed shift into (day, shift)."""
        # 1) Same day: shift someone over from a fuller shift.
        for other_shift in SHIFTS:
            if other_shift != shift and len(self.schedule[day][other_shift]) > MIN_PER_SHIFT:
                name = self.rng.choice(self.schedule[day][other_shift])
                self.unassign(name, day)
                self.assign(name, day, shift)
                self.log.append(f"REBALANCE {day:<9} {shift:<9} <- {name} "
                                f"(moved from {day} {other_shift})")
                return True

        # 2) Another day: free up a 5-day employee by moving one of their extra shifts here.
        names = list(self.employees)
        self.rng.shuffle(names)
        for name in names:
            if day in self.assigned_on[name]:
                continue
            for other_day, other_shift in list(self.assigned_on[name].items()):
                if len(self.schedule[other_day][other_shift]) > MIN_PER_SHIFT:
                    self.unassign(name, other_day)
                    self.assign(name, day, shift)
                    self.log.append(f"REBALANCE {day:<9} {shift:<9} <- {name} "
                                    f"(moved from {other_day} {other_shift})")
                    return True

        # 3) Swap: someone with spare days covers a 5-day employee's other shift,
        #    and that employee moves here.
        for name in names:
            if day in self.assigned_on[name]:
                continue
            for other_day, other_shift in list(self.assigned_on[name].items()):
                subs = [n for n in self.employees if self.can_work(n, other_day)]
                if subs:
                    sub = self.rng.choice(subs)
                    self.unassign(name, other_day)
                    self.assign(sub, other_day, other_shift, RANDOM)
                    self.assign(name, day, shift)
                    self.log.append(f"REBALANCE {day:<9} {shift:<9} <- {name} "
                                    f"({sub} covers {name}'s {other_day} {other_shift})")
                    return True
        return False

    def build(self):
        self.assign_preferences()
        self.fill_understaffed()
        return self.schedule


# --------------------------------------------------------------------------- #
#  Output
# --------------------------------------------------------------------------- #
def print_schedule(scheduler):
    col = 26
    line = "+" + "-" * 11 + ("+" + "-" * (col + 2)) * len(SHIFTS) + "+"

    print("\n" + "=" * len(line))
    print("FINAL WEEKLY SCHEDULE".center(len(line)))
    print("=" * len(line))
    print(line)
    print("| " + f"{'Day':<9} " + "".join(f"| {s:<{col}} " for s in SHIFTS) + "|")
    print(line)
    for day in DAYS:
        cells = [", ".join(scheduler.schedule[day][s]) for s in SHIFTS]
        print("| " + f"{day:<9} " + "".join(f"| {c:<{col}} " for c in cells) + "|")
    print(line)

    print("\nDays worked per employee (max 5):")
    for name in scheduler.employees:
        days = scheduler.days_worked[name]
        print(f"  {name:<8} {days}  " + "#" * days)

    ranks = list(scheduler.choice_rank.values())
    first, second, third = ranks.count(1), ranks.count(2), ranks.count(3)
    reassigned, filled = ranks.count(None), ranks.count(RANDOM)
    print(f"\nAssignment results ({len(ranks)} total): {first} first choice, "
          f"{second} second choice, {third} third choice, {reassigned} reassigned, "
          f"{filled} randomly filled")

    if scheduler.log:
        print("\nConflicts and adjustments:")
        for entry in scheduler.log:
            print("  " + entry)


def main():
    parser = argparse.ArgumentParser(description="Build a weekly employee shift schedule.")
    parser.add_argument("--demo", action="store_true", help="use built-in sample data")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    args = parser.parse_args()
    seed = args.seed

    employees = demo_employees() if args.demo else collect_input()

    if not employees:
        print("No employees entered. Exiting.")
        return

    needed = len(DAYS) * len(SHIFTS) * MIN_PER_SHIFT
    capacity = len(employees) * MAX_DAYS_PER_WEEK
    if capacity < needed:
        print(f"\nNote: {len(employees)} employees x {MAX_DAYS_PER_WEEK} days = {capacity} "
              f"shifts, but {needed} are required. Some shifts will be short-staffed.")

    scheduler = Scheduler(employees, seed)
    scheduler.build()
    print_schedule(scheduler)


if __name__ == "__main__":
    main()

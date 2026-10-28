# Employee Shift Scheduler

A command-line Python program that builds a weekly shift schedule from employees' ranked shift preferences.

## Rules it enforces

- Each employee works at most one shift per day.
- Each employee works at most 5 days per week.
- Every shift (Morning, Afternoon, Evening) has at least 2 employees, filled randomly if not enough people asked for it.
- A shift holds at most 3 employees. If an employee's preferred shift is full, they get their next choice, then any open shift that day, and if the whole day is full they are carried over to the next day.
- Preferences are ranked (1st choice, 2nd choice, ...) and honoured in order.

## Usage

Requires Python 3.6+ and no extra packages.

```bash
python3 scheduler.py              # enter employees and preferences interactively
python3 scheduler.py --demo       # run with built-in sample data
python3 scheduler.py --demo --seed 7
```

When entering preferences, use `m` (morning), `a` (afternoon) and `e` (evening) in order of preference, e.g. `e m` = Evening first, Morning second. Leave blank for no preference.

## Output

- A table of the final weekly schedule
- Days worked per employee
- How many assignments were 1st/2nd/3rd choices, reassigned, or randomly filled
- A log of every conflict, carry-over, random fill and rebalance

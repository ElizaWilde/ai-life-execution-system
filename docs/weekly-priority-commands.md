# Weekly-priority commands

The coach supports `create_weekly_priorities` as a planning-agent operation.
The LLM interprets the complete request into one `CommandInterpretation` tool
call containing a bounded list of `weekly_priorities`. No regex parsing or
automatic daily-task generation is involved.

For example, requesting three priorities at 10h each produces three items with
`target_minutes: 600`. A missing priority value defaults to Medium independently
for each item. The current user-local week is used unless another week is stated.

Execution flow:

1. Validate the tool arguments, including nonblank titles, integer minutes,
   allowed priorities and a maximum of 20 items.
2. The deterministic decision layer rejects duplicate names inside the batch or
   in any non-cancelled weekly goal whose date range overlaps the selected week.
   Other users' goals do not participate in matching.
3. Show the entire batch, week dates, priorities and total hours for confirmation.
4. Revalidate the batch and duplicate constraints against current data when confirmed.
5. Delegate to `PlanningService.create_weekly_priorities`, which stages only
   `WeeklyGoal` records. The coordinator commits the complete batch together
   with command completion. An execution failure rolls back the batch.

An identical idempotency key returns the existing command. Confirming a completed
command returns its existing result without creating another batch. Rejecting a
preview creates no goals. Weekly priorities appear under Key Priorities This Week;
they do not reserve calendar time until daily tasks are separately scheduled.

Regression coverage is in `backend/tests/test_weekly_priority_commands.py`.

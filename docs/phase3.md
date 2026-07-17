# Phase 3 — Intelligent Automation

## 1. What Phase 3 is trying to achieve

In Phase 1, the system records plans and study activity.

In Phase 2, the system analyzes the user's condition and provides recommendations.

In Phase 3, the system should begin acting **proactively**.

This means the system should not wait for the user to open the application and ask:

> What should I do?

Instead, it should automatically notice situations such as:

* A task is about to start.
* A deadline is approaching.
* A task has been postponed several times.
* The weekly goal is becoming difficult to complete.
* Today's workload is unrealistic.
* The user has ignored several reminders.

The system can then:

* Send a reminder.
* Update a forecast.
* Detect a risk.
* Suggest a schedule change.
* Ask the user to approve an action.

The purpose of Phase 3 is therefore:

```text
Observe the plan
→ detect problems
→ propose an appropriate response
→ safely apply approved changes
```

Phase 3 should make the application proactive, but not fully autonomous.

---

# 2. The complete Phase 3 workflow

The final workflow should look like this:

```text
User creates a weekly and daily plan
            ↓
Scheduler checks the system periodically
            ↓
System detects reminders, overdue tasks, or risks
            ↓
Rules determine whether action is needed
            ↓
System sends a notification or creates a proposal
            ↓
User confirms important changes
            ↓
Backend applies the approved action
            ↓
System records the result
            ↓
Forecast and plan are recalculated
```

Every Phase 3 step exists to support part of this workflow.

---

# 3. Step 1 — Define automation permissions

## What to build

Classify automation actions into three permission levels.

### Safe automatic actions

The system may perform these actions without confirmation:

* Send reminders.
* Detect overdue tasks.
* Calculate forecasts.
* Detect possible procrastination.
* Generate suggestions.

### Actions requiring confirmation

The system must ask the user before:

* Moving a task.
* Changing task duration.
* Reducing a weekly goal.
* Updating tasks in Notion.
* Applying a rescheduling proposal.

### Actions that must never happen silently

The system must not silently:

* Delete tasks.
* Cancel goals.
* Change important deadlines.
* Replace a user-created plan.

## Why this step is necessary

Before creating automation, the system needs clear boundaries.

Without permission rules, an AI-generated decision could directly change important user data.

For example:

```text
System detects that the user is behind
→ AI decides to delete two tasks
→ database is updated automatically
```

This is unsafe because the user did not approve the change.

The correct design is:

```text
System detects that the user is behind
→ system generates a proposal
→ user reviews it
→ user approves it
→ backend applies it
```

## Output of this step

Create enums or constants such as:

```python
class AutomationLevel(str, Enum):
    SAFE_AUTOMATIC = "safe_automatic"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    NEVER_SILENT = "never_silent"
```

This permission system will later be used by reminders, commands, rescheduling, and the coordinator.

---

# 4. Step 2 — Add user automation preferences

## What to build

Store automation settings for each user:

* Time zone.
* Morning notification time.
* Evening review time.
* Quiet hours.
* Working days.
* Preferred study periods.
* Notification channel.
* Maximum reminders per day.
* Automatic rescheduling enabled or disabled.
* Confirmation requirements.

## Why this step is necessary

Automation cannot behave correctly without knowing the user's preferences.

For example, a reminder scheduled for `08:00` is incomplete information.

The system also needs to know:

```text
08:00 in which time zone?
Should reminders be sent during weekends?
Is 08:00 inside quiet hours?
Which notification channel should be used?
```

Without these settings, the scheduler may send messages at the wrong time or perform actions the user does not want.

## Output of this step

Create a model such as:

```text
UserAutomationPreference
```

It becomes the source of constraints for all automated jobs.

---

# 5. Step 3 — Build the notification system

## What to build

Create one notification service that can send messages through one provider.

For the first version, use only one channel:

* Telegram, or
* Email.

Do not implement several providers at the beginning.

The service should support:

* Morning-plan notification.
* Upcoming-task reminder.
* Overdue-task warning.
* Deadline warning.
* Evening check-in.
* Weekly-review notification.
* Rescheduling proposal.

Every notification delivery should record:

* User.
* Notification type.
* Message.
* Scheduled time.
* Delivery time.
* Delivery status.
* Failure reason.

## Why this step is necessary

Detection alone does not help the user.

For example:

```text
System detects that a task is overdue
```

Nothing changes unless the user is informed.

The notification service is the communication layer between the automation system and the user.

It also separates business logic from delivery logic.

```text
Reminder service decides what message is needed
Notification service decides how to send it
```

## Output of this step

Create:

```text
notification_service.py
notification_delivery model
notification provider adapter
```

---

# 6. Step 4 — Add a background scheduler

## What to build

Use APScheduler to run jobs automatically.

The scheduler should run jobs such as:

* Check due reminders.
* Detect overdue tasks.
* Recalculate forecasts.
* Detect procrastination signals.
* Generate rescheduling proposals.
* Send morning notifications.
* Send evening notifications.

Run the scheduler as a separate Docker service.

## Why this step is necessary

FastAPI normally runs code only when an API request arrives.

Without a scheduler:

```text
User does not open the application
→ no API request is made
→ no reminder check runs
→ no notification is sent
```

With a scheduler:

```text
08:00 arrives
→ scheduler starts morning notification job
→ job loads today's plan
→ notification is sent
```

The scheduler gives the system the ability to act without waiting for the user.

## Why it should be a separate Docker service

Suppose FastAPI runs with four workers:

```bash
uvicorn app.main:app --workers 4
```

If APScheduler starts inside FastAPI, every worker may start its own scheduler.

The same job could then run four times:

```text
Worker 1 sends reminder
Worker 2 sends reminder
Worker 3 sends reminder
Worker 4 sends reminder
```

Instead, use:

```text
api service       → handles HTTP requests
scheduler service → runs scheduled jobs
database          → stores shared data
```

Example:

```yaml
services:
  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  scheduler:
    build: .
    command: python -m app.scheduler_main

  postgres:
    image: postgres:16
```

## Output of this step

Create:

```text
app/scheduler_main.py
app/scheduler/scheduler.py
app/scheduler/jobs/
```

---

# 7. Step 5 — Implement reminders

## What to build

Create reminder records with fields such as:

* Reminder type.
* Related task.
* Scheduled time.
* User time zone.
* Delivery channel.
* Enabled state.
* Recurrence rule.
* Last execution time.
* Next execution time.

The execution process should be:

```text
Scheduler finds due reminder
→ check whether reminder is still relevant
→ generate message
→ send notification
→ record result
→ calculate next execution time
```

## Why this step is necessary

The scheduler only decides **when a function should run**.

It does not know:

* Which reminder belongs to which user.
* Which task is related.
* Whether the task is already completed.
* Whether the reminder repeats.
* Whether the notification was already sent.

The reminder model stores this information.

## Important rule

Before sending a reminder, check the current task state.

Do not send the reminder when the task is:

```text
completed
cancelled
moved to another time
```

## Output of this step

Create:

```text
Reminder model
Reminder service
Reminder APIs
Reminder scheduled job
```

---

# 8. Step 6 — Define task lifecycle states

## What to build

Use explicit task states:

```text
planned
in_progress
completed
deferred
overdue
cancelled
```

Also store:

* Original planned date.
* Current planned date.
* Deadline.
* Estimated duration.
* Actual duration.
* Priority.
* Number of deferrals.
* Last activity time.
* Completion time.

## Why this step is necessary

Automation must understand what happened to a task.

Consider a task whose planned date was yesterday.

It may be:

* Forgotten.
* Intentionally moved.
* Completed late.
* Cancelled.
* Still in progress.

Without lifecycle states, the system cannot distinguish these cases.

For example:

```text
planned date passed
```

does not always mean:

```text
task is overdue
```

The user may have intentionally deferred it.

## Output of this step

Update the task model and task service before building overdue detection or rescheduling.

---

# 9. Step 7 — Detect overdue tasks

## What to build

Create a deterministic service that checks tasks.

A task may be overdue when:

```text
planned date has passed
and task is not completed
and task is not cancelled
and task was not intentionally moved
```

Classify overdue tasks:

### Low severity

* Optional task.
* Deadline is far away.
* First delay.

### Medium severity

* Important task.
* Delay affects the weekly plan.
* Still recoverable.

### High severity

* Deadline is close.
* Task has been postponed several times.
* Missing it will affect an important goal.

## Why this step is necessary

The system must detect a problem before it can respond to it.

This service should only answer:

> Which tasks require attention?

It should not immediately move tasks.

Detection and action must remain separate:

```text
Overdue detector → identifies the problem
Rescheduling service → proposes a solution
User → approves important changes
```

This separation makes the system easier to test and safer to operate.

## Output of this step

Create:

```text
overdue_detection_service.py
overdue detection scheduled job
overdue event records
```

---

# 10. Step 8 — Build rescheduling proposals

## What to build

When unfinished work exists, calculate possible future dates.

Consider:

* Priority.
* Deadline.
* Estimated duration.
* Remaining weekly capacity.
* Daily workload limit.
* Energy and readiness.
* Existing future tasks.
* Preferred working periods.
* Previous postponements.

The process should be:

```text
Find unfinished tasks
→ calculate future available capacity
→ rank tasks
→ select possible dates
→ create a proposal
→ request confirmation
→ apply approved changes
```

## Why this step is necessary

Simply moving all unfinished tasks to tomorrow creates a new problem.

Example:

```text
Tomorrow already contains 240 minutes of work
Today's unfinished work adds another 180 minutes
New total = 420 minutes
```

The plan becomes unrealistic.

The rescheduling service must therefore consider workload capacity instead of only changing dates.

## Important rule

Do not repeatedly move the same task to the next day.

After several deferrals:

```text
Task deferred 4 times
→ stop automatic movement
→ classify as persistent problem
→ suggest reducing scope, duration, or priority
```

## Output of this step

Create:

```text
rescheduling_service.py
rescheduling proposal model
proposal approval APIs
```

---

# 11. Step 9 — Store proposals before applying changes

## What to build

A proposal should store:

* Affected tasks.
* Original dates.
* Proposed dates.
* Reason for each change.
* Expected workload.
* Creation time.
* Expiration time.
* Status.

Recommended statuses:

```text
pending
approved
rejected
applied
expired
```

## Why this step is necessary

A suggestion is not the same as an actual change.

Without a proposal record, the system may directly modify tasks before the user reviews the result.

The proposal creates a controlled workflow:

```text
System suggests
→ user reviews
→ user approves or rejects
→ backend applies only approved changes
```

It also allows the frontend to display an automation inbox.

## Output of this step

Create:

```text
ReschedulingProposal
ReschedulingProposalItem
Approve/reject/apply services
```

---

# 12. Step 10 — Detect procrastination patterns

## What to build

Begin with rules, not machine learning.

Possible signals:

* Task repeatedly deferred.
* Several reminders ignored.
* High-priority task repeatedly avoided.
* Planned focus time is much higher than actual focus time.
* User works on low-priority tasks instead of urgent tasks.
* No activity during preferred working periods.
* Completion rate is below the recent baseline.
* Similar tasks are repeatedly postponed.

Each detection should include:

* Detection type.
* Severity.
* Evidence.
* Related tasks.
* Confidence.
* Recommended intervention.

Example types:

```text
repeated_postponement
planning_overload
task_ambiguity
low_energy_avoidance
unrealistic_duration
deadline_avoidance
```

## Why this step is necessary

An overdue task tells the system **what happened**.

Procrastination detection tries to explain **what pattern may be causing it**.

Example:

```text
Task A was missed once
→ probably not enough evidence

Task A was deferred five times
and reminders were ignored
and similar tasks were avoided
→ repeated avoidance pattern
```

The system should not treat one missed task as proof of procrastination.

## Output of this step

Create:

```text
procrastination_detection_service.py
procrastination_event model
rule definitions
```

---

# 13. Step 11 — Select an intervention

## What to build

Map detected patterns to possible responses.

Examples:

### Large or unclear task

```text
Intervention:
Break task into smaller subtasks.
Ask for the first concrete action.
```

### Low energy

```text
Intervention:
Reduce the next work block.
Move optional tasks.
```

### Repeated avoidance

```text
Intervention:
Schedule task during strongest working period.
Ask whether the task is still relevant.
```

### Unrealistic planning

```text
Intervention:
Reduce daily workload.
Update task-duration estimate.
```

## Why this step is necessary

Detection without a response is not useful.

The intervention layer answers:

> Given this detected problem, what should the system recommend?

Rules should decide which interventions are allowed.

The LLM may explain the recommendation in natural language, but it should not decide permission boundaries.

## Output of this step

Create:

```text
intervention_service.py
mapping between detection types and interventions
```

---

# 14. Step 12 — Forecast goal completion

## What to build

Estimate whether a task or weekly goal will be completed on time.

Start with a transparent formula.

Use data such as:

* Remaining work.
* Remaining days.
* Recent completion rate.
* Average daily focus time.
* Required daily effort.
* Deadline distance.
* Number of overdue tasks.
* Previous deferrals.
* Current readiness.
* Historical performance.

Return:

* Completion probability.
* Risk level.
* Risk factors.
* Required daily effort.
* Current daily effort.
* Recommended adjustment.

Example:

```text
Weekly goal: 15 hours
Completed: 6 hours
Remaining: 9 hours
Days remaining: 3
Required effort: 3 hours/day
Current average: 1.8 hours/day

Risk level: high
```

## Why this step is necessary

Overdue detection identifies a problem that has already happened.

Forecasting tries to identify a problem before it happens.

For example:

```text
No tasks are overdue yet
but current progress is too slow
→ weekly goal is likely to fail
```

This gives the system time to recommend an adjustment.

## Output of this step

Create:

```text
forecast_service.py
forecast model
forecast scheduled job
forecast APIs
```

---

# 15. Step 13 — Store forecast history

## What to build

Do not overwrite old forecasts.

Store:

* Forecast time.
* Predicted probability.
* Risk level.
* Data used.
* Actual final outcome.

## Why this step is necessary

Without history, you cannot evaluate whether the forecasting logic is accurate.

Example:

```text
Monday forecast: 80%
Wednesday forecast: 55%
Friday result: incomplete
```

Later, the system can measure:

* Overconfidence.
* Underconfidence.
* Error by goal type.
* Accuracy by risk category.

This data can support a learned model in Phase 4.

## Output of this step

Create:

```text
ForecastHistory
ForecastOutcomeEvaluation
```

---

# 16. Step 14 — Add natural-language commands

## What to build

Allow commands such as:

```text
Move today's unfinished tasks to tomorrow.
Remind me about FastAPI at 8 PM.
Reduce today's workload.
Why am I behind this week?
What should I focus on now?
```

Map them to intents:

```text
create_reminder
reschedule_task
reduce_workload
get_progress
get_forecast
get_coaching
complete_task
unknown
```

Extract parameters such as:

* Task.
* Date.
* Time.
* Duration.
* Requested action.
* Priority.

## Why this step is necessary

Users should not need to manually open several forms for every action.

Natural-language commands provide a simpler interface.

However, the LLM should only convert language into structured data.

Example:

```text
User message
→ intent: create_reminder
→ task: FastAPI
→ time: 20:00
```

The LLM should not directly update the database.

## Output of this step

Create:

```text
command schema
intent classifier
parameter extractor
command API
```

---

# 17. Step 15 — Map commands to backend services

## What to build

Connect each intent to an existing service.

Examples:

```text
create_reminder
→ reminder_service.create()
```

```text
reschedule_task
→ rescheduling_service.create_proposal()
```

```text
get_forecast
→ forecast_service.get_current()
```

## Why this step is necessary

The LLM is not the business-logic layer.

The backend must still enforce:

* Authentication.
* Ownership checks.
* Validation.
* Permission rules.
* Confirmation requirements.
* Database constraints.

The correct flow is:

```text
User command
→ LLM extracts structured intent
→ backend validates it
→ approved service executes
→ result is returned
```

## Output of this step

Create a controlled tool registry or command dispatcher.

---

# 18. Step 16 — Add confirmation for write operations

## What to build

Read-only commands may run immediately.

Examples:

```text
Show my forecast.
Why am I behind?
What should I focus on?
```

Commands that change data should require confirmation.

Example:

```text
User:
Move today's unfinished tasks to tomorrow.

System:
Three tasks will be moved.
Tomorrow's workload will become 210 minutes.
Confirm?
```

## Why this step is necessary

Natural language can be ambiguous.

The user may not understand the full effect of the requested action.

Confirmation lets the system show:

* Which records will change.
* How workload will change.
* Whether deadlines are affected.

## Output of this step

Create:

```text
pending command model
confirm command API
reject command API
```

---

# 19. Step 17 — Add a coordinator workflow

## What to build

After all independent services work, connect them through one coordinator.

The coordinator should:

1. Receive the request.
2. Classify intent.
3. Extract parameters.
4. Load required context.
5. Validate the request.
6. Choose one approved service.
7. Check whether confirmation is needed.
8. Execute or store a pending action.
9. Format the result.
10. Record the execution.

A simple workflow is enough:

```text
Receive command
      ↓
Classify intent
      ↓
Validate parameters
      ↓
Need confirmation?
   ↙             ↘
 yes              no
 ↓                 ↓
Store pending     Execute service
action             ↓
   ↘             Format result
```

## Why this step comes late

The coordinator depends on the other services.

If the reminder service, forecast service, and rescheduling service do not exist, the coordinator has nothing reliable to call.

Therefore:

```text
Build services first
→ connect them with the coordinator later
```

Do not build several specialized agents in Phase 3.

One coordinator with approved tools is enough.

## Output of this step

Create a simple LangGraph workflow or normal Python coordinator service.

---

# 20. Step 18 — Add audit records

## What to build

Record every automated action:

* User.
* Trigger source.
* Automation type.
* Input.
* Decision.
* Service called.
* Records changed.
* Confirmation status.
* Execution status.
* Failure reason.
* Start time.
* Completion time.

Possible trigger sources:

```text
scheduler
user_command
API_request
forecast_threshold
procrastination_detector
```

## Why this step is necessary

Automation may change plans without the user manually opening an edit form.

When something unexpected happens, you need to answer:

* What changed?
* Why did it change?
* Which process triggered it?
* Did the user approve it?
* Did the action succeed?

Without audit logs, debugging automation becomes very difficult.

## Output of this step

Create:

```text
AutomationAudit
AutomationAction
```

---

# 21. Step 19 — Prevent duplicate execution

## What to build

Use unique action identifiers and execution states:

```text
pending
running
completed
failed
cancelled
```

Ensure only one process can claim an action.

Protect against:

* Duplicate reminders.
* Duplicate forecasts.
* Duplicate proposals.
* Applying one proposal twice.
* Processing one overdue task repeatedly.

## Why this step is necessary

Scheduled jobs may run more than once because of:

* Scheduler restart.
* Network retry.
* Docker restart.
* Multiple workers.
* Job timeout.
* Manual retry.

For example:

```text
Notification sent successfully
→ process crashes before status is saved
→ job runs again
→ same notification is sent twice
```

Idempotency ensures that repeating the same operation does not create additional effects.

## Output of this step

Add:

```text
unique execution key
database uniqueness constraints
row locking or atomic claim operation
```

---

# 22. Step 20 — Add failure recovery

## What to build

Define behavior for failures.

### Temporary failure

Examples:

* Notification provider unavailable.
* Database connection temporarily fails.
* Cloud Ollama times out.

Response:

```text
retry with a maximum limit
```

### Invalid or stale action

Examples:

* Task was completed after proposal creation.
* User changed the task date.
* Proposal expired.

Response:

```text
mark proposal as expired or failed
do not apply it
```

### LLM unavailable

Response:

```text
continue deterministic reminders
continue overdue detection
continue forecasts
skip AI-generated explanation
```

## Why this step is necessary

Automation runs without the user watching every operation.

Failures must therefore be handled automatically and predictably.

The entire automation system should not stop because the cloud model is unavailable.

## Output of this step

Create:

```text
retry policy
failure states
stale-data validation
fallback behavior
```

---

# 23. Step 21 — Add Phase 3 APIs

## What to build

### Reminder APIs

```text
POST   /reminders
GET    /reminders
PATCH  /reminders/{id}
DELETE /reminders/{id}
GET    /notification-history
```

### Automation APIs

```text
POST /automation/detect-overdue
POST /automation/rescheduling-proposals
GET  /automation/proposals
POST /automation/proposals/{id}/approve
POST /automation/proposals/{id}/reject
GET  /automation/history
```

### Forecast APIs

```text
POST /forecasts/weekly
GET  /forecasts/current
GET  /forecasts/history
```

### Command APIs

```text
POST /commands
POST /commands/{id}/confirm
POST /commands/{id}/reject
GET  /commands/history
```

## Why this step is necessary

The frontend and scheduler need stable ways to access the services.

APIs expose the completed business functions to:

* Frontend pages.
* Natural-language coordinator.
* Manual testing.
* Future integrations.

## Output of this step

Create routers and schemas using the services already implemented.

---

# 24. Step 22 — Add frontend interfaces

## What to build

### Reminder settings

Allow the user to configure:

* Reminder times.
* Quiet hours.
* Notification channels.
* Enabled reminder types.

### Automation inbox

Display:

* Rescheduling proposals.
* Confirmation requests.
* Procrastination warnings.
* Workload reduction suggestions.

### Forecast panel

Display:

* Completion probability.
* Risk level.
* Required daily effort.
* Current daily effort.
* Main risk factors.

### AI command box

Allow the user to enter commands and review parsed actions.

### Automation history

Display:

* What happened.
* Why it happened.
* What changed.
* Whether approval was required.
* Whether the action succeeded.

## Why this step comes last

The frontend depends on completed backend APIs.

Building the frontend first would require mock data and frequent redesign when backend models change.

The safer order is:

```text
Database and services
→ scheduler and automation
→ APIs
→ frontend
```

---

# 25. Recommended implementation order

The previous sections describe the complete architecture.

For actual coding, use this smaller implementation sequence.

## Stage A — Safety and configuration

1. Define automation permissions.
2. Add user automation preferences.
3. Finalize task lifecycle states.

Reason:

```text
Automation must know what it may do,
when it may do it,
and what each task state means.
```

## Stage B — Basic proactive behavior

4. Build one notification provider.
5. Add reminder storage and APIs.
6. Add the separate APScheduler service.
7. Execute due reminders.

Reason:

```text
This creates the first complete proactive workflow:
time arrives → scheduler runs → notification is sent
```

## Stage C — Detect execution problems

8. Add overdue-task detection.
9. Add rule-based procrastination detection.
10. Add intervention recommendations.

Reason:

```text
The system can now observe execution and identify problems.
```

## Stage D — Adapt the plan

11. Add rescheduling proposals.
12. Add approval and rejection.
13. Apply approved changes.

Reason:

```text
The system can propose plan changes without modifying data silently.
```

## Stage E — Predict future risk

14. Add completion forecasting.
15. Store forecast history.
16. Compare predictions with actual results.

Reason:

```text
The system can identify future risk before goals fail.
```

## Stage F — Natural-language control

17. Add command classification.
18. Map commands to backend services.
19. Add confirmation for write operations.
20. Add the coordinator workflow.

Reason:

```text
Natural language becomes an interface to services that already work.
```

## Stage G — Reliability and interface

21. Add audit records.
22. Add idempotency.
23. Add failure recovery.
24. Add Phase 3 frontend pages.
25. Test the complete workflow.

Reason:

```text
The automation becomes traceable, reliable, and usable.
```

---

# 26. Minimum Phase 3 version

You do not need to implement all advanced features immediately.

The minimum useful Phase 3 version is:

```text
1. User configures reminder preferences.
2. Scheduler runs as a separate Docker service.
3. Scheduler finds due reminders.
4. Notification service sends Telegram or email messages.
5. Overdue tasks are detected.
6. System creates a rescheduling proposal.
7. User approves or rejects the proposal.
8. Approved changes are applied once.
9. Every action is recorded.
```

After this workflow works, add:

```text
procrastination detection
completion forecasting
natural-language commands
LangGraph coordinator
```

---

# 27. Phase 3 completion condition

Phase 3 is complete when the following scenario works:

```text
1. The user creates tasks and weekly goals.
2. The user chooses reminder times and quiet hours.
3. The scheduler runs independently from FastAPI.
4. The scheduler sends reminders at the correct local time.
5. An unfinished task becomes overdue.
6. The overdue detector identifies it.
7. The rescheduling service finds available future capacity.
8. The system creates a proposal instead of directly changing the task.
9. The user approves the proposal.
10. The backend safely updates the task.
11. The weekly forecast is recalculated.
12. The user receives a notification.
13. The system stores an audit record.
14. Restarting the scheduler does not duplicate the action.
```

The final Phase 3 execution loop is:

```text
Plan
→ schedule
→ observe
→ detect
→ forecast
→ propose
→ confirm
→ apply
→ notify
→ record
```

This is the purpose of the Phase 3 steps: each one builds a required part of a safe, proactive automation loop.

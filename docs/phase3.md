# Phase 3 — Intelligent Automation

Phase 3 turns the system from a passive coaching application into a proactive assistant. Its main functions are reminders, automatic rescheduling, procrastination detection, completion forecasting, and natural-language commands. 

## Step 1 — Define automation rules

Before adding schedulers or agents, decide what the system may do automatically.

Separate actions into three levels:

1. **Safe automatic actions**

   * Send reminders
   * Generate forecasts
   * Detect overdue tasks
   * Suggest schedule changes

2. **Actions requiring confirmation**

   * Move tasks to another day
   * Change task duration
   * Reduce a weekly goal
   * Update Notion tasks

3. **Actions that should never happen silently**

   * Delete tasks
   * Cancel goals
   * Modify important deadlines
   * Replace user-created plans

This prevents the automation system from making unexpected changes.

---

## Step 2 — Add user automation preferences

Allow each user to configure:

* Time zone
* Morning reminder time
* Evening review time
* Preferred notification channel
* Whether automatic rescheduling is enabled
* Whether confirmation is required
* Maximum number of reminders per day
* Quiet hours
* Working days
* Preferred study periods

These settings become the constraints for every scheduled action.

---

## Step 3 — Create the notification system

Build one notification interface that supports different channels.

Start with one channel, such as Telegram or email. Do not implement several channels at the same time.

The notification system should support:

* Morning-plan notification
* Upcoming-task reminder
* Missed-task reminder
* Deadline warning
* Evening check-in reminder
* Weekly-review notification
* Rescheduling proposal

Every delivery should record:

* User
* Notification type
* Message
* Scheduled time
* Actual delivery time
* Delivery status
* Failure reason

This allows failed notifications to be inspected and retried.

---

## Step 4 — Introduce a background scheduler

The scheduler runs tasks without waiting for an API request.

For the current project, APScheduler is sufficient for Phase 3.

It should periodically run jobs such as:

* Check for reminders that are due
* Find overdue tasks
* Detect procrastination signals
* Recalculate completion forecasts
* Generate rescheduling proposals
* Send morning and evening notifications

Run the scheduler as a separate Docker service rather than inside every FastAPI process. Otherwise, multiple API workers may execute the same job several times.

---

## Step 5 — Implement scheduled reminders

Add reminder creation and management.

A reminder should contain:

* Reminder type
* Target task or plan
* Scheduled execution time
* User time zone
* Delivery channel
* Enabled or disabled state
* Recurrence rule
* Last execution time
* Next execution time

The reminder process should be:

```text
Scheduler finds due reminder
→ validate reminder is still relevant
→ generate message
→ send notification
→ record delivery result
→ calculate next execution time
```

A task reminder should not be sent when the task is already completed, cancelled, or moved.

---

## Step 6 — Define task lifecycle states

Automatic rescheduling requires explicit task states.

Recommended states:

```text
planned
in_progress
completed
deferred
overdue
cancelled
```

Also track:

* Original planned date
* Current planned date
* Deadline
* Estimated duration
* Actual duration
* Priority
* Number of previous deferrals
* Last activity time
* Completion time

Without these fields, the system cannot reliably distinguish a delayed task from an intentionally postponed task.

---

## Step 7 — Build overdue-task detection

Create a deterministic service that identifies tasks requiring attention.

A task may be considered overdue when:

* Its planned date has passed
* It is not completed or cancelled
* Its deadline has not been intentionally changed
* It has not already been processed by the same automation cycle

The detector should classify overdue tasks by severity:

* **Low severity:** optional task, no close deadline
* **Medium severity:** important task, still recoverable
* **High severity:** deadline approaching or repeatedly deferred

The detector should only identify the condition. It should not immediately move the task.

---

## Step 8 — Implement automatic rescheduling logic

The rescheduling service determines where unfinished work can be moved.

It should consider:

* Task priority
* Deadline
* Estimated duration
* Remaining weekly capacity
* Daily workload limits
* Phase 2 readiness score
* Sleep, energy, mood, and stress data
* Existing tasks on future days
* Number of previous postponements
* User working preferences

The process should be:

```text
Find unfinished tasks
→ calculate available future capacity
→ rank tasks by urgency and importance
→ select suitable future dates
→ create a rescheduling proposal
→ request confirmation when required
→ apply approved changes
→ notify the user
```

Do not repeatedly move the same task to the next day. After several deferrals, mark it as a persistent problem and ask the user to reconsider its scope, priority, or duration.

---

## Step 9 — Store rescheduling proposals

Before changing the actual plan, store a proposal containing:

* Tasks affected
* Original dates
* Proposed dates
* Reason for each change
* Expected workload after the change
* Creation time
* Expiration time
* Status: pending, approved, rejected, applied, expired

This gives the user visibility and allows the application to separate suggested actions from committed actions.

---

## Step 10 — Implement procrastination detection

Start with rule-based detection rather than machine learning.

Possible signals include:

* Task repeatedly deferred
* Task is overdue
* User starts a task but records little progress
* Several reminders are ignored
* Completion rate falls below the recent baseline
* User frequently completes low-priority tasks while avoiding high-priority tasks
* Planned study time is much higher than actual focus time
* Similar tasks are consistently postponed
* No task activity during preferred working periods

The detector should produce:

* Detection type
* Severity
* Supporting evidence
* Related tasks
* Confidence level
* Recommended intervention

Example classifications:

```text
Repeated postponement
Planning overload
Low-energy avoidance
Task ambiguity
Unrealistic duration estimate
Deadline avoidance
```

Avoid treating every missed task as procrastination. Low energy, illness, lack of time, or external interruptions may explain the behavior.

---

## Step 11 — Add intervention strategies

After detecting a procrastination pattern, select a suitable intervention.

Examples:

* Break a large task into smaller subtasks
* Reduce the next work block to 15–25 minutes
* Move optional tasks away from the current day
* Ask the user to define the first concrete action
* Schedule the avoided task during the user’s strongest working period
* Replace a vague task with a measurable outcome
* Reduce workload based on Phase 2 readiness
* Ask the user whether the goal is still relevant

The LLM can explain the intervention, but deterministic rules should decide which actions are allowed.

---

## Step 12 — Build completion-probability forecasting

The forecast estimates whether a weekly goal or task will be completed on time.

Begin with a transparent scoring model, not a complex machine-learning model.

Use features such as:

* Remaining work
* Remaining days
* Recent completion rate
* Average daily focus time
* Estimated task duration
* Deadline distance
* Number of overdue tasks
* Number of previous deferrals
* Current readiness score
* Historical performance on similar goals

The result should include:

* Completion probability
* Risk level
* Main risk factors
* Required average daily effort
* Current average daily effort
* Recommended adjustment

Example interpretation:

```text
High probability: 75–100%
Moderate probability: 40–74%
Low probability: 0–39%
```

The forecast should be recalculated after task completion, rescheduling, new check-ins, or major plan changes.

---

## Step 13 — Compare forecasts with actual outcomes

Store each forecast rather than replacing it.

Later, compare:

* Predicted probability
* Actual completion result
* Forecast date
* Data available at forecast time

This lets you evaluate whether the forecasting logic is useful.

Track metrics such as:

* Accuracy by risk category
* Overconfidence
* Underconfidence
* Forecast error
* Accuracy for different task types

Phase 3 does not require a trained prediction model, but it should collect data that could support one later.

---

## Step 14 — Add natural-language command classification

Allow the user to control the system using commands such as:

```text
Move today’s unfinished tasks to tomorrow.
What should I focus on now?
Reduce today’s workload.
Remind me about the database task at 8 PM.
Why am I behind this week?
Show tasks at risk of missing their deadlines.
```

The first task is intent classification.

Recommended intents:

```text
view_today_plan
create_reminder
update_reminder
complete_task
reschedule_task
reduce_workload
get_progress
get_forecast
get_coaching
generate_weekly_review
unknown
```

The command system should extract structured parameters such as:

* Task
* Date
* Time
* Duration
* Priority
* Requested action
* Confirmation status

---

## Step 15 — Convert commands into tool calls

Each command intent should map to an existing backend service.

For example:

```text
“Remind me about FastAPI at 8 PM”
→ create reminder tool
```

```text
“Move unfinished tasks to tomorrow”
→ generate rescheduling proposal tool
```

```text
“How likely am I to finish this week?”
→ completion forecast tool
```

Do not let the LLM directly update the database.

The correct flow is:

```text
User command
→ LLM extracts intent and arguments
→ backend validates arguments
→ approved service is called
→ result is returned
```

This keeps authentication, ownership checks, and business rules inside normal application services.

---

## Step 16 — Add confirmation for write operations

Natural-language commands that change data should use confirmation.

Example:

```text
User: Move my unfinished tasks to tomorrow.

System:
Three tasks will be moved:
- FastAPI router practice
- PostgreSQL notes
- README update

Tomorrow’s planned workload will become 210 minutes.
Confirm?
```

After confirmation:

```text
Apply proposal
→ record automation action
→ return updated plan
```

Read-only commands do not require confirmation.

---

## Step 17 — Add a lightweight coordinator workflow

After reminder, rescheduling, forecasting, and command services work independently, connect them with a coordinator.

The coordinator should:

1. Receive a natural-language request.
2. Determine the intent.
3. Load required context.
4. Select one approved tool.
5. Execute the tool.
6. Determine whether confirmation is required.
7. Return the result.
8. Record the execution.

LangGraph can be introduced here, but only after the underlying services already work.

A simple graph is sufficient:

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
Store pending     Execute tool
action             ↓
   ↘             Format response
```

Do not build separate planner, coach, reminder, and analytics agents in Phase 3. One coordinator with tools is enough.

---

## Step 18 — Add automation audit records

Every automated action should be traceable.

Record:

* User
* Trigger source
* Automation type
* Input data
* Decision
* Tool called
* Records changed
* Whether confirmation was required
* Execution status
* Failure reason
* Start and completion times

Trigger sources may include:

```text
scheduler
user_command
API_request
procrastination_detector
forecast_threshold
```

This is essential for debugging unexpected schedule changes.

---

## Step 19 — Add idempotency and concurrency protection

Scheduled jobs may run more than once because of retries, restarts, or multiple workers.

Protect against:

* Sending the same reminder twice
* Creating duplicate rescheduling proposals
* Processing the same overdue task repeatedly
* Generating duplicate forecasts for the same period
* Applying the same approved action twice

Use unique job identifiers and action states such as:

```text
pending
running
completed
failed
cancelled
```

Only one worker should be able to claim a pending action.

---

## Step 20 — Add failure recovery

Define behavior for common failures:

* Notification provider unavailable
* Cloud Ollama timeout
* Invalid LLM command output
* Database temporarily unavailable
* Scheduler restart
* Task changed while a proposal is pending
* User timezone changed
* Reminder execution delayed

Recommended behavior:

```text
Transient failure
→ retry with limits
```

```text
Invalid request or stale proposal
→ mark as failed or expired
```

```text
LLM unavailable
→ keep deterministic reminders, detection, and forecasting operational
```

Automation should not depend entirely on the cloud model.

---

## Step 21 — Add Phase 3 APIs

Create APIs for:

### Reminders

```text
Create reminder
List reminders
Update reminder
Disable reminder
Delete reminder
View notification history
```

### Automation

```text
Run overdue-task detection
Generate rescheduling proposal
View pending proposals
Approve proposal
Reject proposal
View automation history
```

### Forecasts

```text
Generate weekly forecast
Get current forecast
Get forecast history
```

### Commands

```text
Submit natural-language command
Confirm pending command
Reject pending command
View command history
```

These APIs should use existing authentication and ownership checks.

---

## Step 22 — Add frontend interfaces

Phase 3 requires five main frontend areas.

### Reminder settings

The user configures:

* Reminder times
* Channels
* Quiet hours
* Enabled reminder types

### Automation inbox

Display pending actions such as:

* Rescheduling proposals
* Workload reduction suggestions
* Persistent procrastination warnings
* Confirmation requests

### Forecast panel

Display:

* Completion probability
* Risk level
* Required daily effort
* Main risk factors
* Recommended changes

### Natural-language command box

Allow users to enter commands and review parsed actions before approval.

### Automation history

Show:

* What happened
* Why it happened
* Whether it was automatic or user-triggered
* Which records changed
* Whether the action succeeded

---

# Recommended implementation order

Follow this order:

1. Define automation permissions and confirmation rules.
2. Add user timezone and automation preferences.
3. Build one notification provider.
4. Add reminder storage and reminder APIs.
5. Add the separate scheduler service.
6. Implement reminder execution and delivery history.
7. Finalize task lifecycle states.
8. Implement overdue-task detection.
9. Implement rescheduling proposals.
10. Add proposal approval and rejection.
11. Implement rule-based procrastination detection.
12. Add intervention recommendations.
13. Implement deterministic completion forecasting.
14. Store forecast history and outcomes.
15. Add natural-language intent classification.
16. Map intents to existing application services.
17. Add confirmation for command-based changes.
18. Introduce the coordinator workflow.
19. Add automation audit logging.
20. Add idempotency and failure recovery.
21. Add frontend automation screens.
22. Test the complete proactive workflow.

---

# Phase 3 testing requirements

Test each feature independently.

## Reminder tests

Verify:

* Reminder is created correctly.
* Correct timezone conversion is used.
* Completed-task reminders are skipped.
* Quiet hours are respected.
* Duplicate notifications are prevented.
* Failed deliveries are recorded.

## Rescheduling tests

Verify:

* High-priority tasks are preserved.
* Deadlines are respected.
* Daily capacity is not exceeded.
* Phase 2 workload adjustment is applied.
* Repeatedly deferred tasks are escalated.
* Rejected proposals do not modify tasks.
* Approved proposals are applied once.

## Procrastination tests

Verify:

* One missed task does not automatically produce a high-severity event.
* Repeated deferral is detected.
* Low completion rate is detected.
* Evidence is recorded.
* Duplicate events are avoided.

## Forecast tests

Verify:

* Remaining work and time are calculated correctly.
* Probability remains between 0 and 100%.
* Risk increases when deadlines approach.
* Risk decreases after task completion.
* Forecast history is preserved.

## Command tests

Verify:

* Intents are identified correctly.
* Parameters are validated.
* Read-only commands execute directly.
* Write commands require confirmation.
* Users cannot modify another user’s data.
* Invalid LLM output cannot call arbitrary services.

## Scheduler tests

Verify:

* Jobs execute once.
* Failed jobs retry correctly.
* Restarted scheduler recovers pending jobs.
* Concurrent workers do not process the same action twice.

---

# Features to leave for Phase 4

Do not add these yet:

* Separate specialized agents
* Agent-to-agent communication
* Long-term semantic memory
* pgvector retrieval
* Calendar synchronization
* Predictive habit modeling
* Learned forecasting models
* Wearable-device data
* Autonomous long-term goal modification
* Complex workflow infrastructure such as Temporal

Phase 3 should make the current application proactive without making it fully autonomous.

---

# Phase 3 completion checklist

Phase 3 is complete when this workflow functions:

```text
1. User defines reminder and automation preferences.
2. Scheduler runs independently from FastAPI.
3. Morning and task reminders are sent at the correct local time.
4. Missed tasks are detected automatically.
5. The system proposes realistic rescheduling changes.
6. Sensitive changes require user approval.
7. Repeated avoidance patterns generate procrastination events.
8. The system recommends specific interventions.
9. Weekly-goal completion probability is calculated and stored.
10. Forecasts update when behavior or plans change.
11. Natural-language commands are converted into validated tool calls.
12. Write operations require confirmation.
13. Every automated action has an audit record.
14. Duplicate scheduled actions are prevented.
15. Core automation continues working when cloud Ollama is unavailable.
16. The frontend displays reminders, proposals, forecasts, and automation history.
17. All Phase 1, Phase 2, and Phase 3 tests pass.
```

The final Phase 3 system should operate as:

```text
Plan
→ observe execution
→ detect risk
→ forecast outcome
→ propose intervention
→ receive approval
→ adjust plan
→ notify user
→ record result
```

# Scheduler setup: django-q2 background jobs

This covers turning on the background jobs that depend on django-q2. Right
now that means:

- `cycles.task_status_engine.run_scheduled_maintenance`, which runs daily
  for task activation and overdue state updates.
- `notifications.tasks.check_notifications`, which runs every 5 minutes for
  reminders and overdue emails.

Everything below the code is already done, this file is only about the last
step, getting a worker to actually run them.

## Local testing (before production)

Safe to turn on and off freely on your own machine, it's just a local
process reading your own database, nothing about starting or stopping it
can corrupt anything.

**Terminal 1** (your normal server): `python manage.py runserver`

**Terminal 2**, once, then start the worker:
```
python manage.py setup_scheduled_jobs
python manage.py setup_notification_schedule
python manage.py qcluster
```
Leave that terminal open while doing manual/frontend testing. When done,
`Ctrl+C` or close the terminal, that's the entire shutdown, no service to
stop, no config to revert.

**Two things worth knowing before you start it, not harm, but real
effects:**

1. Since no explicit `next_run` is set, the first execution happens
   almost immediately once `qcluster` picks up the schedule, not 24 hours
   later. Any test task sitting in `pending`/`in_progress` with a past
   `calculated_end_date`, in a `running` cycle, will flip to `overdue`
   within seconds of starting it. That's the feature working, not a bug,
   just don't be surprised mid-demo.
2. The API only allows `overdue -> in_progress/completed/skipped`, never
   back to `pending`. To reset a test task after seeing it go `overdue`,
   use the Django admin or shell, that transition isn't exposed through
   the normal API on purpose.

Confirm it actually fired:
```
python manage.py shell -c "from django_q.models import Success; print(Success.objects.filter(func='cycles.task_status_engine.mark_overdue_tasks').count())"
```
Should show at least 1 once `qcluster` has been running a moment.

## What already exists (no action needed)

- `Q_CLUSTER` is configured in `core/settings.py`, uses the ORM broker, so
  it reuses the existing Postgres connection, no Redis or other broker to
  install.
- `cycles/task_status_engine.mark_overdue_tasks()` is the actual job logic,
  fully tested in `cycles/tests/test_runtime_task_management.py` without
  needing any of this running.
- `python manage.py mark_overdue_tasks` runs it once by hand, any time.
- `python manage.py setup_scheduled_jobs` registers it with django-q2's
  scheduler to repeat daily. Safe to run more than once.
- `notifications.tasks.check_notifications()` is the notification scan,
  fully tested in `notifications/tests.py`, and persists delivery state so
  five-minute scans do not duplicate emails.
- `python manage.py setup_notification_schedule` registers the notification
  schedule to repeat every 5 minutes. Safe to run more than once.

## What's still missing, and why it's not code

A registered schedule does nothing by itself. django-q2 needs a worker
process, `python manage.py qcluster`, running **continuously** to actually
check the schedule and execute due jobs. Nothing in this repo starts that
process for you, on purpose, because how you keep a process alive forever
is a hosting decision, not an application one, and NFR-6.4 requires this
to work on both Linux and Windows.

## Steps to go live, once hosting is decided

1. Run migrations if not already done, django-q2's own tables come from
   its app migrations, already in `INSTALLED_APPS`.
2. Run once:
   `python manage.py setup_scheduled_jobs`
3. Run once:
   `python manage.py setup_notification_schedule`
4. Get `python manage.py qcluster` running continuously. Pick based on
   the actual server:

   **Linux (systemd)**: create a unit file, e.g.
   `/etc/systemd/system/recurra-qcluster.service`:
   ```ini
   [Unit]
   Description=Recurra django-q2 worker
   After=network.target postgresql.service

   [Service]
   WorkingDirectory=/path/to/backend
   ExecStart=/path/to/.venv/bin/python manage.py qcluster
   Restart=always
   User=www-data

   [Install]
   WantedBy=multi-user.target
   ```
   Then `systemctl enable --now recurra-qcluster`.

   **Windows**: run `python manage.py qcluster` as a Windows Service
   (via `nssm` or Task Scheduler set to run at startup with restart-on-
   failure), or inside whatever container/process manager the Windows
   host already uses for the main app.

5. Confirm it's actually running: check `django_q.models.Success` /
   `Failure` in the admin, or `python manage.py qmonitor` if the monitor
   dependency is installed.

## Verifying it worked

```
python manage.py shell -c "from django_q.models import Schedule; print(Schedule.objects.filter(func='cycles.task_status_engine.mark_overdue_tasks').exists())"
```
Should print `True` after step 2. Actual execution only happens once a
qcluster worker (step 4) is running, the schedule existing is not the
same as it firing.

For notifications:
```
python manage.py shell -c "from django_q.models import Schedule; s=Schedule.objects.get(func='notifications.tasks.check_notifications'); print((s.schedule_type, s.minutes, s.repeats))"
```
Should print something equivalent to `('I', 5, -1)` after step 3. Actual
email delivery still requires the `qcluster` worker from step 4 to be
running continuously.

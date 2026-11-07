import calendar
import csv
import json
from datetime import date, datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import SubjectForm, TimeEntryForm, TimerStartForm
from .models import Subject, TimeEntry


ACTIVITIES = [choice.value for choice in TimeEntry.Activity]
ACTIVITY_COLORS = {"class": "#3563e9", "notes": "#8b5cf6", "free": "#f59e0b", "other": "#64748b"}


def duration(seconds):
    seconds = int(seconds or 0)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def display_entry(entry):
    entry.duration_display = duration(entry.duration_seconds)
    return entry


def completed_for_dates(user, start, end):
    return TimeEntry.objects.filter(user=user, end_datetime__isnull=False, start_datetime__date__gte=start, start_datetime__date__lte=end).select_related("subject")


def metric_data(entries):
    totals = {key: 0 for key in ACTIVITIES}
    for row in entries.values("activity").annotate(seconds=Sum("duration_seconds")):
        totals[row["activity"]] = row["seconds"] or 0
    study = totals["class"] + totals["notes"]
    return {
        "study": study, "class": totals["class"], "notes": totals["notes"], "free": totals["free"], "other": totals["other"],
        "sessions": entries.count(), "cards": [
            ("Total study", duration(study), "bi-book", "primary"), ("Class", duration(totals["class"]), "bi-headphones", "class"),
            ("Notes", duration(totals["notes"]), "bi-pencil-square", "notes"), ("Practice time", duration(totals["free"]), "bi-cup-hot", "free"),
            ("Other", duration(totals["other"]), "bi-grid", "other"), ("Sessions", str(entries.count()), "bi-collection", "slate"),
        ],
    }


def parse_date(value, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else default
    except ValueError:
        return default


@login_required
def dashboard(request):
    today = timezone.localdate()
    selected = parse_date(request.GET.get("date"), today)
    entries = completed_for_dates(request.user, selected, selected)
    subjects = list(Subject.objects.filter(user=request.user))
    class_totals = {row["subject_id"]: row["seconds"] or 0 for row in entries.filter(activity="class").values("subject_id").annotate(seconds=Sum("duration_seconds"))}
    for subject in subjects:
        subject.total_display = duration(class_totals.get(subject.id, 0))
    dates = list(TimeEntry.objects.filter(user=request.user, end_datetime__isnull=False).dates("start_datetime", "day", order="DESC"))
    if today not in dates:
        dates.insert(0, today)
    metrics = metric_data(entries)
    context = {
        "selected_date": selected, "available_dates": dates, "entries": [display_entry(e) for e in entries], "subjects": subjects, "metrics": metrics,
        "chart_labels": json.dumps([s.name for s in subjects]), "chart_values": json.dumps([round(class_totals.get(s.id, 0) / 3600, 2) for s in subjects]),
        "chart_colors": json.dumps([s.color for s in subjects]), "distribution": json.dumps([round(metrics[key] / 3600, 2) for key in ("class", "notes", "free", "other")]),
    }
    return render(request, "tracker/dashboard.html", context)


@login_required
def timer(request):
    active = TimeEntry.objects.filter(user=request.user, end_datetime__isnull=True).select_related("subject").first()
    form = TimerStartForm(request.POST or None, user=request.user)
    if request.method == "POST":
        if active:
            messages.error(request, "A timer is already running. Stop it before starting another.")
        elif form.is_valid():
            with transaction.atomic():
                if TimeEntry.objects.select_for_update().filter(user=request.user, end_datetime__isnull=True).exists():
                    messages.error(request, "A timer is already running. Stop it before starting another.")
                else:
                    TimeEntry.objects.create(user=request.user, subject=form.cleaned_data["subject"], activity=form.cleaned_data["activity"], start_datetime=timezone.now())
                    messages.success(request, "Timer started. Your session is being tracked.")
                    return redirect("timer")
    today_entries = completed_for_dates(request.user, timezone.localdate(), timezone.localdate())
    metrics = metric_data(today_entries)
    latest = [display_entry(e) for e in today_entries[:5]]
    elapsed_seconds = int((timezone.now() - active.start_datetime).total_seconds()) if active else 0
    progress = [("Class", duration(metrics["class"]), "bi-headphones text-primary"), ("Notes", duration(metrics["notes"]), "bi-pencil-square notes-text"), ("Practice time", duration(metrics["free"]), "bi-journal-check free-text"), ("Total study", duration(metrics["study"]), "")]
    return render(request, "tracker/timer.html", {"form": form, "active": active, "elapsed_seconds": elapsed_seconds, "metrics": metrics, "progress": progress, "recent": latest})


@login_required
def stop_timer(request):
    if request.method != "POST":
        return redirect("timer")
    with transaction.atomic():
        active = TimeEntry.objects.select_for_update(of=("self",)).filter(user=request.user, end_datetime__isnull=True).select_related("subject").first()
        if not active:
            messages.error(request, "There is no active timer to stop.")
        else:
            active.end_datetime = timezone.now()
            active.full_clean()
            active.save()
            messages.success(request, f"Session saved — {active.subject or 'No subject'} · {active.get_activity_display()} · {duration(active.duration_seconds)}")
    return redirect("timer")


@login_required
def time_log(request):
    entries = TimeEntry.objects.filter(user=request.user, end_datetime__isnull=False).select_related("subject")
    return render(request, "tracker/time_log.html", {"entries": [display_entry(e) for e in entries]})


@login_required
def export_time_log(request):
    """Provide a portable backup without exposing a separate API."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="studytrack-time-log.csv"'
    writer = csv.writer(response)
    writer.writerow(["Date", "Subject", "Activity", "Start", "End", "Duration", "Notes"])
    entries = TimeEntry.objects.filter(user=request.user, end_datetime__isnull=False).select_related("subject").order_by("-start_datetime")
    for entry in entries:
        writer.writerow([
            timezone.localtime(entry.start_datetime).strftime("%Y-%m-%d"), entry.subject.name if entry.subject else "",
            entry.get_activity_display(), timezone.localtime(entry.start_datetime).strftime("%H:%M"),
            timezone.localtime(entry.end_datetime).strftime("%H:%M"), duration(entry.duration_seconds), entry.notes,
        ])
    return response


def health(request):
    return HttpResponse("OK", content_type="text/plain")


@login_required
def edit_entry(request, pk):
    entry = get_object_or_404(TimeEntry, user=request.user, pk=pk)
    if entry.is_active:
        messages.error(request, "Stop the active timer before editing it.")
        return redirect("timer")
    form = TimeEntryForm(request.POST or None, instance=entry, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Time entry updated and duration recalculated.")
        return redirect("time_log")
    return render(request, "tracker/entry_form.html", {"form": form, "entry": entry})


@login_required
def delete_entry(request, pk):
    entry = get_object_or_404(TimeEntry, user=request.user, pk=pk)
    if request.method == "POST":
        entry.delete()
        messages.success(request, "Time entry deleted.")
        return redirect("time_log")
    return render(request, "tracker/delete_confirm.html", {"entry": display_entry(entry)})


def week_start(value):
    selected = parse_date(value, timezone.localdate())
    return selected - timedelta(days=selected.weekday())


@login_required
def weekly(request):
    start = week_start(request.GET.get("week"))
    end = start + timedelta(days=6)
    entries = completed_for_dates(request.user, start, end)
    subjects = list(Subject.objects.filter(user=request.user))
    matrix = {(row["subject_id"], row["start_datetime__date"]): row["seconds"] or 0 for row in entries.filter(activity="class").values("subject_id", "start_datetime__date").annotate(seconds=Sum("duration_seconds"))}
    days = [start + timedelta(days=n) for n in range(7)]
    rows = []
    for subject in subjects:
        values = [matrix.get((subject.id, day), 0) for day in days]
        rows.append({"subject": subject, "days": [duration(v) for v in values], "total": duration(sum(values)), "seconds": sum(values)})
    daily_class = [sum(matrix.get((s.id, day), 0) for s in subjects) for day in days]
    notes_map = {row["start_datetime__date"]: row["seconds"] or 0 for row in entries.filter(activity="notes").values("start_datetime__date").annotate(seconds=Sum("duration_seconds"))}
    return render(request, "tracker/weekly.html", {
        "start": start, "end": end, "previous": start - timedelta(days=7), "next": start + timedelta(days=7), "days": days, "rows": rows,
        "metrics": metric_data(entries), "total_class": duration(sum(daily_class)), "labels": json.dumps([d.strftime("%a") for d in days]),
        "daily_class": json.dumps([round(v / 3600, 2) for v in daily_class]), "daily_notes": json.dumps([round(notes_map.get(d, 0) / 3600, 2) for d in days]),
        "subject_labels": json.dumps([s.name for s in subjects]), "subject_values": json.dumps([round(r["seconds"] / 3600, 2) for r in rows]), "subject_colors": json.dumps([s.color for s in subjects]),
    })


def month_bounds(value):
    try:
        year, month = [int(n) for n in value.split("-")]
        start = date(year, month, 1)
    except (ValueError, AttributeError):
        today = timezone.localdate()
        start = date(today.year, today.month, 1)
    last = calendar.monthrange(start.year, start.month)[1]
    return start, date(start.year, start.month, last)


@login_required
def monthly(request):
    start, end = month_bounds(request.GET.get("month"))
    entries = completed_for_dates(request.user, start, end)
    subjects = list(Subject.objects.filter(user=request.user))
    sums = {(row["subject_id"], row["activity"]): row["seconds"] or 0 for row in entries.filter(activity__in=["class", "notes"]).values("subject_id", "activity").annotate(seconds=Sum("duration_seconds"))}
    summary = []
    for subject in subjects:
        c, n = sums.get((subject.id, "class"), 0), sums.get((subject.id, "notes"), 0)
        summary.append({"subject": subject, "class": duration(c), "notes": duration(n), "total": duration(c + n), "class_seconds": c})
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    daily = {row["start_datetime__date"]: row["seconds"] or 0 for row in entries.filter(activity="class").values("start_datetime__date").annotate(seconds=Sum("duration_seconds"))}
    previous = (start - timedelta(days=1)).replace(day=1)
    next_month = (end + timedelta(days=1)).replace(day=1)
    return render(request, "tracker/monthly.html", {
        "start": start, "end": end, "previous": previous, "next": next_month, "metrics": metric_data(entries), "summary": summary,
        "labels": json.dumps([str(day.day) for day in days]), "daily": json.dumps([round(daily.get(day, 0) / 3600, 2) for day in days]),
        "subject_labels": json.dumps([s.name for s in subjects]), "subject_values": json.dumps([round(row["class_seconds"] / 3600, 2) for row in summary]), "subject_colors": json.dumps([s.color for s in subjects]),
    })


@login_required
def settings_view(request):
    subjects = list(Subject.objects.filter(user=request.user))
    if request.method == "POST":
        if "add_subject" in request.POST:
            subject_form = SubjectForm(request.POST, user=request.user)
            if subject_form.is_valid():
                subject_form.save()
                messages.success(request, "Subject added.")
                return redirect("settings")
            return render(request, "tracker/settings.html", {"subjects": subjects, "subject_form": subject_form})

        submitted_names = {
            subject.id: request.POST.get(f"name_{subject.id}", "").strip() or subject.name
            for subject in subjects
        }
        normalized_names = [name.casefold() for name in submitted_names.values()]
        if len(normalized_names) != len(set(normalized_names)):
            messages.error(request, "Each subject must have a unique name.")
            return render(request, "tracker/settings.html", {"subjects": subjects, "subject_form": SubjectForm(user=request.user)})
        for subject in subjects:
            name = submitted_names[subject.id]
            color = request.POST.get(f"color_{subject.id}", subject.color)
            subject.name = name or subject.name
            subject.color = color if len(color) == 7 and color.startswith("#") else subject.color
            subject.active = f"active_{subject.id}" in request.POST
            subject.save()
        messages.success(request, "Subject settings saved across StudyTrack.")
        return redirect("settings")
    return render(request, "tracker/settings.html", {"subjects": subjects, "subject_form": SubjectForm(user=request.user)})


@login_required
@require_POST
def delete_subject(request, pk):
    subject = get_object_or_404(Subject, user=request.user, pk=pk)
    try:
        subject.delete()
    except ProtectedError:
        messages.error(request, f"{subject.name} has saved sessions and cannot be deleted. Deactivate it to keep its history.")
    else:
        messages.success(request, f"{subject.name} deleted.")
    return redirect("settings")

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"), path("timer/", views.timer, name="timer"),
    path("timer/stop/", views.stop_timer, name="stop_timer"), path("log/", views.time_log, name="time_log"),
    path("log/export/", views.export_time_log, name="export_time_log"),
    path("log/<int:pk>/edit/", views.edit_entry, name="edit_entry"), path("log/<int:pk>/delete/", views.delete_entry, name="delete_entry"),
    path("weekly/", views.weekly, name="weekly"), path("monthly/", views.monthly, name="monthly"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/subjects/<int:pk>/delete/", views.delete_subject, name="delete_subject"),
]

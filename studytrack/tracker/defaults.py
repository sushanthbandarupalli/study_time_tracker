from .models import Subject


SUBJECT_COLORS = [
    "#3563e9", "#7c4dff", "#16a56b", "#e67e22", "#e55252", "#0f9ca6",
    "#a855f7", "#d97706", "#db2777", "#4f7dff", "#64748b",
]


def create_default_subjects(user):
    for number, color in enumerate(SUBJECT_COLORS, 1):
        Subject.objects.get_or_create(
            user=user,
            name=f"Subject {number}",
            defaults={"color": color},
        )

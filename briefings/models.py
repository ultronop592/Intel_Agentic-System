from django.db import models

from competitors.models import Competitor, CompetitorSnapshot


class Briefing(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    )

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE, related_name="briefings")
    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name="briefings")
    snapshot = models.ForeignKey(CompetitorSnapshot, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    changes_detected = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.competitor.name} briefing {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def word_count(self) -> int:
        return len(self.content.split())

    @property
    def preview(self) -> str:
        return self.content[:250]

    @property
    def changes_detected_count(self) -> int:
        return len(
            [
                line
                for line in self.changes_detected.splitlines()
                if line.startswith("+") or line.startswith("-")
            ]
        )

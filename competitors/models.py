import hashlib

from django.contrib.auth.models import User
from django.db import models


class Competitor(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="competitors")
    name = models.CharField(max_length=100)
    url = models.URLField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_scraped = models.DateTimeField(null=True, blank=True)
    last_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    current_task_id = models.CharField(max_length=255, blank=True)
    current_task_started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "url")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.name


class CompetitorSnapshot(models.Model):
    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name="snapshots")
    raw_text = models.TextField()
    content_hash = models.CharField(max_length=64)
    screenshot = models.ImageField(upload_to="screenshots/", blank=True, null=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-scraped_at",)

    def __str__(self) -> str:
        return f"{self.competitor.name} snapshot {self.scraped_at:%Y-%m-%d %H:%M}"

    @property
    def is_duplicate(self) -> bool:
        previous_snapshot = (
            self.competitor.snapshots.exclude(pk=self.pk).only("content_hash").order_by("-scraped_at").first()
        )
        return bool(previous_snapshot and previous_snapshot.content_hash == self.content_hash)

    @staticmethod
    def generate_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DiscoveredPage(models.Model):
    PAGE_TYPE_CHOICES = (
        ("pricing", "Pricing"),
        ("features", "Features"),
        ("blog", "Blog"),
        ("about", "About"),
        ("careers", "Careers"),
        ("product", "Product"),
        ("other", "Other"),
    )

    competitor = models.ForeignKey(Competitor, on_delete=models.CASCADE, related_name="discovered_pages")
    url = models.URLField()
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, default="other")
    is_tracked = models.BooleanField(default=False)
    discovered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("competitor", "url")
        ordering = ("-discovered_at",)

    def __str__(self) -> str:
        return f"{self.competitor.name} - {self.page_type}: {self.url}"

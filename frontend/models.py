from django.db import models

class ContactInquiry(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField()
    institution = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact Inquiry"
        verbose_name_plural = "Contact Inquiries"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.institution}"

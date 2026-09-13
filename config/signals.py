from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import Book, BookStatusEvent

@receiver(pre_save, sender=Book)
def remember_status(sender, instance, **kwargs):
    instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None

@receiver(post_save, sender=Book)
def record_status(sender, instance, created, **kwargs):
    if not created and getattr(instance, '_previous_status', instance.status) != instance.status:
        BookStatusEvent.objects.create(book=instance, status=instance.status)


from .models import BookPageAnswer, PageVersion

@receiver(pre_save, sender=BookPageAnswer)
def remember_page_text(sender, instance, **kwargs):
    instance._old_text = sender.objects.filter(pk=instance.pk).values_list('answer', flat=True).first() if instance.pk else None

@receiver(post_save, sender=BookPageAnswer)
def save_page_version(sender, instance, created, **kwargs):
    old = getattr(instance, '_old_text', None)
    if old is not None and old != instance.answer:
        if not instance.versions.exists():
            PageVersion.objects.create(page=instance, text=old)
        PageVersion.objects.create(page=instance, text=instance.answer)
    elif created:
        PageVersion.objects.create(page=instance, text=instance.answer)

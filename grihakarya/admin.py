from django.contrib import admin

from .models import HomeworkEntry, HomeworkTemplate, HomeworkComplain


def _register(model, admin_class):
    try:
        admin.site.register(model, admin_class)
    except admin.sites.AlreadyRegistered:
        pass


class HomeworkEntryAdmin(admin.ModelAdmin):
    list_display = ('homework', 'subject', 'homework_text')
    list_select_related = ('homework', 'subject')
    search_fields = ('homework_text', 'subject__subject')


class HomeworkTemplateAdmin(admin.ModelAdmin):
    list_display = ('grade', 'subject', 'template_text')
    list_select_related = ('grade', 'subject')
    search_fields = ('template_text', 'subject__subject', 'grade__grade_name')


class HomeworkComplainAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'grade', 'section', 'subject', 'status', 'created_at')
    list_select_related = ('teacher', 'grade', 'section', 'subject')
    list_filter = ('status', 'grade')
    search_fields = ('complaint_text', 'admin_response', 'teacher__username')
    readonly_fields = ('created_at', 'updated_at')


_register(HomeworkEntry, HomeworkEntryAdmin)
_register(HomeworkTemplate, HomeworkTemplateAdmin)
_register(HomeworkComplain, HomeworkComplainAdmin)

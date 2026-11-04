from django.contrib import admin

from .models import (
    Remark,
    RemarkEditLog,
    Concern,
    CommunicationLog,
    RemarkTemplate,
    GuardianToken,
)


class RemarkEditLogInline(admin.TabularInline):
    model = RemarkEditLog
    extra = 0
    readonly_fields = ('changed_by', 'field', 'old_value', 'new_value', 'changed_at')
    can_delete = False
    max_num = 0


class CommunicationLogInline(admin.TabularInline):
    model = CommunicationLog
    extra = 0
    readonly_fields = ('created_at',)


# panel/admin.py bulk-registers all models with a default ModelAdmin.
# Unregister so we can re-register with our custom admin classes.
for _m in [Remark, RemarkEditLog, Concern, CommunicationLog, RemarkTemplate, GuardianToken]:
    try:
        admin.site.unregister(_m)
    except admin.NotRegistered:
        pass


@admin.register(Remark)
class RemarkAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'reason', 'severity', 'visibility',
                    'status', 'active', 'teacher', 'remark_date', 'school')
    list_filter = ('category', 'severity', 'visibility', 'status', 'active',
                   'school', 'remark_date')
    search_fields = ('student__name', 'student__reg_no', 'reason', 'note',
                     'teacher__username', 'teacher__first_name')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [RemarkEditLogInline]
    actions = ['escalate_selected', 'dismiss_selected']

    @admin.action(description='Escalate selected remarks')
    def escalate_selected(self, request, queryset):
        updated = queryset.filter(active=True).update(status='escalated')
        self.message_user(request, f'{updated} remark(s) escalated.')

    @admin.action(description='Dismiss selected remarks')
    def dismiss_selected(self, request, queryset):
        updated = queryset.filter(active=True).update(status='dismissed')
        self.message_user(request, f'{updated} remark(s) dismissed.')


@admin.register(Concern)
class ConcernAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'category', 'status', 'assigned_to',
                    'source_remark', 'school', 'created_at')
    list_filter = ('status', 'category', 'school', 'created_at')
    search_fields = ('student__name', 'student__reg_no', 'title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('student', 'source_remark', 'assigned_to', 'created_by')
    inlines = [CommunicationLogInline]


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ('concern', 'direction', 'channel', 'author', 'created_at')
    list_filter = ('direction', 'channel', 'created_at')
    search_fields = ('message', 'concern__title', 'concern__student__name')
    readonly_fields = ('created_at',)


@admin.register(RemarkTemplate)
class RemarkTemplateAdmin(admin.ModelAdmin):
    list_display = ('school', 'category', 'text', 'sort_order', 'active')
    list_filter = ('category', 'active', 'school')
    search_fields = ('text',)
    ordering = ('school', 'category', 'sort_order')


@admin.register(RemarkEditLog)
class RemarkEditLogAdmin(admin.ModelAdmin):
    list_display = ('remark', 'changed_by', 'field', 'changed_at')
    list_filter = ('field', 'changed_at')
    readonly_fields = ('remark', 'changed_by', 'field', 'old_value', 'new_value', 'changed_at')
    can_delete = False


admin.site.register(GuardianToken)

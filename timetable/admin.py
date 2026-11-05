from django.contrib import admin

from .models import (
    ScheduleProfile,
    ScheduleProfilePeriod,
    TimetableEntry,
    TimetableException,
    TimetableVersion,
)

# panel/admin.py bulk-registers every model — unregister timetable models so
# we can re-register them with proper admin classes.
for _m in [ScheduleProfile, ScheduleProfilePeriod, TimetableVersion,
           TimetableEntry, TimetableException]:
    try:
        admin.site.unregister(_m)
    except admin.NotRegistered:
        pass


class ScheduleProfilePeriodInline(admin.TabularInline):
    model  = ScheduleProfilePeriod
    extra  = 0
    fields = ('sequence', 'shift', 'period_type', 'label', 'start_time', 'end_time')
    ordering = ('sequence',)


@admin.register(ScheduleProfile)
class ScheduleProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'name', 'is_active')
    list_filter  = ('is_active', 'school')
    search_fields = ('name',)
    inlines      = [ScheduleProfilePeriodInline]


@admin.register(TimetableVersion)
class TimetableVersionAdmin(admin.ModelAdmin):
    list_display  = ('id', 'school', 'academic_year', 'version_no',
                     'effective_from', 'status', 'published_at', 'archived_at')
    list_filter   = ('status', 'school', 'academic_year')
    search_fields = ('change_note',)
    readonly_fields = ('created_at', 'effective_from_ad')
    # No updated_at — versions are immutable (invariant #1)


class TimetableEntryAdmin(admin.ModelAdmin):
    list_display  = ('id', 'version', 'section', 'subject', 'teacher',
                     'period', 'period_span', 'recurrence', 'entry_type', 'archived_at')
    list_filter   = ('recurrence', 'entry_type', 'version__status')
    search_fields = ('version__id',)
    readonly_fields = ('created_at', 'specific_date_ad', 'valid_from_ad', 'valid_to_ad')

    def save_model(self, request, obj, form, change):
        from .validators import validate_entry_raise
        validate_entry_raise(obj)
        super().save_model(request, obj, form, change)

admin.site.register(TimetableEntry, TimetableEntryAdmin)


@admin.register(TimetableException)
class TimetableExceptionAdmin(admin.ModelAdmin):
    list_display  = ('id', 'school', 'academic_year', 'date_from', 'date_to',
                     'kind', 'scope', 'scope_id', 'created_by', 'locked_at')
    list_filter   = ('kind', 'scope', 'school', 'academic_year')
    search_fields = ('reason',)
    readonly_fields = ('created_at', 'date_from_ad', 'date_to_ad')

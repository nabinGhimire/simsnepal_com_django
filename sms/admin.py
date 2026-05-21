from django.contrib import admin
from .models import (
    EduSession, SuperBranchUser, SchoolBranch, GradeLevel, SchoolGrade,
    Section, SubjectMaster, Subject, BranchUser, SchoolTermStatus,
    SchoolTerm, ResultManagement, WeightedResultManagement, House
)

@admin.register(EduSession)
class EduSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'year', 'status')
    list_filter = ('status',)
    search_fields = ('year',)

@admin.register(SuperBranchUser)
class SuperBranchUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'range_start', 'range_end')
    search_fields = ('user__username', 'user__email')

@admin.register(SchoolBranch)
class SchoolBranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'phone', 'email', 'status', 'is_branch')
    list_filter = ('status', 'is_branch')
    search_fields = ('name', 'location', 'shortcode')

@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

@admin.register(SchoolGrade)
class SchoolGradeAdmin(admin.ModelAdmin):
    list_display = ('id', 'grade_name', 'school', 'level', 'session', 'active', 'grade_weight')
    list_filter = ('active', 'session', 'level', 'school')
    search_fields = ('grade_name',)

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'section', 'grade', 'session')
    list_filter = ('session', 'grade')
    search_fields = ('section',)

@admin.register(SubjectMaster)
class SubjectMasterAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'canonical_name', 'description')
    search_fields = ('code', 'canonical_name', 'description')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'subject_master', 'grade', 'section', 'session', 'branch', 'status')
    list_filter = ('status', 'session', 'branch', 'grade')
    search_fields = ('subject', 'subject_master__canonical_name')

@admin.register(BranchUser)
class BranchUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'school', 'admin_status', 'status')
    list_filter = ('admin_status', 'status', 'school')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')

@admin.register(SchoolTermStatus)
class SchoolTermStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'value')

@admin.register(SchoolTerm)
class SchoolTermAdmin(admin.ModelAdmin):
    list_display = ('id', 'term_name', 'school', 'year', 'active', 'final_term')
    list_filter = ('active', 'final_term', 'year', 'school')
    search_fields = ('term_name',)

@admin.register(ResultManagement)
class ResultManagementAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'year', 'school_term')
    list_filter = ('year', 'school')

@admin.register(WeightedResultManagement)
class WeightedResultManagementAdmin(admin.ModelAdmin):
    list_display = ('id', 'school', 'year', 'school_term')
    list_filter = ('year', 'school')

@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'school')
    list_filter = ('school',)
    search_fields = ('name',)

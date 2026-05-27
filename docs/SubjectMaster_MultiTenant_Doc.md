# Multi‑Tenant Data Isolation with `SchoolScopedManager`

## Overview
The application is a **SaaS** platform where **each school** is a separate tenant.  All data that belongs to a school must be isolated so that an administrator of one school cannot see or modify another school's records.

## Core Concept
1. **Session‑based school identification**
   - When a user logs in, the middleware stores the school shortcode in the session under `request.session['sso_business']['id']`.
   - Helper `sms.utils.get_current_school()` (or the internal `get_current_request()` call) reads this value.
2. **`SchoolScopedManager`**
   - A custom Django manager that automatically adds `school__shortcode = <current‑school‑id>` to every queryset.
   - Implemented in `sms/models.py`:
   ```python
   class SchoolScopedQuerySet(models.QuerySet):
       def filter(self, *args, **kwargs):
           qs = super().filter(*args, **kwargs)
           request = get_current_request()
           if request and request.session:
               business_id = request.session.get('sso_business', {}).get('id')
               if business_id:
                   qs = qs.filter(school__shortcode=business_id)
           return qs

   class SchoolScopedManager(models.Manager):
       def get_queryset(self):
           return SchoolScopedQuerySet(self.model, using=self._db)
   ```
   - Every model that includes `objects = SchoolScopedManager()` inherits this behaviour.
3. **Model‑level scoping**
   - `Section`, `SubjectMaster`, `Subject`, `Student`, etc., all declare `objects = SchoolScopedManager()`.
   - The `school` foreign‑key may be nullable for legacy data, but the manager still guarantees that **only rows belonging to the current school are ever returned**.

## Why `SubjectMaster` Is Already Scoped
`SubjectMaster` stores the catalogue of subjects (code, canonical name, description) that a school can use.  Without automatic scoping, a query such as:
```python
SubjectMaster.objects.get(id=subject_master_id)
```
could inadvertently retrieve a subject belonging to a different school, leaking data.
By attaching the manager, the same call becomes:
```python
# Implicitly filtered by the current school
subject = SubjectMaster.objects.get(id=subject_master_id)
```
No extra `school=` filter is required, and the code remains clean.

## Practical Usage Patterns
### 1. Simple Retrieval (already scoped)
```python
# In a view – current user belongs to school X
sm = SubjectMaster.objects.get(id=pk)  # Returns only if the subject belongs to X
```
### 2. Filtering a List
```python
# List all subjects for the current school
subject_list = SubjectMaster.objects.all()
```
### 3. Creating a New Record
```python
# The manager does not automatically set the FK, so we still need to assign it.
new_subject = SubjectMaster.objects.create(
    school=request.branchuser.school,  # explicit FK for the new row
    code='ENG101',
    canonical_name='English Basics',
    description='Introductory English course'
)
```
### 4. Legacy Queries (remove manual `school=`)
Before the manager:
```python
SubjectMaster.objects.filter(school=branchuser.school, code='MTH')
```
After the manager (simpler):
```python
SubjectMaster.objects.filter(code='MTH')
```
The manager injects the school filter automatically.

## Best Practices
| Situation | Recommendation |
|-----------|----------------|
| **Direct foreign‑key access** (`subject_master.school`) | Keep the explicit `school` assignment when **creating** a new instance. |
| **Complex joins** (`select_related`, `prefetch_related`) | Use them as normal; the manager’s filter runs first, then the joins are applied. |
| **Raw SQL** (`raw()`, `extra()`) | Manually add `WHERE school_id = %s` using the session value – the manager cannot intervene. |
| **Testing** | Override the session in your test client (`client.session['sso_business']['id'] = <shortcode>`) to simulate different schools. |

## How It Interacts with Views
In `panel/views.py` (excerpt from lines 355‑374):
```python
branchuser, error = get_branch_info(user)
# …
gradelevel = SchoolGrade.objects.get(id=int(gradelevel))
subjects = Subject.objects.filter(branch=branchuser.school, grade=gradelevel.id)
students = Student.objects.filter(school=branchuser.school, grade=gradelevel.id)
```
- `Subject` and `Student` already have the manager, so the explicit `school=` filter is **redundant** – it can be removed for brevity.
- The same applies to `Section` (line 371) and, importantly, to `SubjectMaster` in the `addsubject` view (line 477).

## Migration Checklist
1. **Add `objects = SchoolScopedManager()`** to each tenant‑specific model (already done for `SubjectMaster`).
2. **Run migrations** to add the `school` foreign‑key where missing (already applied).
3. **Search for manual `school=` filters** in the codebase and replace them where the manager is present.
4. **Review raw SQL** for missing school constraints.
5. **Update tests** to cover multi‑tenant isolation.

---
### TL;DR
- The manager reads the current school from the session and automatically filters all queries.
- `SubjectMaster` now safely returns only subjects belonging to the logged‑in school.
- Remove explicit `school=` filters in ORM queries; keep them only when **creating** new rows.
- Follow the best‑practice table to avoid pitfalls.

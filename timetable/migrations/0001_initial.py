"""
Timetable module — single clean initial migration.

Creates all 5 tables with the correct schema in one pass:

  1. timetable_schedule_profile
  2. timetable_schedule_profile_period
  3. timetable_version
  4. timetable_entry
  5. timetable_exception

Key design points (see .kilo/plans/timetable.md):
──────────────────────────────────────────────────
BS dates:
  Stored as VARCHAR(10) 'YYYY-MM-DD'. AD shadow columns are DB-generated
  (STORED GENERATED on MySQL, trigger-managed on SQLite). They are declared
  in Django state as DateField(editable=False) so the ORM can read them but
  never writes them.

  The AD formula used in DB triggers/generated cols:
    AD year ≈ BS year - 57  (same month/day)
  Accurate for index range purposes; authoritative conversion is always done
  by the nepali_datetime library at application level.

Generated columns (MySQL):
  CREATE TABLE already includes the GENERATED ALWAYS AS expression via
  RunSQL for these columns. On SQLite, AFTER INSERT/UPDATE triggers are
  created by RunPython.

days_of_week bitmask:
  Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64  (SMALLINT)

Indexes:
  tt_version_school_year_eff_idx  — (school_id, academic_year_id, effective_from DESC)
  tt_entry_version_section_idx    — (version_id, section_id)          covers FK
  tt_entry_teacher_idx            — (teacher_id)
  tt_entry_specific_date_idx      — (specific_date_ad) partial on SQLite
  tt_exc_school_date_from_idx     — (school_id, date_from_ad)
  tt_exc_school_year_idx          — (school_id, academic_year_id)
  tt_exc_teacher_idx              — (teacher_id)

Invariants never violated:
  • No updated_at on timetable_version (append-only, invariant #1)
  • No hard deletes — archived_at / locked_at on relevant tables
  • created_by on timetable_exception is NOT NULL (mandatory audit, invariant #6)
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# ── DB vendor helpers ─────────────────────────────────────────────────────────

def _mysql(se):  return se.connection.vendor == "mysql"
def _sqlite(se): return se.connection.vendor == "sqlite"


# ── Generated AD column enforcement ──────────────────────────────────────────
#
# On MySQL: ALTER the just-created nullable DATE column to STORED GENERATED.
# On SQLite: install AFTER INSERT / AFTER UPDATE triggers.
#
# %% escapes literal % in strings passed to schema_editor.execute() so
# MySQLdb does not interpret them as parameter placeholders.

def _sqlite_trigger_ins(table, bs_col, ad_col):
    return (
        f"CREATE TRIGGER IF NOT EXISTS trg_{table}_{ad_col}_ins "
        f"AFTER INSERT ON {table} FOR EACH ROW "
        f"WHEN NEW.{bs_col} IS NOT NULL BEGIN "
        f"  UPDATE {table} SET {ad_col} = date("
        f"    (CAST(SUBSTR(NEW.{bs_col},1,4) AS INTEGER)-57)"
        f"    || SUBSTR(NEW.{bs_col},5)"
        f"  ) WHERE id = NEW.id; "
        f"END"
    )

def _sqlite_trigger_upd(table, bs_col, ad_col):
    return (
        f"CREATE TRIGGER IF NOT EXISTS trg_{table}_{ad_col}_upd "
        f"AFTER UPDATE OF {bs_col} ON {table} FOR EACH ROW "
        f"WHEN NEW.{bs_col} IS NOT NULL BEGIN "
        f"  UPDATE {table} SET {ad_col} = date("
        f"    (CAST(SUBSTR(NEW.{bs_col},1,4) AS INTEGER)-57)"
        f"    || SUBSTR(NEW.{bs_col},5)"
        f"  ) WHERE id = NEW.id; "
        f"END"
    )

# (table, bs_col, ad_col, nullable_source) for every generated shadow
# nullable_source=True  → GENERATED column is NULL when bs_col IS NULL
# nullable_source=False → GENERATED column is NOT NULL (bs_col is always set)
_GENERATED = [
    ("timetable_version",   "effective_from", "effective_from_ad", False),
    ("timetable_entry",     "specific_date",  "specific_date_ad",  True),   # nullable
    ("timetable_entry",     "valid_from",      "valid_from_ad",     True),   # nullable
    ("timetable_entry",     "valid_to",        "valid_to_ad",       True),   # nullable
    ("timetable_exception", "date_from",       "date_from_ad",      False),
    ("timetable_exception", "date_to",         "date_to_ad",        False),
]

def fwd_generated(apps, se):
    for table, bs_col, ad_col, nullable in _GENERATED:
        nullability = "NULL" if nullable else "NOT NULL"
        if _mysql(se):
            se.execute(
                f"ALTER TABLE {table} MODIFY COLUMN {ad_col} DATE "
                f"GENERATED ALWAYS AS (STR_TO_DATE(CONCAT(CAST(SUBSTRING({bs_col},1,4) AS UNSIGNED)-57,SUBSTRING({bs_col},5)),'%%Y-%%m-%%d')) "
                f"STORED {nullability} "
                f"COMMENT 'Generated shadow of {bs_col}'"
            )
        elif _sqlite(se):
            se.execute(_sqlite_trigger_ins(table, bs_col, ad_col))
            se.execute(_sqlite_trigger_upd(table, bs_col, ad_col))

def rev_generated(apps, se):
    for table, bs_col, ad_col, nullable in _GENERATED:
        if _mysql(se):
            se.execute(
                f"ALTER TABLE {table} "
                f"MODIFY COLUMN {ad_col} DATE NULL "
                f"COMMENT 'Reverted from generated'"
            )
        elif _sqlite(se):
            se.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{ad_col}_ins")
            se.execute(f"DROP TRIGGER IF EXISTS trg_{table}_{ad_col}_upd")


# ── Indexes that need DESC or partial WHERE (not expressible in Django Index) ─

def fwd_custom_indexes(apps, se):
    # (school_id ASC, academic_year_id ASC, effective_from DESC)
    # Resolver: "latest published version with effective_from <= target_date"
    if _mysql(se):
        se.execute(
            "CREATE INDEX tt_version_school_year_eff_idx "
            "ON timetable_version "
            "(school_id ASC, academic_year_id ASC, effective_from DESC)"
        )
    else:
        se.execute(
            "CREATE INDEX IF NOT EXISTS tt_version_school_year_eff_idx "
            "ON timetable_version "
            "(school_id ASC, academic_year_id ASC, effective_from DESC)"
        )

    # Partial index on specific_date_ad: SQLite supports WHERE, MySQL does not
    if _sqlite(se):
        se.execute(
            "CREATE INDEX IF NOT EXISTS tt_entry_specific_date_idx "
            "ON timetable_entry (specific_date_ad) "
            "WHERE specific_date IS NOT NULL"
        )
    elif _mysql(se):
        se.execute(
            "CREATE INDEX tt_entry_specific_date_idx "
            "ON timetable_entry (specific_date_ad)"
        )

def rev_custom_indexes(apps, se):
    if _mysql(se):
        se.execute(
            "ALTER TABLE timetable_version "
            "DROP INDEX tt_version_school_year_eff_idx"
        )
        se.execute(
            "ALTER TABLE timetable_entry "
            "DROP INDEX tt_entry_specific_date_idx"
        )
    else:
        se.execute("DROP INDEX IF EXISTS tt_version_school_year_eff_idx")
        se.execute("DROP INDEX IF EXISTS tt_entry_specific_date_idx")


# ══════════════════════════════════════════════════════════════════════════════
# Migration
# ══════════════════════════════════════════════════════════════════════════════

class Migration(migrations.Migration):

    # DDL (STORED GENERATED columns, triggers, CREATE INDEX) cannot run
    # inside a transaction on databases that don't support transactional DDL.
    atomic = False

    initial = True

    dependencies = [
        ("sms", "0031_homework_due_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [

        # ── 1. ScheduleProfile ────────────────────────────────────────────────
        migrations.CreateModel(
            name="ScheduleProfile",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("school", models.ForeignKey(
                    db_column="school_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="schedule_profiles",
                    to="sms.schoolbranch",
                )),
                ("name",      models.CharField(max_length=120)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={"db_table": "timetable_schedule_profile"},
        ),
        migrations.AddIndex(
            model_name="ScheduleProfile",
            index=models.Index(fields=["school"], name="tt_sprofile_school_idx"),
        ),

        # ── 2. ScheduleProfilePeriod ──────────────────────────────────────────
        migrations.CreateModel(
            name="ScheduleProfilePeriod",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("profile", models.ForeignKey(
                    db_column="profile_id",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="periods",
                    to="timetable.scheduleprofile",
                )),
                ("sequence",    models.PositiveSmallIntegerField()),
                ("shift",       models.CharField(max_length=10, choices=[
                    ("morning","Morning"), ("day","Day"), ("evening","Evening")])),
                ("start_time",  models.TimeField()),
                ("end_time",    models.TimeField()),
                ("period_type", models.CharField(max_length=10, choices=[
                    ("class","Class"), ("break","Break"),
                    ("assembly","Assembly"), ("lunch","Lunch")])),
                ("label",       models.CharField(max_length=60, blank=True)),
            ],
            options={
                "db_table": "timetable_schedule_profile_period",
                "ordering": ["profile", "sequence"],
            },
        ),
        migrations.AddConstraint(
            model_name="ScheduleProfilePeriod",
            constraint=models.UniqueConstraint(
                fields=["profile", "sequence"],
                name="tt_spp_profile_seq_uniq",
            ),
        ),

        # ── 3. TimetableVersion ───────────────────────────────────────────────
        migrations.CreateModel(
            name="TimetableVersion",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("school", models.ForeignKey(
                    db_column="school_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_versions",
                    to="sms.schoolbranch",
                )),
                ("academic_year", models.ForeignKey(
                    db_column="academic_year_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_versions",
                    to="sms.edusession",
                )),
                ("version_no",     models.PositiveSmallIntegerField()),
                ("effective_from", models.CharField(max_length=10)),
                # AD shadow — DB-managed; editable=False so ORM never writes it
                ("effective_from_ad", models.DateField(
                    editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                ("status", models.CharField(max_length=12, default="draft", choices=[
                    ("draft","Draft"), ("published","Published"), ("archived","Archived")])),
                ("published_at", models.DateTimeField(null=True, blank=True)),
                ("published_by", models.ForeignKey(
                    db_column="published_by",
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name="published_timetable_versions",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("change_note", models.TextField(blank=True)),
                ("archived_at", models.DateTimeField(null=True, blank=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("created_by",  models.ForeignKey(
                    db_column="created_by",
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name="created_timetable_versions",
                    to=settings.AUTH_USER_MODEL,
                )),
                # NOTE: no updated_at — versions are immutable (invariant #1)
            ],
            options={"db_table": "timetable_version"},
        ),
        migrations.AddConstraint(
            model_name="TimetableVersion",
            constraint=models.UniqueConstraint(
                fields=["school", "academic_year", "version_no"],
                name="tt_version_school_year_no_uniq",
            ),
        ),
        # State-only placeholder for the DESC covering index created by RunPython below.
        # database_operations=[] prevents Django from issuing its own CREATE INDEX.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="TimetableVersion",
                    index=models.Index(
                        fields=["school", "academic_year", "effective_from"],
                        name="tt_version_school_year_eff_idx",
                    ),
                ),
            ],
            database_operations=[],
        ),

        # ── 4. TimetableEntry ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="TimetableEntry",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("version", models.ForeignKey(
                    db_column="version_id",
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="entries",
                    to="timetable.timetableversion",
                )),
                ("section", models.ForeignKey(
                    db_column="section_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_entries",
                    to="sms.section",
                )),
                ("period", models.ForeignKey(
                    db_column="period_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_entries",
                    to="timetable.scheduleprofileperiod",
                )),
                ("subject", models.ForeignKey(
                    db_column="subject_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_entries",
                    to="sms.subject",
                )),
                ("teacher", models.ForeignKey(
                    db_column="teacher_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_entries",
                    to=settings.AUTH_USER_MODEL,
                )),
                # TODO: FK to Room once that table exists
                ("room_id", models.IntegerField(null=True, blank=True)),
                ("recurrence", models.CharField(max_length=10, choices=[
                    ("daily","Daily"), ("weekly","Weekly"),
                    ("monthly","Monthly"), ("once","Once")])),
                # Bitmask: Mon=1 Tue=2 Wed=4 Thu=8 Fri=16 Sat=32 Sun=64
                ("days_of_week",  models.SmallIntegerField(null=True, blank=True)),
                ("day_of_month",  models.PositiveSmallIntegerField(null=True, blank=True)),
                # BS canonical dates
                ("specific_date", models.CharField(max_length=10, null=True, blank=True)),
                ("valid_from",    models.CharField(max_length=10, null=True, blank=True)),
                ("valid_to",      models.CharField(max_length=10, null=True, blank=True)),
                # AD shadows — DB-managed; editable=False so ORM never writes them.
                # specific_date / valid_from / valid_to are nullable sources, so
                # their shadows are also nullable (GENERATED NULL when source IS NULL).
                ("specific_date_ad", models.DateField(
                    null=True, blank=True, editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                ("valid_from_ad", models.DateField(
                    null=True, blank=True, editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                ("valid_to_ad", models.DateField(
                    null=True, blank=True, editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                ("entry_type", models.CharField(max_length=10, default="regular", choices=[
                    ("regular","Regular"), ("special","Special")])),
                # Number of consecutive CLASS periods this entry occupies.
                # 1 = single period (default). Must not cross a break or shift boundary.
                ("period_span", models.PositiveSmallIntegerField(default=1)),
                ("archived_at", models.DateTimeField(null=True, blank=True)),
                ("created_at",  models.DateTimeField(auto_now_add=True)),
                ("created_by",  models.ForeignKey(
                    db_column="created_by",
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name="created_timetable_entries",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"db_table": "timetable_entry"},
        ),
        migrations.AddConstraint(
            model_name="TimetableEntry",
            constraint=models.CheckConstraint(
                check=(
                    (
                        models.Q(days_of_week__isnull=False)
                        & models.Q(day_of_month__isnull=True)
                        & models.Q(specific_date__isnull=True)
                    ) | (
                        models.Q(days_of_week__isnull=True)
                        & models.Q(day_of_month__isnull=False)
                        & models.Q(specific_date__isnull=True)
                    ) | (
                        models.Q(days_of_week__isnull=True)
                        & models.Q(day_of_month__isnull=True)
                        & models.Q(specific_date__isnull=False)
                    )
                ),
                name="tt_entry_exactly_one_strategy",
            ),
        ),
        migrations.AddConstraint(
            model_name="TimetableEntry",
            constraint=models.CheckConstraint(
                check=models.Q(period_span__gte=1),
                name="tt_entry_period_span_gte_1",
            ),
        ),
        migrations.AddIndex(
            model_name="TimetableEntry",
            index=models.Index(
                fields=["version", "section"],
                name="tt_entry_version_section_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TimetableEntry",
            index=models.Index(fields=["teacher"], name="tt_entry_teacher_idx"),
        ),
        # State-only placeholder for the partial/full index created by RunPython below.
        # database_operations=[] prevents Django from issuing its own CREATE INDEX.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddIndex(
                    model_name="TimetableEntry",
                    index=models.Index(
                        fields=["specific_date_ad"],
                        name="tt_entry_specific_date_idx",
                    ),
                ),
            ],
            database_operations=[],
        ),

        # ── 5. TimetableException ─────────────────────────────────────────────
        migrations.CreateModel(
            name="TimetableException",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("school", models.ForeignKey(
                    db_column="school_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_exceptions",
                    to="sms.schoolbranch",
                )),
                ("academic_year", models.ForeignKey(
                    db_column="academic_year_id",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="timetable_exceptions",
                    to="sms.edusession",
                )),
                ("date_from", models.CharField(max_length=10)),
                ("date_to",   models.CharField(max_length=10)),
                # AD shadows — DB-managed; editable=False
                ("date_from_ad", models.DateField(
                    editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                ("date_to_ad", models.DateField(
                    editable=False,
                    help_text="DB-managed generated column. Never assign in Python.",
                )),
                # Bitmask: NULL = every day in range
                ("days_of_week", models.SmallIntegerField(null=True, blank=True)),
                ("kind",  models.CharField(max_length=10, choices=[
                    ("whole_day","Whole Day"), ("replace","Replace"),
                    ("cancel","Cancel"), ("add","Add")])),
                ("scope", models.CharField(max_length=10, choices=[
                    ("section","Section"), ("class","Class"),
                    ("grade","Grade"), ("school","School")])),
                # Generic FK — target depends on scope; resolver resolves
                # TODO: replace with GenericForeignKey once scope handling is stable
                ("scope_id", models.IntegerField()),
                # Bare integers — no DB FK on these (see models.py for rationale)
                # TODO: period_id → FK to ScheduleProfilePeriod once DB FK is added
                ("period_id",  models.IntegerField(null=True, blank=True)),
                # TODO: subject_id → FK to Subject once DB FK is added
                ("subject_id", models.IntegerField(null=True, blank=True)),
                # TODO: teacher_id → FK to AUTH_USER_MODEL once column type is aligned
                ("teacher_id", models.IntegerField(null=True, blank=True)),
                # TODO: room_id → FK to Room once that table exists
                ("room_id",    models.IntegerField(null=True, blank=True)),
                # Mandatory (invariant #6) — NOT NULL
                ("reason",     models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(
                    db_column="created_by",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="created_timetable_exceptions",
                    to=settings.AUTH_USER_MODEL,
                    # NOT NULL — mandatory audit field
                )),
                ("locked_at",   models.DateTimeField(null=True, blank=True)),
                ("archived_at", models.DateTimeField(null=True, blank=True)),
            ],
            options={"db_table": "timetable_exception"},
        ),
        migrations.AddConstraint(
            model_name="TimetableException",
            constraint=models.CheckConstraint(
                check=models.Q(date_to__gte=models.F("date_from")),
                name="tt_exc_date_to_gte_date_from",
            ),
        ),
        migrations.AddIndex(
            model_name="TimetableException",
            index=models.Index(
                fields=["school", "date_from_ad"],
                name="tt_exc_school_date_from_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TimetableException",
            index=models.Index(
                fields=["school", "academic_year"],
                name="tt_exc_school_year_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="TimetableException",
            index=models.Index(fields=["teacher_id"], name="tt_exc_teacher_idx"),
        ),

        # ── Generated AD columns + custom index DDL ───────────────────────────
        # RunPython handles vendor differences and avoids transaction wrapping.
        # Must run AFTER all tables are created.
        migrations.RunPython(fwd_generated,      rev_generated),
        migrations.RunPython(fwd_custom_indexes, rev_custom_indexes),
    ]

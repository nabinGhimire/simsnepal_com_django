# Exam Result Calculation Configuration Guide

## Overview

The exam module uses a multi-layered configuration system for calculating and displaying student results. Understanding how these layers interact is crucial for correct result generation.

---

## Configuration Layers

### 1. GradeResultConfig (Per Grade/Session)
**Location:** `/exam/settings/result-config/`
**Model:** `exam.models.GradeResultConfig`

| Field | Type | Options | Description |
|-------|------|---------|-------------|
| `grading_type` | Integer | `0=Legacy`, `1=Non-Grade System`, `2=New Grading System` | Determines which grading algorithm to use |
| `ledger_type` | Integer | `1=Marks`, `2=Grade` | What to display in ledgers: raw marks or letter grades |
| `calculation_type` | String | `legacy`, `weighted` | How to combine marks across terms |
| `assessment_source` | String | `exam`, `internal` | Source of assessment data |
| `th_pass_type` | String | `percentage`, `gpa`, `marks` | Pass logic for Theory |
| `th_pass_value` | Decimal | e.g., `35.00`, `1.60`, `20` | Pass threshold for Theory |
| `pr_pass_type` | String | `percentage`, `gpa`, `marks` | Pass logic for Practical |
| `pr_pass_value` | Decimal | e.g., `35.00`, `1.60`, `20` | Pass threshold for Practical |

---

### 2. ResultManagement (Term Calculation Weights)
**Location:** `/exam/terms/?action=result_calc`
**Model:** `sms.models.ResultManagement`

Stores JSON configuration for weighted calculation. **Two schemas are supported:**

**Schema A (Simple - scalar weights):**
```json
{
  "plan": "direct|scaling",
  "target_fm_th": 100,
  "target_fm_pr": 100,
  "sources": {
    "mid_term_id": 40,
    "final_term_id": 60
  }
}
```

**Schema B (Advanced - per-component weights):**
```json
{
  "plan": "direct|scaling",
  "target_fm_th": 100,
  "target_fm_pr": 100,
  "sources": {
    "1": {"th": 100, "pr": 100},
    "2": {"th": 80, "pr": 20}
  }
}
```

- `plan: "direct"` - Apply weights directly to obtained marks
- `plan: "scaling"` - Scale marks to target full marks before applying weights
- When source value is a number, it's used for both TH and PR equally
- When source value is an object, `th` and `pr` weights are applied separately

---

### 3. WeightedResultManagement (Advanced Weighting)
**Model:** `exam.models.WeightedResultManagement`

More flexible configuration with separate TH/PR mixing:
```json
{
  "th_from_th": 0.8,
  "th_from_pr": 0.2,
  "pr_from_th": 0.1,
  "pr_from_pr": 0.9,
  "plan": "direct|scaling",
  "th_target_fm": 100,
  "pr_target_fm": 100
}
```

---

### 4. Print Mode (Runtime Selection)
**Views:** `/exam/print/ledger/`, `/exam/print/grade-ledger/`, `/exam/print/result/`

Runtime options that override or work with above configs:
- **Ledger Mode**: `1=Standard`, `2=Weighted Breakdown`, `3=Consolidated Raw`
- **Ledger Type**: `1=Marks`, `2=Grade`
- **Grading System**: `0=Legacy`, `1=Non-Grade`, `2=New Grading`
- **Calculation**: `legacy`, `weighted`

---

## Grade Boundaries (Percentage → Grade Point)

| Percentage Range | Grade | Symbol | Grade Point |
|------------------|-------|--------|-------------|
| 90 - 100 | A | + | 4.0 |
| 80 - 89 | A | (space) | 3.6 |
| 70 - 79 | B | + | 3.2 |
| 60 - 69 | B | (space) | 2.8 |
| 50 - 59 | C | + | 2.4 |
| 40 - 49 | C | (space) | 2.0 |
| 35 - 39 | D | (space) | 1.6 |
| 0 - 34 | NG | (space) | 0.0 |

**Pass Threshold:** Grade Point ≥ 1.6 (i.e., Percentage ≥ 35%)

---

## Grading Algorithms

### Legacy (grading_type=0) - `GradeAndGpa`
- **Combined grade** for TH+PR together
- Percentage = (TH_MO + PR_MO) / (TH_FM + PR_FM) × 100
- Single grade point from combined percentage using table above
- Fail if combined percentage < 35% (GPA < 1.6)

### Non-Grade System (grading_type=1) - `GradeAndGpaNonGradeTheory/Practical`
- **Separate grades** for Theory and Practical
- Each component gets its own grade/GP from percentage
- Default pass threshold: **35% for both TH and PR** (configurable via `th_pass_value`/`pr_pass_value`)
- GPA calculated per component, then averaged
- More granular fail tracking (can fail TH but pass PR)

### New Grading System (grading_type=2) - `GradeAndGpaNew`
- Similar to Legacy but **stricter fail rules**
- If TH fails OR PR fails → total grade = NG, GPA = 0
- Used for board exam compliance

---

## How Configuration Affects Calculation

### Grade Sheet (`/exam/print/marks-grade-sheet/`)
1. Reads `GradeResultConfig` for the grade/session
2. Uses `grading_type` to select algorithm
3. If `calculation_type=weighted`, applies term weights from `ResultManagement`
4. Displays per-subject grades based on `ledger_type`

### Grade Ledger (`/exam/print/grade-ledger/`)
1. Reads `GradeResultConfig` for the grade/session
2. Uses `grading_type` + `ledger_type` from config
3. Builds term list from `ResultManagement.term_calculation`
4. Applies weighting if `calculation_type=weighted`
5. Can override with runtime `grading_type` parameter

### Mark Ledger Preview (`/exam/print/ledger/preview/`)
- **Mode 1 (Standard)**: Current term raw marks only
- **Mode 2 (Weighted Breakdown)**: Shows each source term with weights applied
- **Mode 3 (Consolidated Raw)**: Sums raw marks from all source terms

### Unified Result (`/exam/print/result/`)
- **Raw Mode**: Shows actual marks from `MarkObtained`
- **Calculated Mode**: Full grading with config from `GradeResultConfig`

---

## Pass/Fail Logic

### Legacy (grading_type=0)
- **Combined TH+PR percentage** < 35% → Fail
- Single combined grade for TH+PR

### Non-Grade System (grading_type=1)
- **Separate pass logic** for TH and PR
- **Theory**: Fail if (TH_MO / TH_FM × 100) < `th_pass_value` (default 35%)
- **Practical**: Fail if (PR_MO / PR_FM × 100) < `pr_pass_value` (default 35%)
- Separate grades for TH and PR

### New Grading System (grading_type=2)
- Same calculation as Legacy
- **But**: If TH fails OR PR fails → overall grade = NG, GP = 0

---

## Terminology Settings
**Location:** `/exam/settings/terminologies/`
**Model:** `exam.models.SchoolTerminology`

| Field | Default | Usage |
|-------|---------|-------|
| `theory_short` | `TH` | Column headers |
| `theory_long` | `Theory` | Legends/footers |
| `practical_short` | `PR` | Column headers |
| `practical_long` | `Practical` | Legends/footers |

---

## Recommended Configuration

### For Standard School (NEB/Board Compliance)
```json
{
  "grading_type": 2,
  "ledger_type": 2,
  "calculation_type": "legacy",
  "assessment_source": "exam",
  "th_pass_type": "gpa",
  "th_pass_value": 1.60,
  "pr_pass_type": "gpa",
  "pr_pass_value": 1.60
}
```

### For Internal Assessment (Marks-based)
```json
{
  "grading_type": 1,
  "ledger_type": 1,
  "calculation_type": "legacy",
  "th_pass_type": "percentage",
  "th_pass_value": 35.00,
  "pr_pass_type": "percentage",
  "pr_pass_value": 35.00
}
```

### For Weighted Final (e.g., 40% Mid + 60% Final)
```json
{
  "calculation_type": "weighted",
  "ResultManagement": {
    "plan": "direct",
    "target_fm_th": 100,
    "target_fm_pr": 100,
    "sources": {
      "mid_term_id": 40,
      "final_term_id": 60
    }
  }
}
```

---

## Testing Checklist

1. Create test students with known marks
2. Verify pass/fail matches expected thresholds
3. Check CGPA calculation matches manual computation
4. Verify rank skips failed students
5. Test weighted calculation with known inputs
6. Compare Raw vs Calculated modes
7. Export to Excel and verify formulas
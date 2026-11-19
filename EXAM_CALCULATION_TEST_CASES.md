# Exam Calculation Test Cases & Sample Data

## Sample Student Data

### Student: John Doe (Reg: 2024001)
**Grade:** 10 | **Section:** A | **Session:** 2084

| Subject | TH_FM | TH_PM | PR_FM | PR_PM | TH_MO (Mid) | PR_MO (Mid) | TH_MO (Final) | PR_MO (Final) |
|---------|-------|-------|-------|-------|-------------|-------------|---------------|---------------|
| Nepali  | 75    | 27    | 25    | 9     | 45          | 15          | 60            | 20            |
| English | 75    | 27    | 25    | 9     | 50          | 18          | 65            | 22            |
| Math    | 75    | 27    | 25    | 9     | 30          | 10          | 55            | 18            |
| Science | 75    | 27    | 25    | 9     | 40          | 12          | 50            | 15            |
| Social  | 75    | 27    | 25    | 9     | 35          | 10          | 45            | 12            |

---

## Test Case 1: Legacy Grading (grading_type=0)

### Configuration
```json
{
  "grading_type": 0,
  "ledger_type": 2,
  "calculation_type": "legacy",
  "th_pass_type": "percentage",
  "th_pass_value": 35,
  "pr_pass_type": "percentage", 
  "pr_pass_value": 35
}
```

### Final Term Only Calculation
| Subject | TH% | PR% | Total% | Grade | GP | Status |
|---------|-----|-----|--------|-------|----|--------|
| Nepali  | 80.00% | 80.00% | 80.00% | A | 3.6 | Pass |
| English | 86.67% | 88.00% | 87.00% | A | 3.6 | Pass |
| Math    | 73.33% | 72.00% | 73.00% | B+ | 3.2 | Pass |
| Science | 66.67% | 60.00% | 65.00% | B | 2.8 | Pass |
| Social  | 60.00% | 48.00% | 57.00% | B | 2.8 | Pass |

**Calculations:**
- Nepali: TH=60/75=80%, PR=20/25=80%, Total=80/100=80% → A/3.6
- English: TH=65/75=86.67%, PR=22/25=88%, Total=87/100=87% → A/3.6
- Math: TH=55/75=73.33%, PR=18/25=72%, Total=73/100=73% → B+/3.2
- Science: TH=50/75=66.67%, PR=15/25=60%, Total=65/100=65% → B/2.8
- Social: TH=45/75=60%, PR=12/25=48%, Total=57/100=57% → B/2.8

**CGPA:** (3.6+3.6+3.2+2.8+2.8)/5 = **3.2** → **B+**

---

## Test Case 2: New Grading System (grading_type=2)

### Same data, New Grading
| Subject | TH% | PR% | Total% | Grade | GP | Fail? |
|---------|-----|-----|--------|-------|----|-------|
| Nepali  | 80.00% | 80.00% | 80.00% | A | 3.6 | No |
| English | 86.67% | 88.00% | 87.00% | A | 3.6 | No |
| Math    | 73.33% | 72.00% | 73.00% | B+ | 3.2 | No |
| Science | 66.67% | 60.00% | 65.00% | B | 2.8 | No |
| Social  | 60.00% | 48.00% | 57.00% | B | 2.8 | No |

**CGPA:** 3.2 → **B+**

> **Note:** Results identical to Legacy because all subjects pass. Difference appears when failures occur.

---

## Test Case 3: Failure Scenario (Math Fail)

### Modified Data: Math TH_MO=20 (26.67%), PR_MO=8 (32%)

### Legacy (grading_type=0)
| Subject | TH% | PR% | Total% | Grade | GP | Fail? |
|---------|-----|-----|--------|-------|----|-------|
| Nepali  | 80.00% | 80.00% | 80.00% | A | 3.6 | No |
| English | 86.67% | 88.00% | 87.00% | A | 3.6 | No |
| **Math** | **26.67%** | **32.00%** | **28.00%** | **NG** | **0** | **YES** |
| Science | 66.67% | 60.00% | 65.00% | B | 2.8 | No |
| Social  | 60.00% | 48.00% | 57.00% | B | 2.8 | No |

**CGPA:** (3.6+3.6+0+2.8+2.8)/5 = **2.56** → **C+**

### New Grading (grading_type=2)
| Subject | TH% | PR% | Total% | Grade | GP | Fail? |
|---------|-----|-----|--------|-------|----|-------|
| Nepali  | 80.00% | 80.00% | 80.00% | A | 3.6 | No |
| English | 86.67% | 88.00% | 87.00% | A | 3.6 | No |
| **Math** | **26.67%** | **32.00%** | **28.00%** | **NG** | **0** | **YES** |
| Science | 66.67% | 60.00% | 65.00% | B | 2.8 | No |
| Social  | 60.00% | 48.00% | 57.00% | B | 2.8 | No |

**CGPA:** 2.56 → **C+** (but overall fail due to Math NG)

### Non-Grade System (grading_type=1)
| Subject | TH% | TH Grade | PR% | PR Grade | Total Grade | GP | Fail? |
|---------|-----|----------|-----|----------|-------------|----|-------|
| Nepali  | 80.00% | A | 80.00% | A | A | 3.6 | No |
| English | 86.67% | A | 88.00% | A | A | 3.6 | No |
| **Math** | **26.67%** | **NG** | **32.00%** | **NG** | **NG** | **0** | **YES** |
| Science | 66.67% | B | 60.00% | B | B | 2.8 | No |
| Social  | 60.00% | B | 48.00% | C | B | 2.8 | No |

**CGPA:** (3.6+3.6+0+2.8+2.8)/5 = **2.56** → **C+**

> **Key Difference:** Non-Grade shows separate TH/PR grades. Math fails both components.

---

## Test Case 4: Weighted Calculation (40% Mid + 60% Final)

### Configuration
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

### Nepali Subject Calculation
| Component | Mid (40%) | Final (60%) | Weighted |
|-----------|-----------|-------------|----------|
| TH_MO | 45 | 60 | 45×0.4 + 60×0.6 = **54** |
| PR_MO | 15 | 20 | 15×0.4 + 20×0.6 = **18** |
| TH_FM | 75 | 75 | 75×0.4 + 75×0.6 = **75** |
| PR_FM | 25 | 25 | 25×0.4 + 25×0.6 = **25** |

**Weighted %:** (54+18)/(75+25) = 72% → **B+ (3.2)**

### With Scaling Plan
```json
{
  "plan": "scaling",
  "target_fm_th": 100,
  "target_fm_pr": 100
}
```
- Scales each term's marks to target FM before weighting
- Same result in this case since both terms have same FM

---

## Test Case 5: Pass/Fail Threshold Variations

### Configuration A: Percentage (35%)
| Subject | TH% | Pass? |
|---------|-----|-------|
| Math (26.7%) | 26.7% | **FAIL** |

### Configuration B: GPA (1.60)
| Subject | GP | Pass? |
|---------|-----|-------|
| Math (NG) | 0.0 | **FAIL** |

### Configuration C: Absolute Marks (25)
| Subject | TH_MO | Pass? |
|---------|-------|-------|
| Math | 20 | **FAIL** |

> All three configurations give same result for this data, but differ at boundaries.

---

## Test Case 6: Rank Calculation

### Students with Total Marks
| Student | Total MO | Total FM | % | CGPA | Rank |
|---------|----------|----------|---|------|------|
| Alice | 450 | 500 | 90% | 3.8 | 1 |
| Bob | 400 | 500 | 80% | 3.4 | 2 |
| Charlie | 350 | 500 | 70% | 3.0 | 3 |
| David (FAIL) | 250 | 500 | 50% | 2.0 | **None** |

**Rank by Total:** Alice(1), Bob(2), Charlie(3) - David omitted
**Rank by TH Only:** Same order
**Rank by GPA:** Same order

---

## Test Case 7: Consolidated Raw Mode (Ledger Mode 3)

### Source Terms: Unit Test (20%), Mid (30%), Final (50%)
| Subject | Unit TH | Mid TH | Final TH | Consolidated TH |
|---------|---------|--------|----------|-----------------|
| Nepali | 18/20 | 45/75 | 60/75 | 18+45+60 = **123** / (20+75+75) = **123/170** |

**Total FM:** Sum of all term FMs
**Total MO:** Sum of all term MOs

---

## Expected Output Formats

### Grade Sheet (Detail)
```
S.N | Subject    | TH_FM | TH_MO | PR_FM | PR_MO | Grade | GP | Status
1   | Nepali     | 75    | 60    | 25    | 20    | A     | 3.6| Pass
```

### Grade Sheet (Summary)
```
S.N | Name       | RegNo | Roll | Rank | TotFM | TotMO | %   | CGPA | Grade | Status
1   | John Doe   | 001   | 5    | 2    | 500   | 400   | 80% | 3.4  | B+    | Pass
```

### Grade Ledger (Multi-term)
```
S.N | Name | RegNo | Roll | Rank | Term1 TH | Term1 PR | Term1 Tot | ... | TotFM | TotMO | % | CGPA | Grade | Status
```

### Mark Ledger Preview
| S.N | RegNo | Roll | Name | Term | Subject | TH | PR | TH_Max | PR_Max |
|-----|-------|------|------|------|---------|----|----|--------|--------|

---

## Configuration Decision Matrix

| Requirement | Grading Type | Ledger Type | Calc Type | Pass Type |
|-------------|--------------|-------------|-----------|-----------|
| Board exam compliance | 2 (New) | 2 (Grade) | legacy | GPA 1.6 |
| Internal marks tracking | 1 (Non-Grade) | 1 (Marks) | legacy | % 35 |
| Weighted final exam | 2 (New) | 2 (Grade) | weighted | GPA 1.6 |
| CCE/Continuous assessment | 1 (Non-Grade) | 1 (Marks) | weighted | % 35 |
| Simple marksheet | 0 (Legacy) | 2 (Grade) | legacy | % 35 |

---

## Validation Queries

```sql
-- Check pass/fail consistency
SELECT student_id, COUNT(*) as fail_count
FROM mark_obtained mo
JOIN grade_full_marks gfm ON ...
WHERE (mo.th_mo / gfm.th_fm * 100) < 35
   OR (mo.pr_mo / gfm.pr_fm * 100) < 35
GROUP BY student_id;

-- Verify CGPA calculation
SELECT s.reg_no, AVG(gp) as cgpa
FROM student_subject_grades
GROUP BY s.reg_no;

-- Rank skipping failures
SELECT s.reg_no, RANK() OVER (ORDER BY total_mo DESC) as rank
FROM student_totals
WHERE fail_count = 0;
```
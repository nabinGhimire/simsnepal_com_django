with open(r'C:\Projects\sims\sims_django\panel\views.py', 'r', encoding='utf-8') as f:
    content = f.read()

if 'pass_fail_filter=data_filter' in content and 'ledgermode == "4"' in content:
    print('ledgermode=4 handler with pass_fail_filter: YES')
else:
    print('Check failed')

# Verify the filter logic in build_grade_ledger_nongraded
if 'pass_fail_filter == 1' in content and 'pass_fail_filter == 2' in content:
    print('Filter logic in build_grade_ledger_nongraded: YES')
else:
    print('Filter logic missing')
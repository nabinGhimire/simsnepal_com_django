import re

with open('static/css/home.css', 'r', encoding='utf-8') as f:
    home_css = f.read()

# Extract card grid and u-card styles
card_pattern = re.compile(r'(\.card-grid[\s\S]*?)(?=\n\s*\.features-brief-section|\Z)', re.MULTILINE)
match = card_pattern.search(home_css)
if match:
    card_css = match.group(1)
    
    with open('static/css/base.css', 'a', encoding='utf-8') as f:
        f.write('\n/* Global Card Components */\n')
        f.write(card_css)
        
    print('Cards moved to base.css')
    
    # Remove it from home.css to avoid duplication? Actually, leaving it is harmless, but better to remove.
    home_css = home_css.replace(card_css, '')
    with open('static/css/home.css', 'w', encoding='utf-8') as f:
        f.write(home_css)
else:
    print('Could not find card-grid in home.css')


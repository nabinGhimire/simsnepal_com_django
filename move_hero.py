import re

with open('static/css/home.css', 'r', encoding='utf-8') as f:
    home_css = f.read()

# Extract hero section CSS block (assuming it starts with .hero-section and ends before the next major section, or we can just extract using regex)
hero_pattern = re.compile(r'(\.hero-section[\s\S]*?)(?=\n\s*\.features-brief-section|\n\s*\.card-grid|\Z)', re.MULTILINE)
match = hero_pattern.search(home_css)
if match:
    hero_css = match.group(1)
    
    with open('static/css/base.css', 'a', encoding='utf-8') as f:
        f.write('\n/* Global Components */\n')
        f.write(hero_css)
        
    print('Hero section moved to base.css')
    
    # Optionally remove it from home.css
    home_css = home_css.replace(hero_css, '')
    with open('static/css/home.css', 'w', encoding='utf-8') as f:
        f.write(home_css)
else:
    print('Could not find hero-section in home.css')


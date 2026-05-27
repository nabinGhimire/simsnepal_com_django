import os
import re

def process_template(name, old_css_name, custom_css_name):
    html_path = f'frontend/templates/frontend/{name}.html'
    
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # If it has inline style, extract it
    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if style_match:
        style_content = style_match.group(1).strip()
        css_path = f'static/css/{custom_css_name}'
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(style_content)
        print(f'Extracted inline CSS from {name}.html to {custom_css_name}')
        # Replace inline style with link
        content = content[:style_match.start()] + f'<link rel=\"stylesheet\" href=\"{{% static \'css/{custom_css_name}\' %}}\">' + content[style_match.end():]

    # Also replace any existing links to old_css_name with custom_css_name
    # febcc51 didn't use {% load static %} for base.css because it was in builtins, but it used {% static ... %}
    if old_css_name:
        content = content.replace(f'{{% static \'css/{old_css_name}\' %}}', f'{{% static \'css/{custom_css_name}\' %}}')
        # Just in case it was hardcoded:
        content = content.replace(f'/static/css/{old_css_name}', f'{{% static \'css/{custom_css_name}\' %}}')
    
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
process_template('base', 'base.css', 'custom_base.css')
process_template('home', 'home.css', 'custom_home.css')
process_template('about', 'about.css', 'custom_about.css')
process_template('features', 'features.css', 'custom_features.css')
process_template('faq', 'faq.css', 'custom_faq.css')
process_template('pricing', 'pricing.css', 'custom_pricing.css')
process_template('contact', 'contact.css', 'custom_contact.css')

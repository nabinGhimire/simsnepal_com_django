import re
import os

def extract_css(html_path, css_name):
    css_path = os.path.join('static/css', css_name)
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    style_match = re.search(r'<style>(.*?)</style>', content, re.DOTALL)
    if style_match:
        style_content = style_match.group(1).strip()
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(style_content)
        
        new_content = content[:style_match.start()] + f'<link rel=\"stylesheet\" href=\"{{% static \'css/{css_name}\' %}}\">' + content[style_match.end():]
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Extracted {css_name} from {html_path}')
    else:
        print(f'No style block found in {html_path}')

extract_css('frontend/templates/frontend/base.html', 'sims_base.css')
extract_css('frontend/templates/frontend/home.html', 'sims_home.css')
extract_css('frontend/templates/frontend/about.html', 'sims_about.css')
extract_css('frontend/templates/frontend/features.html', 'sims_features.css')
extract_css('frontend/templates/frontend/faq.html', 'sims_faq.css')
extract_css('frontend/templates/frontend/pricing.html', 'sims_pricing.css')
extract_css('frontend/templates/frontend/contact.html', 'sims_contact.css')

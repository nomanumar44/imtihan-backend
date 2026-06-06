#!/usr/bin/env python
"""Debug script using curl to analyze gotest.com.pk HTML structure"""

import subprocess
import json
from bs4 import BeautifulSoup

print("Fetching English test page using curl...")
url = 'https://gotest.com.pk/general-english-online-test-preparation/'

# Fetch using curl
result = subprocess.run(
    ['curl', '-s', '-A', 'Mozilla/5.0', url],
    capture_output=True
)

if result.returncode != 0:
    print(f"Error fetching: {result.stderr}")
    exit(1)

html = result.stdout.decode('utf-8', errors='replace')
soup = BeautifulSoup(html, 'html.parser')

print("=" * 60)
print("PAGE STRUCTURE ANALYSIS")
print("=" * 60)

# Find test links
print("\n1. Test Links Found:")
links = soup.find_all('a', href=True)
test_links = [l for l in links if any(x in l.get('href', '').lower() for x in ['test', 'quiz', 'q='])]
print(f"   Total test/quiz links: {len(test_links)}")
for i, link in enumerate(test_links[:5]):
    href = link.get('href', '')
    text = link.text.strip()[:50]
    print(f"   {i+1}. {text}")
    print(f"      {href[:100]}")

# Try fetching first test
if test_links:
    test_url = test_links[0].get('href', '')
    if test_url.startswith('/'):
        test_url = 'https://gotest.com.pk' + test_url
    
    print(f"\n2. Fetching test: {test_url[:80]}")
    result = subprocess.run(
        ['curl', '-s', '-A', 'Mozilla/5.0', test_url],
        capture_output=True,
        timeout=30
    )
    
    if result.returncode == 0:
        test_html = result.stdout.decode('utf-8', errors='replace')
        test_soup = BeautifulSoup(test_html, 'html.parser')
        
        # Save for inspection
        with open('gotest_test_page.html', 'w', encoding='utf-8') as f:
            f.write(test_html)
        
        print("\n3. Question/Answer Elements:")
        
        # Look for divs with common class patterns
        all_divs = test_soup.find_all('div')
        print(f"   Total divs: {len(all_divs)}")
        
        # Look for data or structure hints
        for pattern in ['watupro', 'question', 'answer', 'quiz', 'mcq', 'option', 'choice']:
            elements = test_soup.find_all(class_=lambda x: x and pattern in x.lower())
            if elements:
                print(f"   Found {len(elements)} elements with '{pattern}' in class")
                if len(elements) > 0:
                    print(f"      First: {elements[0].name} class={elements[0].get('class')}")
                    print(f"      Text preview: {elements[0].get_text(strip=True)[:60]}")
        
        # Look for answer markers
        print("\n4. Looking for answer patterns:")
        html_lower = test_html.lower()
        if 'correct-answer' in html_lower:
            print("   ✓ Found 'correct-answer' class")
        if 'watupro' in html_lower:
            print("   ✓ Found 'watupro' elements")
        if '<li class' in html_lower:
            lis = test_soup.find_all('li')
            print(f"   ✓ Found {len(lis)} <li> elements")
            for li in lis[:5]:
                cls = li.get('class', [])
                print(f"      class={cls} text={li.get_text(strip=True)[:50]}")
        
        print("\n5. Saved to: gotest_test_page.html")

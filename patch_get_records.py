with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = 'where_clauses = []\n        params = []'
replacement = '''where_clauses = []
        params = []
        
        # Filter out records where birth year is before 1962.
        # Year < 1962 means RFC YY (chars 5-6) is between '27' and '61'.
        where_clauses.append("(SUBSTR(u6rfc, 5, 2) NOT BETWEEN '27' AND '61' OR LENGTH(u6rfc) < 6)")
'''

content = content.replace(target, replacement)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

import sys
p = r"C:\Users\Usuario\Desktop\Minimarket\SWI\modules\theme_editor.py"
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()
stack = []  # stores (indent_level, line_no)
for i, line in enumerate(lines, start=1):
    stripped = line.lstrip()
    indent = len(line) - len(stripped)
    s = stripped.strip()
    if s.startswith('try:'):
        stack.append((indent, i))
    elif s.startswith('except') or s.startswith('finally'):
        # find a matching try with indent <= this indent
        matched = False
        for j in range(len(stack)-1, -1, -1):
            if stack[j][0] <= indent:
                stack.pop(j)
                matched = True
                break
        if not matched:
            print(f"Unmatched '{s.split()[0]}' at line {i}: {line.rstrip()}")
            sys.exit(1)
print('Stack remaining (unmatched try count):', len(stack))
if stack:
    for indent, lineno in stack:
        print(' Unmatched try at line', lineno)
else:
    print('All try/except/finally seem balanced by indentation heuristic')

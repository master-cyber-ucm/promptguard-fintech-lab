with open('run_redteam.py', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 1 <= i <= 200:
            spaces = len(line) - len(line.lstrip(' '))
            print(i, spaces, repr(line))